/* The whole application on simulated parts: gestures to signed flags, voice
 * window, undo, chirps, settings, and a well-ordered session log. */
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unity.h>

#include "fakes.h"
#include "umi/core/clip.h"
#include "umi/sim/soft_signer.h"
#include "umi/sim/world.h"

#define STEP_MS 10u
#define RIDE_MS 32000u

static const uint8_t KEY[UMI_PRIVATE_KEY_LEN] = {
    0xc9, 0xaf, 0xa9, 0xd8, 0x45, 0xba, 0x75, 0x16, 0x6b, 0x5c, 0x21, 0x57, 0x67, 0xb1, 0xd6, 0x93,
    0x4e, 0x50, 0xc3, 0xdb, 0x36, 0xe8, 0x9b, 0x12, 0x7b, 0x8a, 0x62, 0x2b, 0x12, 0x0f, 0x67, 0x21,
};
static const umi_identity_t ID = {
    .device_id = 0x00a1b2c3d4e5f601ull,
    .fw_version = {0, 1, 0},
    .header_flags = UMI_HEADER_FLAG_SIMULATED,
    .activity = UMI_ACTIVITY_RIDE,
};

static char text[512 * 1024];
static size_t text_len;
static umi_sim_world_t world;
static fake_storage_t storage;
static fake_indicator_t ind;
static umi_soft_signer_t signer;
static umi_clip_t clip;
static fake_log_t log_;

static void add(const char *fmt, ...)
{
    va_list args;
    va_start(args, fmt);
    text_len += (size_t)vsnprintf(text + text_len, sizeof text - text_len, fmt, args);
    va_end(args);
}

static void add_nmea(uint32_t t_ms, const char *body)
{
    uint8_t sum = 0;
    for (const char *p = body; *p != '\0'; p++) {
        sum ^= (uint8_t)*p;
    }
    add("%u,gnss,$%s*%02X\n", t_ms, body, sum);
}

/* A steady ride at 5 m/s from t = 0 with GNSS from 1 s. `extra` holds more
 * scenario lines, in time order, merged where they belong. */
static void build_ride(const char *extra)
{
    text_len = 0;
    add("# umi-sil-scenario v1\n");
    for (uint32_t t = 0; t <= RIDE_MS; t += STEP_MS) {
        while (*extra != '\0' && strtoul(extra, NULL, 10) <= t) {
            const char *end = strchr(extra, '\n');
            add("%.*s\n", (int)(end - extra), extra);
            extra = end + 1;
        }
        add("%u,imu,0.2,0.0,%.2f,0,0,0\n", t, 9.81 + ((t / 10) % 7) * 0.1 - 0.3);
        if (t % 100 == 0) {
            add("%u,spl,65.0\n", t);
        }
        if (t % 1000 == 0 && t > 0) {
            char body[128];
            unsigned s = t / 1000;
            snprintf(body, sizeof body,
                     "GNRMC,0752%02u.00,A,4123.71200,N,00209.66600,E,9.72,134.6,181126,,,A", s);
            add_nmea(t, body);
            snprintf(body, sizeof body,
                     "GNGGA,0752%02u.00,4123.71200,N,00209.66600,E,1,12,0.8,42.0,M,49.5,M,,", s);
            add_nmea(t, body);
        }
    }
}

static void run(const umi_settings_t *settings)
{
    TEST_ASSERT_TRUE(umi_sim_world_init(&world, text, NULL, NULL));
    fake_storage_init(&storage, 7);
    fake_indicator_init(&ind);
    TEST_ASSERT_TRUE(umi_soft_signer_init(&signer, KEY));
    umi_hal_t hal = {
        .buzzer = fake_buzzer_hal(&ind),
        .led = fake_led_hal(&ind),
        .storage = fake_storage_hal(&storage),
        .signer = umi_soft_signer_hal(&signer),
    };
    umi_sim_world_bind(&world, &hal);
    umi_clip_init(&clip, &hal, &ID, settings);
    uint32_t now = 0;
    for (; now <= RIDE_MS + 2000; now += STEP_MS) {
        umi_sim_world_advance(&world, now);
        umi_clip_step(&clip, now);
    }
    umi_clip_shutdown(&clip, now);
    fake_log_read(&log_, storage.data, storage.len);
}

static umi_settings_t voice_on(void)
{
    umi_settings_t s = umi_settings_default();
    s.voice = true;
    return s;
}

static umi_flag_t flag_at(size_t index)
{
    umi_flag_t f;
    TEST_ASSERT_TRUE(umi_flag_decode(fake_log_find(&log_, UMI_RECORD_TYPE_FLAG, index), &f));
    return f;
}

static uint32_t session_t(uint32_t device_ms)
{
    return device_ms - clip.recorder.start_ms;
}

void setUp(void) {}
void tearDown(void) {}

