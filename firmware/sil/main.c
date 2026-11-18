/* Software-in-the-loop runner: the Clip application with simulated sensors,
 * in simulated time, from a SIL scenario to .umis session logs.
 *
 *   program --scenario PATH --out PATH --device-id HEX --session-id N
 *           [--key-hex 64HEX] [--activity ride|run] [--voice on|off] [--verbose]
 */
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "host_storage.h"
#include "trace.h"
#include "umi/core/clip.h"
#include "umi/core/version.h"
#include "umi/sim/soft_signer.h"
#include "umi/sim/world.h"

/* One application step per IMU sample, as on the Clip. */
#define STEP_MS (1000u / UMI_RATES_IMU_HZ)
/* Run past the last scenario line long enough for a pending gesture (double
 * press gap) and a brake's GNSS cross-check to settle before stopping. */
#define TAIL_MS 2500u

enum { EXIT_USAGE = 1, EXIT_SCENARIO = 2, EXIT_NO_SESSION = 3, EXIT_STORAGE = 4 };

typedef struct {
    const char *scenario;
    const char *out;
    uint64_t device_id;
    uint32_t session_id;
    bool has_key;
    uint8_t key[UMI_PRIVATE_KEY_LEN];
    uint8_t activity;
    bool voice;
    bool verbose;
} options_t;

static void usage(void)
{
    fputs("usage: program --scenario PATH --out PATH --device-id HEX --session-id N\n"
          "               [--key-hex 64HEX] [--activity ride|run] [--voice on|off] [--verbose]\n",
          stderr);
}

static bool parse_hex_bytes(const char *hex, uint8_t *out, size_t n)
{
    if (strlen(hex) != 2 * n) {
        return false;
    }
    for (size_t i = 0; i < n; i++) {
        char byte[3] = {hex[2 * i], hex[2 * i + 1], '\0'};
        char *end;
        unsigned long v = strtoul(byte, &end, 16);
        if (*end != '\0') {
            return false;
        }
        out[i] = (uint8_t)v;
    }
    return true;
}

static bool parse_options(int argc, char **argv, options_t *o)
{
    *o = (options_t){.activity = UMI_ACTIVITY_UNKNOWN, .voice = true};
    bool has_device = false, has_session = false;
    for (int i = 1; i < argc; i++) {
        const char *arg = argv[i];
        if (strcmp(arg, "--verbose") == 0) {
            o->verbose = true;
            continue;
        }
        if (i + 1 >= argc) {
            return false;
        }
        const char *value = argv[++i];
        char *end;
        errno = 0;
        if (strcmp(arg, "--scenario") == 0) {
            o->scenario = value;
        } else if (strcmp(arg, "--out") == 0) {
            o->out = value;
        } else if (strcmp(arg, "--device-id") == 0) {
            o->device_id = strtoull(value, &end, 16);
            has_device = *value != '\0' && *end == '\0' && errno == 0 && strlen(value) <= 16;
            if (!has_device) {
                return false;
            }
        } else if (strcmp(arg, "--session-id") == 0) {
            unsigned long long id = strtoull(value, &end, 10);
            has_session = *value != '\0' && *end == '\0' && errno == 0 && id <= UINT32_MAX;
            if (!has_session) {
                return false;
            }
            o->session_id = (uint32_t)id;
        } else if (strcmp(arg, "--key-hex") == 0) {
            if (!parse_hex_bytes(value, o->key, sizeof o->key)) {
                return false;
            }
            o->has_key = true;
        } else if (strcmp(arg, "--activity") == 0) {
            if (strcmp(value, "ride") == 0) {
                o->activity = UMI_ACTIVITY_RIDE;
            } else if (strcmp(value, "run") == 0) {
                o->activity = UMI_ACTIVITY_RUN;
            } else {
                return false;
            }
        } else if (strcmp(arg, "--voice") == 0) {
            if (strcmp(value, "on") != 0 && strcmp(value, "off") != 0) {
                return false;
            }
            o->voice = strcmp(value, "on") == 0;
        } else {
            return false;
        }
    }
    return o->scenario != NULL && o->out != NULL && has_device && has_session;
}

static char *read_text(const char *path)
{
    FILE *f = fopen(path, "rb");
    if (f == NULL) {
        return NULL;
    }
    char *text = NULL;
    size_t len = 0;
    if (fseek(f, 0, SEEK_END) == 0) {
        long size = ftell(f);
        if (size >= 0 && fseek(f, 0, SEEK_SET) == 0) {
            text = malloc((size_t)size + 1);
            len = text != NULL ? fread(text, 1, (size_t)size, f) : 0;
            if (text != NULL && len != (size_t)size) {
                free(text);
                text = NULL;
            }
        }
    }
    fclose(f);
    if (text != NULL) {
        text[len] = '\0';
    }
    return text;
}

