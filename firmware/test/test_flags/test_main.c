/* Flags (snapshot, keyword rules, signing, undo) and feedback patterns. */
#include <string.h>
#include <unity.h>

#include "fakes.h"
#include "uECC.h"
#include "umi/core/feedback.h"
#include "umi/core/flags.h"
#include "umi/flag_signing.h"
#include "umi/sim/sha256.h"
#include "umi/sim/soft_signer.h"

static const uint8_t KEY[UMI_PRIVATE_KEY_LEN] = {
    0xc9, 0xaf, 0xa9, 0xd8, 0x45, 0xba, 0x75, 0x16, 0x6b, 0x5c, 0x21, 0x57, 0x67, 0xb1, 0xd6, 0x93,
    0x4e, 0x50, 0xc3, 0xdb, 0x36, 0xe8, 0x9b, 0x12, 0x7b, 0x8a, 0x62, 0x2b, 0x12, 0x0f, 0x67, 0x21,
};
static const uint64_t DEVICE = 0x00a1b2c3d4e5f601ull;
static const umi_snapshot_t SNAP = {413950130, 21613528, 501, 1232, 6558};

static umi_soft_signer_t soft;
static umi_flags_t flags;
static fake_indicator_t ind;
static umi_feedback_t fb;

void setUp(void)
{
    TEST_ASSERT_TRUE(umi_soft_signer_init(&soft, KEY));
    umi_flags_init(&flags, umi_soft_signer_hal(&soft), DEVICE);
    umi_flags_begin_session(&flags, 7);
    fake_indicator_init(&ind);
    umi_feedback_init(&fb, fake_buzzer_hal(&ind), fake_led_hal(&ind));
}

void tearDown(void) {}

static umi_flag_t decode(const umi_record_t *rec)
{
    umi_flag_t f;
    TEST_ASSERT_TRUE(umi_flag_decode(rec, &f));
    return f;
}

static bool verifies(const umi_record_t *rec, uint64_t device, uint32_t session)
{
    uint8_t msg[UMI_FLAG_MESSAGE_LEN], digest[UMI_SHA256_LEN];
    umi_flag_signing_message(device, session, rec, msg);
    umi_sha256(msg, sizeof msg, digest);
    return uECC_verify(soft.public_key + 1, digest, sizeof digest, rec->payload + 30,
                       uECC_secp256r1()) == 1;
}

static void test_press_flag_carries_the_snapshot(void)
{
    umi_record_t rec;
    TEST_ASSERT_EQUAL(UMI_FLAG_PRESSED,
                      umi_flags_create(&flags, 16000, UMI_FLAG_SOURCE_PRESS, NULL, &SNAP, &rec));
    umi_flag_t f = decode(&rec);
    TEST_ASSERT_EQUAL_UINT32(16000, f.t_ms);
    TEST_ASSERT_EQUAL_UINT16(0, f.seq);
    TEST_ASSERT_EQUAL_UINT8(UMI_FLAG_SOURCE_PRESS, f.source);
    TEST_ASSERT_EQUAL_UINT8(UMI_HAZARD_KIND_NONE, f.kind);
    TEST_ASSERT_EQUAL_UINT8(0, f.confidence);
    TEST_ASSERT_EQUAL_INT32(SNAP.lat_e7, f.lat_e7);
    TEST_ASSERT_EQUAL_UINT16(SNAP.noise_cdba, f.noise_cdba);
    TEST_ASSERT_EQUAL_UINT8(UMI_SIG_ALG_ECDSA_P256, f.sig_alg);
    TEST_ASSERT_EQUAL_UINT8(64, f.sig_len);
}

static void test_signature_verifies_and_binds_device_and_session(void)
{
    umi_record_t rec;
    umi_flags_create(&flags, 16000, UMI_FLAG_SOURCE_PRESS, NULL, &SNAP, &rec);
    TEST_ASSERT_TRUE(verifies(&rec, DEVICE, 7));
    TEST_ASSERT_FALSE(verifies(&rec, DEVICE + 1, 7));
    TEST_ASSERT_FALSE(verifies(&rec, DEVICE, 8));
    rec.payload[12] ^= 1; /* move the position */
    TEST_ASSERT_FALSE(verifies(&rec, DEVICE, 7));
}