static void test_session_is_complete_and_ordered(void)
{
    build_ride("");
    umi_settings_t s = umi_settings_default();
    run(&s);
    TEST_ASSERT_EQUAL(UMI_LOG_END, log_.result);
    TEST_ASSERT_EQUAL_UINT32(7, log_.header.session_id);
    TEST_ASSERT_EQUAL_UINT16(UMI_HEADER_FLAG_SIMULATED, log_.header.flags);
    TEST_ASSERT_EQUAL_size_t(1, fake_log_count(&log_, UMI_RECORD_TYPE_TIME_SYNC));
    TEST_ASSERT_TRUE(fake_log_count(&log_, UMI_RECORD_TYPE_SAMPLE) >= 25);
    for (size_t i = 1; i < log_.count; i++) {
        TEST_ASSERT_TRUE(umi_record_t_ms(&log_.records[i - 1]) <= umi_record_t_ms(&log_.records[i]));
    }
    umi_sample_t sample;
    TEST_ASSERT_TRUE(umi_sample_decode(fake_log_find(&log_, UMI_RECORD_TYPE_SAMPLE, 5), &sample));
    TEST_ASSERT_UINT16_WITHIN(20, 6500, sample.noise_cdba);
    TEST_ASSERT_EQUAL_UINT16(500, sample.speed_cms);
    TEST_ASSERT_EQUAL_UINT32(0, clip.recorder.dropped);
}

static void test_every_gesture_end_to_end(void)
{
    build_ride("12000,button,down\n12150,button,up\n"
               "15000,button,down\n16300,button,up\n17500,keyword,roadworks,92,ca\n"
               "21000,button,down\n21120,button,up\n21300,button,down\n21420,button,up\n");
    umi_settings_t s = voice_on();
    run(&s);
    TEST_ASSERT_EQUAL(UMI_LOG_END, log_.result);
    TEST_ASSERT_EQUAL_size_t(2, fake_log_count(&log_, UMI_RECORD_TYPE_FLAG));

    umi_flag_t press = flag_at(0);
    TEST_ASSERT_EQUAL_UINT32(session_t(12000), press.t_ms);
    TEST_ASSERT_EQUAL_UINT8(UMI_FLAG_SOURCE_PRESS, press.source);
    TEST_ASSERT_EQUAL_INT32(413952000, press.lat_e7);
    TEST_ASSERT_EQUAL_UINT16(500, press.speed_cms);
    TEST_ASSERT_EQUAL_UINT8(UMI_SIG_ALG_ECDSA_P256, press.sig_alg);

    umi_flag_t voice = flag_at(1);
    TEST_ASSERT_EQUAL_UINT32(session_t(15000), voice.t_ms);
    TEST_ASSERT_EQUAL_UINT16(1, voice.seq);
    TEST_ASSERT_EQUAL_UINT8(UMI_FLAG_SOURCE_VOICE, voice.source);
    TEST_ASSERT_EQUAL_UINT8(UMI_HAZARD_KIND_ROADWORKS, voice.kind);
    TEST_ASSERT_EQUAL_UINT8(UMI_LANG_CA, voice.lang);

    umi_flag_undo_t undo;
    TEST_ASSERT_TRUE(umi_flag_undo_decode(fake_log_find(&log_, UMI_RECORD_TYPE_FLAG_UNDO, 0), &undo));
    TEST_ASSERT_EQUAL_UINT16(1, undo.seq);
    TEST_ASSERT_EQUAL_UINT32(session_t(21000), undo.t_ms);

    /* flag: high; understood: low, high; undo: high, high. */
    const uint16_t H = UMI_FEEDBACK_CHIRP_HIGH_HZ, L = UMI_FEEDBACK_CHIRP_LOW_HZ;
    const uint16_t expected[] = {H, L, H, H, H};
    TEST_ASSERT_EQUAL_size_t(5, ind.tone_count);
    TEST_ASSERT_EQUAL_HEX16_ARRAY(expected, ind.tones, 5);
    TEST_ASSERT_EQUAL_UINT32(0, clip.recorder.dropped);
}

static void test_silent_voice_window_keeps_the_flag(void)
{
    build_ride("15000,button,down\n16200,button,up\n");
    umi_settings_t s = voice_on();
    run(&s);
    TEST_ASSERT_EQUAL_size_t(1, fake_log_count(&log_, UMI_RECORD_TYPE_FLAG));
    umi_flag_t f = flag_at(0);
    TEST_ASSERT_EQUAL_UINT8(UMI_FLAG_SOURCE_VOICE, f.source);
    TEST_ASSERT_EQUAL_UINT8(UMI_HAZARD_KIND_NONE, f.kind);
    TEST_ASSERT_EQUAL_size_t(1, ind.tone_count);
    TEST_ASSERT_EQUAL_UINT16(UMI_FEEDBACK_CHIRP_LOW_HZ, ind.tones[0]);
}