static void warn_line(void *ctx, uint32_t line_no, const char *reason)
{
    fprintf(stderr, "%s:%u: skipped: %s\n", (const char *)ctx, (unsigned)line_no, reason);
}

static void print_hex(FILE *f, const uint8_t *data, size_t len)
{
    for (size_t i = 0; i < len; i++) {
        fprintf(f, "%02x", data[i]);
    }
}

int main(int argc, char **argv)
{
    options_t opt;
    if (!parse_options(argc, argv, &opt)) {
        usage();
        return EXIT_USAGE;
    }
    char *text = read_text(opt.scenario);
    if (text == NULL) {
        fprintf(stderr, "cannot read %s\n", opt.scenario);
        return EXIT_SCENARIO;
    }

    static umi_sim_world_t world;
    if (!umi_sim_world_init(&world, text, warn_line, (void *)opt.scenario)) {
        fprintf(stderr, "%s: not a v1 SIL scenario (first line must be \"%s\")\n", opt.scenario,
                UMI_SCENARIO_HEADER);
        free(text);
        return EXIT_SCENARIO;
    }

    uint32_t now_ms = 0;
    umi_trace_t trace;
    umi_trace_init(&trace, &now_ms, opt.verbose);
    static umi_host_storage_t storage;
    umi_host_storage_init(&storage, opt.out, opt.session_id);
    umi_soft_signer_t signer;
    umi_hal_signer_t signer_hal = {.alg = UMI_SIG_ALG_NONE};
    if (opt.has_key) {
        if (!umi_soft_signer_init(&signer, opt.key)) {
            fputs("--key-hex is not a valid P-256 private key\n", stderr);
            free(text);
            return EXIT_USAGE;
        }
        signer_hal = umi_soft_signer_hal(&signer);
    }

    umi_hal_t hal = {
        .buzzer = umi_trace_buzzer(&trace),
        .led = umi_trace_led(&trace),
        .storage = umi_host_storage_hal(&storage),
        .signer = signer_hal,
    };
    umi_sim_world_bind(&world, &hal);
    umi_identity_t identity = {
        .device_id = opt.device_id,
        .hw_rev = UMI_HW_REV_DEVKIT,
        .fw_version = {UMI_FW_VERSION_MAJOR, UMI_FW_VERSION_MINOR, UMI_FW_VERSION_PATCH},
        .header_flags = UMI_HEADER_FLAG_SIMULATED,
        .activity = opt.activity,
    };
    umi_settings_t settings = umi_settings_default();
    settings.voice = opt.voice;

    static umi_clip_t clip;
    umi_clip_init(&clip, &hal, &identity, &settings);
    for (;; now_ms += STEP_MS) {
        umi_sim_world_advance(&world, now_ms);
        umi_clip_step(&clip, now_ms);
        if (umi_sim_world_finished(&world) &&
            now_ms >= umi_sim_world_last_ms(&world) + TAIL_MS) {
            break;
        }
    }
    umi_clip_shutdown(&clip, now_ms);
    free(text);

    const umi_clip_stats_t *st = &clip.stats;
    printf("simulated %.1f s: %u session(s), %u flag(s), %u undo(s), %u event(s), %u chirp(s)\n",
           now_ms / 1000.0, (unsigned)st->sessions, (unsigned)st->flags, (unsigned)st->undos,
           (unsigned)st->events, (unsigned)trace.chirps);
    for (unsigned i = 0; i < storage.session_count; i++) {
        printf("wrote %s\n", storage.paths[i]);
    }
    if (opt.has_key) {
        printf("public key ");
        print_hex(stdout, signer.public_key, UMI_PUBLIC_KEY_LEN);
        printf("\n");
    }
    if (world.scenario.skipped > 0 || world.overruns > 0 || world.stray_keywords > 0) {
        fprintf(stderr, "warnings: %u line(s) skipped, %u reading(s) overrun, %u stray keyword(s)\n",
                (unsigned)world.scenario.skipped, (unsigned)world.overruns,
                (unsigned)world.stray_keywords);
    }
    if (clip.recorder.dropped > 0 || clip.recorder.writer.failed) {
        fprintf(stderr, "storage: %u record(s) dropped\n", (unsigned)clip.recorder.dropped);
        return EXIT_STORAGE;
    }
    if (st->sessions == 0) {
        fputs("no session recorded: the scenario never moved fast enough for long enough\n",
              stderr);
        return EXIT_NO_SESSION;
    }
    return EXIT_SUCCESS;
}
