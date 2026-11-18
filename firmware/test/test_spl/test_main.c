/* Sound level meter: calibration, A-weighting response, LAeq windows. */
#include <math.h>
#include <unity.h>

#include "umi/core/spl.h"

#define FS 16000u
#define PI 3.14159265358979323846

static umi_spl_t meter;

void setUp(void)
{
    umi_spl_init(&meter, FS, 0.0f);
}

void tearDown(void) {}

/* Feeds `ms` of a tone whose RMS (full scale = 1) reads `dba` at 1 kHz. */
static void feed_tone(double freq_hz, float dba_at_1k, uint32_t ms)
{
    static uint64_t k;
    double peak = sqrt(2.0) * umi_spl_tone_rms(dba_at_1k) * 2147483647.0;
    int32_t pcm[160];
    for (uint32_t done = 0; done < ms * FS / 1000u; done += 160) {
        for (int i = 0; i < 160; i++, k++) {
            pcm[i] = (int32_t)lrint(peak * sin(2.0 * PI * freq_hz * (double)k / FS));
        }
        umi_spl_process(&meter, pcm, 160);
    }
}

static float laeq_1s(void)
{
    float dba;
    TEST_ASSERT_TRUE(umi_spl_laeq_1s(&meter, &dba));
    return dba;
}

static void test_reference_tone_reads_94_dba(void)
{
    /* The datasheet calibration point: 94 dB SPL at 1 kHz is -26 dBFS. */
    feed_tone(1000.0, 94.0f, 3000);
    TEST_ASSERT_FLOAT_WITHIN(0.1f, 94.0f, laeq_1s());
}

static void test_levels_track_the_input(void)
{
    feed_tone(1000.0, 45.0f, 3000);
    TEST_ASSERT_FLOAT_WITHIN(0.1f, 45.0f, laeq_1s());
    feed_tone(1000.0, 80.0f, 1000);
    TEST_ASSERT_FLOAT_WITHIN(0.1f, 80.0f, laeq_1s());
}

/* IEC 61672-1 A-weighting at a few frequencies, against our 16 kHz filter. */
static void assert_weighting(double freq_hz, float a_db, float tolerance_db)
{
    feed_tone(freq_hz, 80.0f, 3000);
    TEST_ASSERT_FLOAT_WITHIN(tolerance_db, 80.0f + a_db, laeq_1s());
}

static void test_a_weighting_low_frequencies(void)
{
    assert_weighting(100.0, -19.1f, 0.2f);
}

static void test_a_weighting_mid_frequencies(void)
{
    assert_weighting(500.0, -3.2f, 0.2f);
}

static void test_a_weighting_2k(void)
{
    assert_weighting(2000.0, 1.2f, 0.2f);
}

static void test_a_weighting_4k_within_class_2(void)
{
    assert_weighting(4000.0, 1.0f, 1.0f);
}

static void test_dc_offset_is_removed(void)
{
    int32_t pcm[160];
    for (int i = 0; i < 160; i++) {
        pcm[i] = 50000000; /* a MEMS mic's DC bias */
    }
    for (int i = 0; i < 300; i++) {
        umi_spl_process(&meter, pcm, 160);
    }
    TEST_ASSERT_TRUE(laeq_1s() < 20.0f);
}

static void test_one_second_needs_ten_blocks(void)
{
    float dba;
    feed_tone(1000.0, 60.0f, 900);
    TEST_ASSERT_FALSE(umi_spl_laeq_1s(&meter, &dba));
    TEST_ASSERT_TRUE(umi_spl_laeq_100ms(&meter, &dba));
    TEST_ASSERT_FLOAT_WITHIN(0.3f, 60.0f, dba);
    feed_tone(1000.0, 60.0f, 100);
    TEST_ASSERT_TRUE(umi_spl_laeq_1s(&meter, &dba));
}

static void test_laeq_is_an_energy_average(void)
{
    /* 0.5 s at 70 dB and 0.5 s at 60 dB average to 10*log10((10^7 + 10^6)/2). */
    feed_tone(1000.0, 70.0f, 2000);
    feed_tone(1000.0, 60.0f, 500);
    float expected = (float)(10.0 * log10((1e7 + 1e6) / 2.0));
    TEST_ASSERT_FLOAT_WITHIN(0.3f, expected, laeq_1s());
}

static void test_reset_restarts_the_average(void)
{
    feed_tone(1000.0, 60.0f, 2000);
    umi_spl_reset(&meter);
    float dba;
    TEST_ASSERT_FALSE(umi_spl_laeq_1s(&meter, &dba));
    TEST_ASSERT_FALSE(umi_spl_laeq_100ms(&meter, &dba));
}

int main(void)
{
    UNITY_BEGIN();
    RUN_TEST(test_reference_tone_reads_94_dba);
    RUN_TEST(test_levels_track_the_input);
    RUN_TEST(test_a_weighting_low_frequencies);
    RUN_TEST(test_a_weighting_mid_frequencies);
    RUN_TEST(test_a_weighting_2k);
    RUN_TEST(test_a_weighting_4k_within_class_2);
    RUN_TEST(test_dc_offset_is_removed);
    RUN_TEST(test_one_second_needs_ten_blocks);
    RUN_TEST(test_laeq_is_an_energy_average);
    RUN_TEST(test_reset_restarts_the_average);
    return UNITY_END();
}