static void test_sequence_counts_per_session(void)
{
    umi_record_t rec;
    umi_flags_create(&flags, 1, UMI_FLAG_SOURCE_PRESS, NULL, &SNAP, &rec);
    umi_flags_create(&flags, 2, UMI_FLAG_SOURCE_PRESS, NULL, &SNAP, &rec);
    TEST_ASSERT_EQUAL_UINT16(1, decode(&rec).seq);
    umi_flags_begin_session(&flags, 8);
    umi_flags_create(&flags, 3, UMI_FLAG_SOURCE_PRESS, NULL, &SNAP, &rec);
    TEST_ASSERT_EQUAL_UINT16(0, decode(&rec).seq);
    TEST_ASSERT_TRUE(verifies(&rec, DEVICE, 8));
}

static void test_understood_keyword_sets_the_kind(void)
{
    umi_keyword_result_t kw = {UMI_HAZARD_KIND_ROADWORKS, 92, UMI_LANG_CA};
    umi_record_t rec;
    TEST_ASSERT_EQUAL(UMI_FLAG_UNDERSTOOD,
                      umi_flags_create(&flags, 5, UMI_FLAG_SOURCE_VOICE, &kw, &SNAP, &rec));
    umi_flag_t f = decode(&rec);
    TEST_ASSERT_EQUAL_UINT8(UMI_FLAG_SOURCE_VOICE, f.source);
    TEST_ASSERT_EQUAL_UINT8(UMI_HAZARD_KIND_ROADWORKS, f.kind);
    TEST_ASSERT_EQUAL_UINT8(92, f.confidence);
    TEST_ASSERT_EQUAL_UINT8(UMI_LANG_CA, f.lang);
}

static void test_low_confidence_keeps_the_flag_without_kind(void)
{
    umi_keyword_result_t kw = {UMI_HAZARD_KIND_POTHOLE, UMI_BUTTON_KEYWORD_MIN_CONFIDENCE - 1,
                               UMI_LANG_ES};
    umi_record_t rec;
    TEST_ASSERT_EQUAL(UMI_FLAG_NOT_UNDERSTOOD,
                      umi_flags_create(&flags, 5, UMI_FLAG_SOURCE_VOICE, &kw, &SNAP, &rec));
    umi_flag_t f = decode(&rec);
    TEST_ASSERT_EQUAL_UINT8(UMI_HAZARD_KIND_NONE, f.kind);
    TEST_ASSERT_EQUAL_UINT8(UMI_BUTTON_KEYWORD_MIN_CONFIDENCE - 1, f.confidence);
    TEST_ASSERT_EQUAL_UINT8(UMI_LANG_ES, f.lang);
}

static void test_threshold_confidence_is_accepted(void)
{
    umi_keyword_result_t kw = {UMI_HAZARD_KIND_DANGER, UMI_BUTTON_KEYWORD_MIN_CONFIDENCE, 1};
    TEST_ASSERT_TRUE(umi_keyword_accepted(&kw));
    kw.kind = UMI_HAZARD_KIND_NONE;
    TEST_ASSERT_FALSE(umi_keyword_accepted(&kw));
    kw.kind = UMI_HAZARD_KIND_DANGER + 1;
    TEST_ASSERT_FALSE(umi_keyword_accepted(&kw));
    TEST_ASSERT_FALSE(umi_keyword_accepted(NULL));
}

static void test_silent_window_is_not_understood(void)
{
    umi_record_t rec;
    TEST_ASSERT_EQUAL(UMI_FLAG_NOT_UNDERSTOOD,
                      umi_flags_create(&flags, 5, UMI_FLAG_SOURCE_VOICE, NULL, &SNAP, &rec));
    umi_flag_t f = decode(&rec);
    TEST_ASSERT_EQUAL_UINT8(0, f.kind);
    TEST_ASSERT_EQUAL_UINT8(0, f.confidence);
    TEST_ASSERT_EQUAL_UINT8(UMI_LANG_NONE, f.lang);
}

