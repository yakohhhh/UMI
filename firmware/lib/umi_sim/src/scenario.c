#include "umi/sim/scenario.h"

#include <stdlib.h>
#include <string.h>

#include "umi/protocol_gen.h"

typedef struct {
    const char *name;
    uint8_t value;
} name_t;

/* Names as in protocol/constants.toml [enum.hazard_kind] and [enum.lang]. */
static const name_t HAZARD_KINDS[] = {
    {"none", UMI_HAZARD_KIND_NONE},         {"roadworks", UMI_HAZARD_KIND_ROADWORKS},
    {"pothole", UMI_HAZARD_KIND_POTHOLE},   {"blocked_lane", UMI_HAZARD_KIND_BLOCKED_LANE},
    {"obstacle", UMI_HAZARD_KIND_OBSTACLE}, {"danger", UMI_HAZARD_KIND_DANGER},
};
static const name_t LANGS[] = {
    {"none", UMI_LANG_NONE}, {"ca", UMI_LANG_CA}, {"es", UMI_LANG_ES},
    {"en", UMI_LANG_EN},     {"fr", UMI_LANG_FR},
};

/* A line, without its terminator. */
typedef struct {
    const char *p;
    const char *end;
} span_t;

static bool lookup(const name_t *names, size_t n, span_t word, uint8_t *out)
{
    size_t len = (size_t)(word.end - word.p);
    for (size_t i = 0; i < n; i++) {
        if (strlen(names[i].name) == len && memcmp(names[i].name, word.p, len) == 0) {
            *out = names[i].value;
            return true;
        }
    }
    return false;
}

/* Splits the next comma-separated field off *rest. */
static span_t take_field(span_t *rest)
{
    span_t field = {rest->p, rest->p};
    while (field.end < rest->end && *field.end != ',') {
        field.end++;
    }
    rest->p = field.end < rest->end ? field.end + 1 : field.end;
    return field;
}

static bool span_is(span_t s, const char *word)
{
    size_t len = strlen(word);
    return (size_t)(s.end - s.p) == len && memcmp(s.p, word, len) == 0;
}

/* strtof/strtoul stop at the comma; the field must be consumed exactly. */
static bool parse_float(span_t f, float *out)
{
    char *end;
    if (f.p == f.end) {
        return false;
    }
    *out = strtof(f.p, &end);
    return end == f.end;
}

static bool parse_u32(span_t f, uint32_t *out)
{
    char *end;
    if (f.p == f.end || *f.p < '0' || *f.p > '9') {
        return false;
    }
    unsigned long v = strtoul(f.p, &end, 10);
    if (end != f.end || v > UINT32_MAX) {
        return false;
    }
    *out = (uint32_t)v;
    return true;
}

static bool parse_floats(span_t *rest, float *out, size_t n)
{
    for (size_t i = 0; i < n; i++) {
        if (!parse_float(take_field(rest), &out[i])) {
            return false;
        }
    }
    return rest->p == rest->end;
}

static int hex_value(char c)
{
    if (c >= '0' && c <= '9') {
        return c - '0';
    }
    if (c >= 'a' && c <= 'f') {
        return c - 'a' + 10;
    }
    if (c >= 'A' && c <= 'F') {
        return c - 'A' + 10;
    }
    return -1;
}

static bool parse_hex(span_t f, uint8_t *out, size_t n)
{
    if ((size_t)(f.end - f.p) != 2 * n) {
        return false;
    }
    for (size_t i = 0; i < n; i++) {
        int hi = hex_value(f.p[2 * i]), lo = hex_value(f.p[2 * i + 1]);
        if (hi < 0 || lo < 0) {
            return false;
        }
        out[i] = (uint8_t)(hi << 4 | lo);
    }
    return true;
}