static void test_voice_off_makes_a_hold_a_plain_flag(void)
{
    build_ride("15000,button,down\n16300,button,up\n17000,keyword,roadworks,92,ca\n");
    umi_settings_t s = umi_settings_default();
    run(&s);
    TEST_ASSERT_EQUAL_size_t(1, fake_log_count(&log_, UMI_RECORD_TYPE_FLAG));
    TEST_ASSERT_EQUAL_UINT8(UMI_FLAG_SOURCE_PRESS, flag_at(0).source);
    TEST_ASSERT_EQUAL_UINT32(1, world.stray_keywords);
}

static void test_noise_is_not_measured_during_the_voice_window(void)
{
    build_ride("15000,button,down\n16300,button,up\n");
    umi_settings_t s = voice_on();
    run(&s);
    umi_sample_t sample;
    size_t blanked = 0;
    for (size_t i = 0; fake_log_find(&log_, UMI_RECORD_TYPE_SAMPLE, i) != NULL; i++) {
        umi_sample_decode(fake_log_find(&log_, UMI_RECORD_TYPE_SAMPLE, i), &sample);
        blanked += sample.noise_cdba == UMI_FORMAT_NOT_AVAILABLE_U16;
    }
    /* The window lasts voice_window_ms, then the average needs a second again. */
    TEST_ASSERT_UINT32_WITHIN(1, UMI_BUTTON_VOICE_WINDOW_MS / 1000 + 1, blanked);
}

static void test_chirp_off_keeps_the_led(void)
{
    build_ride("12000,button,down\n12150,button,up\n");
    umi_settings_t s = umi_settings_default();
    s.chirp = false;
    run(&s);
    TEST_ASSERT_EQUAL_size_t(1, fake_log_count(&log_, UMI_RECORD_TYPE_FLAG));
    TEST_ASSERT_EQUAL_size_t(0, ind.tone_count);
    TEST_ASSERT_TRUE(ind.led_changes >= 2);
}

static void test_press_before_the_session_is_ignored(void)
{
    build_ride("1000,button,down\n1150,button,up\n");
    umi_settings_t s = umi_settings_default();
    run(&s);
    TEST_ASSERT_EQUAL_size_t(0, fake_log_count(&log_, UMI_RECORD_TYPE_FLAG));
    TEST_ASSERT_EQUAL_size_t(0, ind.tone_count);
}

static void test_noise_sensor_off(void)
{
    build_ride("");
    umi_settings_t s = umi_settings_default();
    s.sensors = UMI_SENSOR_AIR;
    run(&s);
    umi_sample_t sample;
    TEST_ASSERT_TRUE(umi_sample_decode(fake_log_find(&log_, UMI_RECORD_TYPE_SAMPLE, 5), &sample));
    TEST_ASSERT_EQUAL_UINT16(UMI_FORMAT_NOT_AVAILABLE_U16, sample.noise_cdba);
}

static void test_live_status(void)
{
    build_ride("0,battery,3900,64\n");
    umi_settings_t s = umi_settings_default();
    TEST_ASSERT_TRUE(umi_sim_world_init(&world, text, NULL, NULL));
    fake_storage_init(&storage, 7);
    fake_indicator_init(&ind);
    umi_hal_t hal = {.buzzer = fake_buzzer_hal(&ind), .led = fake_led_hal(&ind),
                     .storage = fake_storage_hal(&storage)};
    umi_sim_world_bind(&world, &hal);
    umi_clip_init(&clip, &hal, &ID, &s);
    for (uint32_t now = 0; now <= 10000; now += STEP_MS) {
        umi_sim_world_advance(&world, now);
        umi_clip_step(&clip, now);
    }
    umi_live_status_t live;
    umi_clip_live_status(&clip, &live);
    TEST_ASSERT_EQUAL_UINT8(64, live.battery_pct);
    TEST_ASSERT_EQUAL_UINT8(UMI_RECORDER_STATE_RECORDING, live.recorder_state);
    TEST_ASSERT_EQUAL_UINT8(UMI_FIX_THREE_D, live.fix);
}

int main(void)
{
    UNITY_BEGIN();
    RUN_TEST(test_session_is_complete_and_ordered);
    RUN_TEST(test_every_gesture_end_to_end);
    RUN_TEST(test_silent_voice_window_keeps_the_flag);
    RUN_TEST(test_voice_off_makes_a_hold_a_plain_flag);
    RUN_TEST(test_noise_is_not_measured_during_the_voice_window);
    RUN_TEST(test_chirp_off_keeps_the_led);
    RUN_TEST(test_press_before_the_session_is_ignored);
    RUN_TEST(test_noise_sensor_off);
    RUN_TEST(test_live_status);
    return UNITY_END();
}