static void test_without_signer_flags_are_unsigned(void)
{
    umi_flags_init(&flags, (umi_hal_signer_t){.alg = UMI_SIG_ALG_NONE}, DEVICE);
    umi_flags_begin_session(&flags, 7);
    umi_record_t rec;
    umi_flags_create(&flags, 5, UMI_FLAG_SOURCE_PRESS, NULL, &SNAP, &rec);
    umi_flag_t f = decode(&rec);
    TEST_ASSERT_EQUAL_UINT8(UMI_SIG_ALG_NONE, f.sig_alg);
    TEST_ASSERT_EQUAL_UINT8(0, f.sig_len);
    uint8_t zeros[64] = {0};
    TEST_ASSERT_EQUAL_MEMORY(zeros, f.signature, 64);
}

static bool failing_sign(void *ctx, const uint8_t *msg, size_t len, uint8_t sig[64])
{
    (void)ctx, (void)msg, (void)len;
    memset(sig, 0xAB, 64);
    return false;
}

static void test_signing_failure_keeps_an_unsigned_flag(void)
{
    umi_flags_init(&flags, (umi_hal_signer_t){.alg = UMI_SIG_ALG_ECDSA_P256, .sign = failing_sign},
                   DEVICE);
    umi_record_t rec;
    umi_flags_create(&flags, 5, UMI_FLAG_SOURCE_PRESS, NULL, &SNAP, &rec);
    umi_flag_t f = decode(&rec);
    TEST_ASSERT_EQUAL_UINT8(UMI_SIG_ALG_NONE, f.sig_alg);
    TEST_ASSERT_EQUAL_UINT8(0, f.signature[0]);
    TEST_ASSERT_EQUAL_UINT32(1, flags.signing_failures);
}

static void test_undo_cancels_the_last_flag_once(void)
{
    umi_record_t rec;
    TEST_ASSERT_FALSE(umi_flags_undo(&flags, 1, &rec));
    umi_flags_create(&flags, 1, UMI_FLAG_SOURCE_PRESS, NULL, &SNAP, &rec);
    umi_flags_create(&flags, 2, UMI_FLAG_SOURCE_PRESS, NULL, &SNAP, &rec);
    TEST_ASSERT_TRUE(umi_flags_undo(&flags, 3, &rec));
    umi_flag_undo_t undo;
    TEST_ASSERT_TRUE(umi_flag_undo_decode(&rec, &undo));
    TEST_ASSERT_EQUAL_UINT32(3, undo.t_ms);
    TEST_ASSERT_EQUAL_UINT16(1, undo.seq);
    TEST_ASSERT_FALSE(umi_flags_undo(&flags, 4, &rec));
}

/* ---------------------------------------------------------------- feedback */

static void play_to_end(umi_feedback_pattern_t pattern, bool muted)
{
    umi_feedback_play(&fb, pattern, muted, 1000);
    for (uint32_t t = 1000; t < 3000; t += 5) {
        umi_feedback_tick(&fb, t);
    }
}

static void test_flag_is_one_high_chirp_with_orange(void)
{
    umi_feedback_play(&fb, UMI_FEEDBACK_FLAG, false, 1000);
    TEST_ASSERT_EQUAL(UMI_LED_ORANGE, ind.led);
    play_to_end(UMI_FEEDBACK_FLAG, false);
    TEST_ASSERT_EQUAL_size_t(1, ind.tone_count);
    TEST_ASSERT_EQUAL_UINT16(UMI_FEEDBACK_CHIRP_HIGH_HZ, ind.tones[0]);
    TEST_ASSERT_EQUAL(UMI_LED_OFF, ind.led);
    TEST_ASSERT_EQUAL_UINT16(0, ind.tone_hz);
    TEST_ASSERT_FALSE(umi_feedback_playing(&fb));
}

static void test_patterns_differ_by_chirps_not_colour(void)
{
    struct {
        umi_feedback_pattern_t pattern;
        size_t chirps;
        uint16_t first, second;
    } cases[] = {
        {UMI_FEEDBACK_KEYWORD_UNDERSTOOD, 2, UMI_FEEDBACK_CHIRP_LOW_HZ, UMI_FEEDBACK_CHIRP_HIGH_HZ},
        {UMI_FEEDBACK_KEYWORD_NOT_UNDERSTOOD, 1, UMI_FEEDBACK_CHIRP_LOW_HZ, 0},
        {UMI_FEEDBACK_UNDO, 2, UMI_FEEDBACK_CHIRP_HIGH_HZ, UMI_FEEDBACK_CHIRP_HIGH_HZ},
        {UMI_FEEDBACK_WARN_AHEAD, 2, UMI_FEEDBACK_CHIRP_LOW_HZ, UMI_FEEDBACK_CHIRP_LOW_HZ},
    };
    for (size_t i = 0; i < sizeof cases / sizeof cases[0]; i++) {
        fake_indicator_init(&ind);
        play_to_end(cases[i].pattern, false);
        TEST_ASSERT_EQUAL_size_t(cases[i].chirps, ind.tone_count);
        TEST_ASSERT_EQUAL_UINT16(cases[i].first, ind.tones[0]);
        if (cases[i].chirps == 2) {
            TEST_ASSERT_EQUAL_UINT16(cases[i].second, ind.tones[1]);
        }
    }
}