/* Returns NULL on success, or why the line is skipped. */
static const char *parse_line(span_t line, umi_scenario_line_t *out)
{
    span_t rest = line;
    if (!parse_u32(take_field(&rest), &out->t_ms)) {
        return "bad t_ms";
    }
    span_t kind = take_field(&rest);
    if (span_is(kind, "imu")) {
        out->kind = UMI_SCN_IMU;
        float v[6];
        if (!parse_floats(&rest, v, 6)) {
            return "imu needs ax,ay,az,gx,gy,gz";
        }
        out->as.imu.ax = v[0];
        out->as.imu.ay = v[1];
        out->as.imu.az = v[2];
        out->as.imu.gx = v[3];
        out->as.imu.gy = v[4];
        out->as.imu.gz = v[5];
    } else if (span_is(kind, "gnss")) {
        /* The sentence keeps its own commas: everything after the kind. */
        out->kind = UMI_SCN_GNSS;
        out->as.gnss.sentence = rest.p;
        out->as.gnss.len = (size_t)(rest.end - rest.p);
        if (out->as.gnss.len == 0) {
            return "empty gnss sentence";
        }
    } else if (span_is(kind, "pm")) {
        out->kind = UMI_SCN_PM;
        if (!parse_hex(take_field(&rest), out->as.pm, UMI_SCENARIO_PM_LEN) || rest.p != rest.end) {
            return "pm needs 64 hex characters";
        }
    } else if (span_is(kind, "spl")) {
        out->kind = UMI_SCN_SPL;
        if (!parse_floats(&rest, &out->as.spl_dba, 1)) {
            return "spl needs dba";
        }
    } else if (span_is(kind, "env")) {
        out->kind = UMI_SCN_ENV;
        float v[2];
        if (!parse_floats(&rest, v, 2)) {
            return "env needs temp_c,rh_pct";
        }
        out->as.env.temp_c = v[0];
        out->as.env.rh_pct = v[1];
    } else if (span_is(kind, "button")) {
        out->kind = UMI_SCN_BUTTON;
        span_t state = take_field(&rest);
        if (rest.p != rest.end || !(span_is(state, "down") || span_is(state, "up"))) {
            return "button needs down or up";
        }
        out->as.button_pressed = span_is(state, "down");
    } else if (span_is(kind, "battery")) {
        out->kind = UMI_SCN_BATTERY;
        uint32_t mv, pct;
        if (!parse_u32(take_field(&rest), &mv) || !parse_u32(take_field(&rest), &pct) ||
            rest.p != rest.end || mv > UINT16_MAX || pct > 100) {
            return "battery needs mv,pct";
        }
        out->as.battery.mv = (uint16_t)mv;
        out->as.battery.pct = (uint8_t)pct;
    } else if (span_is(kind, "keyword")) {
        out->kind = UMI_SCN_KEYWORD;
        uint32_t confidence;
        umi_keyword_result_t *kw = &out->as.keyword;
        if (!lookup(HAZARD_KINDS, sizeof HAZARD_KINDS / sizeof HAZARD_KINDS[0], take_field(&rest),
                    &kw->kind) ||
            !parse_u32(take_field(&rest), &confidence) || confidence > 100 ||
            !lookup(LANGS, sizeof LANGS / sizeof LANGS[0], take_field(&rest), &kw->lang) ||
            rest.p != rest.end) {
            return "keyword needs kind,confidence,lang";
        }
        kw->confidence = (uint8_t)confidence;
    } else {
        return "unknown kind";
    }
    return NULL;
}

bool umi_scenario_open(umi_scenario_t *s, const char *text, umi_scenario_warn_fn warn,
                       void *warn_ctx)
{
    *s = (umi_scenario_t){.text = text, .pos = text, .warn = warn, .warn_ctx = warn_ctx};
    size_t header_len = strlen(UMI_SCENARIO_HEADER);
    if (strncmp(text, UMI_SCENARIO_HEADER, header_len) != 0) {
        return false;
    }
    char after = text[header_len];
    return after == '\n' || after == '\r' || after == '\0';
}

static bool next_line(umi_scenario_t *s, span_t *line)
{
    if (*s->pos == '\0') {
        return false;
    }
    line->p = s->pos;
    const char *end = strchr(s->pos, '\n');
    if (end == NULL) {
        end = s->pos + strlen(s->pos);
        s->pos = end;
    } else {
        s->pos = end + 1;
    }
    if (end > line->p && end[-1] == '\r') {
        end--;
    }
    line->end = end;
    s->line_no++;
    return true;
}

static void skip(umi_scenario_t *s, const char *reason)
{
    s->skipped++;
    if (s->warn != NULL) {
        s->warn(s->warn_ctx, s->line_no, reason);
    }
}

bool umi_scenario_next(umi_scenario_t *s, umi_scenario_line_t *out)
{
    span_t line;
    while (next_line(s, &line)) {
        if (line.p == line.end || *line.p == '#') {
            continue;
        }
        const char *error = parse_line(line, out);
        if (error != NULL) {
            skip(s, error);
        } else if (out->t_ms < s->last_t_ms) {
            skip(s, "t_ms goes back in time");
        } else {
            s->last_t_ms = out->t_ms;
            return true;
        }
    }
    return false;
}