static void test_chirps_are_separated_by_the_gap(void)
{
    umi_feedback_play(&fb, UMI_FEEDBACK_UNDO, false, 1000);
    umi_feedback_tick(&fb, 1000 + UMI_FEEDBACK_CHIRP_MS - 1);
    TEST_ASSERT_EQUAL_UINT16(UMI_FEEDBACK_CHIRP_HIGH_HZ, ind.tone_hz);
    umi_feedback_tick(&fb, 1000 + UMI_FEEDBACK_CHIRP_MS);
    TEST_ASSERT_EQUAL_UINT16(0, ind.tone_hz);
    umi_feedback_tick(&fb, 1000 + UMI_FEEDBACK_CHIRP_MS + UMI_FEEDBACK_CHIRP_GAP_MS);
    TEST_ASSERT_EQUAL_UINT16(UMI_FEEDBACK_CHIRP_HIGH_HZ, ind.tone_hz);
}

static void test_muted_keeps_the_led(void)
{
    umi_feedback_play(&fb, UMI_FEEDBACK_FLAG, true, 1000);
    TEST_ASSERT_EQUAL(UMI_LED_ORANGE, ind.led);
    TEST_ASSERT_EQUAL_UINT16(0, ind.tone_hz);
    TEST_ASSERT_EQUAL_size_t(0, ind.tone_count);
}

static void test_listening_pulses_until_stopped(void)
{
    umi_feedback_play(&fb, UMI_FEEDBACK_LISTENING, true, 0);
    for (uint32_t t = 0; t <= 4000; t += 10) {
        umi_feedback_tick(&fb, t);
    }
    TEST_ASSERT_TRUE(umi_feedback_playing(&fb));
    TEST_ASSERT_TRUE(ind.led_changes >= 15);
    umi_feedback_stop(&fb);
    TEST_ASSERT_EQUAL(UMI_LED_OFF, ind.led);
    TEST_ASSERT_FALSE(umi_feedback_playing(&fb));
}

static void test_a_late_tick_does_not_stretch_a_pattern(void)
{
    umi_feedback_play(&fb, UMI_FEEDBACK_UNDO, false, 0);
    umi_feedback_tick(&fb, 1000); /* the task was busy for a second */
    TEST_ASSERT_FALSE(umi_feedback_playing(&fb));
}

int main(void)
{
    UNITY_BEGIN();
    RUN_TEST(test_press_flag_carries_the_snapshot);
    RUN_TEST(test_signature_verifies_and_binds_device_and_session);
    RUN_TEST(test_sequence_counts_per_session);
    RUN_TEST(test_understood_keyword_sets_the_kind);
    RUN_TEST(test_low_confidence_keeps_the_flag_without_kind);
    RUN_TEST(test_threshold_confidence_is_accepted);
    RUN_TEST(test_silent_window_is_not_understood);
    RUN_TEST(test_without_signer_flags_are_unsigned);
    RUN_TEST(test_signing_failure_keeps_an_unsigned_flag);
    RUN_TEST(test_undo_cancels_the_last_flag_once);
    RUN_TEST(test_flag_is_one_high_chirp_with_orange);
    RUN_TEST(test_patterns_differ_by_chirps_not_colour);
    RUN_TEST(test_chirps_are_separated_by_the_gap);
    RUN_TEST(test_muted_keeps_the_led);
    RUN_TEST(test_listening_pulses_until_stopped);
    RUN_TEST(test_a_late_tick_does_not_stretch_a_pattern);
    return UNITY_END();
}
