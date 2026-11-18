/* IMU pipeline: vibration RMS, hard-brake and pothole detectors ([detection]). */
#include <math.h>
#include <unity.h>

#include "umi/core/brake.h"
#include "umi/core/pothole.h"
#include "umi/core/vibration.h"
#include "umi/protocol_gen.h"

#define G 9.80665f
#define DT_MS 10u
#define PI_F 3.14159265f

static umi_vibration_t vib;
static umi_brake_t brake;
static umi_pothole_t pothole;

void setUp(void)
{
    umi_vibration_init(&vib);
    umi_brake_init(&brake);
    umi_pothole_init(&pothole);
}

void tearDown(void) {}

static umi_imu_sample_t sample(uint32_t t_ms, float ax, float ay, float az)
{
    return (umi_imu_sample_t){.t_ms = t_ms, .ax = ax, .ay = ay, .az = az};
}

static umi_gnss_fix_t fix(uint32_t t_ms, uint16_t speed_cms)
{
    return (umi_gnss_fix_t){.t_ms = t_ms, .fix = UMI_FIX_THREE_D, .speed_cms = speed_cms};
}

/* ---------------------------------------------------------------- vibration */

static void test_vibration_rms_of_a_vertical_sine(void)
{
    /* 2 m/s² amplitude at 10 Hz: RMS = 2 / sqrt(2). */
    for (uint32_t i = 0; i < 1000; i++) {
        float v = 2.0f * sinf(2.0f * PI_F * 10.0f * (float)i / 100.0f);
        umi_imu_sample_t s = sample(i * DT_MS, 0.0f, 0.0f, G + v);
        umi_vibration_update(&vib, &s);
    }
    TEST_ASSERT_TRUE(umi_vibration_ready(&vib));
    TEST_ASSERT_FLOAT_WITHIN(0.03f, 1.4142f, umi_vibration_rms(&vib));
}

static void test_vibration_follows_gravity_on_a_tilted_mount(void)
{
    /* Mounted at 30°, shaken along true vertical: the same RMS as level. */
    float tilt = 30.0f * PI_F / 180.0f;
    for (uint32_t i = 0; i < 1500; i++) {
        float v = 2.0f * sinf(2.0f * PI_F * 10.0f * (float)i / 100.0f);
        umi_imu_sample_t s = sample(i * DT_MS, (G + v) * sinf(tilt), 0.0f, (G + v) * cosf(tilt));
        umi_vibration_update(&vib, &s);
    }
    TEST_ASSERT_FLOAT_WITHIN(0.03f, 1.4142f, umi_vibration_rms(&vib));
}

static void test_vibration_at_rest_is_zero(void)
{
    for (uint32_t i = 0; i < 300; i++) {
        umi_imu_sample_t s = sample(i * DT_MS, 0.5f, 0.0f, G);
        umi_vibration_update(&vib, &s);
    }
    TEST_ASSERT_FLOAT_WITHIN(0.001f, 0.0f, umi_vibration_rms(&vib));
}

/* ---------------------------------------------------------------- brake */

/* Rides at constant speed, then decelerates for decel_ms; returns the time
 * after the brake. The x axis carries a 0.5 m/s² mounting offset. */
static uint32_t ride_with_brake(uint32_t brake_at_ms, uint32_t decel_ms, float decel)
{
    uint32_t t = 0;
    for (; t < brake_at_ms + decel_ms + 500; t += DT_MS) {
        bool braking = t >= brake_at_ms && t < brake_at_ms + decel_ms;
        umi_imu_sample_t s = sample(t, 0.5f - (braking ? decel : 0.0f), 0.0f, G);
        umi_brake_on_imu(&brake, &s);
    }
    return t;
}

static void test_sustained_deceleration_is_a_hard_brake(void)
{
    umi_brake_on_fix(&brake, &(umi_gnss_fix_t){.t_ms = 4900, .fix = 3, .speed_cms = 500});
    uint32_t t = ride_with_brake(5000, 600, 4.0f);
    umi_detection_t d;
    TEST_ASSERT_FALSE(umi_brake_poll(&brake, t, &d)); /* waits for the next fix */
    umi_gnss_fix_t after = fix(6000, 260);
    umi_brake_on_fix(&brake, &after);
    TEST_ASSERT_TRUE(umi_brake_poll(&brake, t, &d));
    TEST_ASSERT_EQUAL_UINT8(UMI_EVENT_KIND_HARD_BRAKE, d.kind);
    TEST_ASSERT_UINT32_WITHIN(60, 5000, d.t_ms);
    TEST_ASSERT_UINT32_WITHIN(60, 600, d.duration_ms);
    TEST_ASSERT_FLOAT_WITHIN(0.3f, 4.0f, d.value_mps2);
    TEST_ASSERT_FLOAT_WITHIN(0.3f, 4.0f, d.peak_mps2);
}

static void test_short_deceleration_is_not_a_brake(void)
{
    uint32_t t = ride_with_brake(5000, UMI_DETECTION_HARD_BRAKE_MIN_MS - 100, 5.0f);
    umi_detection_t d;
    TEST_ASSERT_FALSE(umi_brake_poll(&brake, t + 5000, &d));
    uint32_t since;
    TEST_ASSERT_FALSE(umi_brake_pending_since(&brake, &since));
}

static void test_gentle_deceleration_is_not_a_brake(void)
{
    uint32_t t = ride_with_brake(5000, 1500, UMI_DETECTION_HARD_BRAKE_MPS2 - 0.5f);
    umi_detection_t d;
    TEST_ASSERT_FALSE(umi_brake_poll(&brake, t + 5000, &d));
}

static void test_gnss_rejects_a_brake_without_speed_loss(void)
{
    umi_gnss_fix_t before = fix(4900, 500), after = fix(6000, 495);
    umi_brake_on_fix(&brake, &before);
    uint32_t t = ride_with_brake(5000, 600, 4.0f);
    umi_brake_on_fix(&brake, &after);
    umi_detection_t d;
    TEST_ASSERT_FALSE(umi_brake_poll(&brake, t, &d));
    TEST_ASSERT_EQUAL_UINT32(1, brake.rejected);
}

static void test_without_gnss_the_imu_decides_after_a_wait(void)
{
    uint32_t t = ride_with_brake(5000, 600, 4.0f);
    umi_detection_t d;
    TEST_ASSERT_FALSE(umi_brake_poll(&brake, t, &d));
    uint32_t since;
    TEST_ASSERT_TRUE(umi_brake_pending_since(&brake, &since));
    TEST_ASSERT_UINT32_WITHIN(60, 5000, since);
    TEST_ASSERT_TRUE(umi_brake_poll(&brake, 5600 + 2000, &d));
}

static void test_refractory_period_after_a_brake(void)
{
    uint32_t t = 0;
    /* Two brakes 1 s apart: the second falls in the refractory period. */
    for (; t < 9000; t += DT_MS) {
        bool braking = (t >= 5000 && t < 5500) || (t >= 6500 && t < 7000);
        umi_imu_sample_t s = sample(t, braking ? -4.0f : 0.0f, 0.0f, G);
        umi_brake_on_imu(&brake, &s);
        umi_detection_t d;
        umi_brake_poll(&brake, t, &d);
    }
    umi_detection_t d;
    TEST_ASSERT_FALSE(umi_brake_poll(&brake, t + 5000, &d));
    TEST_ASSERT_EQUAL(UMI_BRAKE_IDLE, brake.phase);
}

static void test_long_brake_is_not_absorbed_by_the_baseline(void)
{
    uint32_t t = ride_with_brake(5000, 3000, 3.6f);
    umi_detection_t d;
    TEST_ASSERT_TRUE(umi_brake_poll(&brake, t + 2000, &d));
    TEST_ASSERT_UINT32_WITHIN(100, 3000, d.duration_ms);
}

/* ---------------------------------------------------------------- pothole */

/* Feeds one second of road at `rough` m/s² plus an optional shock at shock_ms. */
static bool run_road(uint32_t until_ms, uint32_t shock_ms, float amplitude, float decay_s,
                     umi_detection_t *out)
{
    bool found = false;
    for (uint32_t t = 0; t < until_ms; t += DT_MS) {
        float v = 0.3f * sinf((float)t * 0.37f);
        if (amplitude > 0.0f && t >= shock_ms) {
            float dt = (float)(t - shock_ms) / 1000.0f;
            v += amplitude * expf(-dt / decay_s) * cosf(2.0f * PI_F * 12.0f * dt);
        }
        umi_imu_sample_t s = sample(t, 0.0f, 0.0f, G + v);
        float vertical = umi_vibration_update(&vib, &s);
        umi_pothole_update(&pothole, t, vertical, umi_vibration_rms(&vib));
        if (umi_pothole_poll(&pothole, out)) {
            found = true;
        }
    }
    return found;
}

static void test_shock_with_energy_is_a_pothole(void)
{
    umi_detection_t d;
    TEST_ASSERT_TRUE(run_road(5000, 3000, 20.0f, 0.2f, &d));
    TEST_ASSERT_EQUAL_UINT8(UMI_EVENT_KIND_POTHOLE, d.kind);
    TEST_ASSERT_UINT32_WITHIN(20, 3000, d.t_ms);
    TEST_ASSERT_TRUE(d.peak_mps2 >= UMI_DETECTION_POTHOLE_PEAK_MPS2);
    TEST_ASSERT_TRUE(d.value_mps2 >= UMI_DETECTION_POTHOLE_RMS_MPS2);
    TEST_ASSERT_TRUE(d.duration_ms > 0 && d.duration_ms < 1000);
}

static void test_lone_spike_is_not_a_pothole(void)
{
    /* A knock on the Clip: a high peak gone in 20 ms. */
    umi_detection_t d;
    TEST_ASSERT_FALSE(run_road(5000, 3000, 25.0f, 0.01f, &d));
}

static void test_rough_road_without_impact_is_not_a_pothole(void)
{
    umi_detection_t d;
    TEST_ASSERT_FALSE(run_road(5000, 0, 0.0f, 0.0f, &d));
}

static void test_pothole_refractory(void)
{
    umi_detection_t d;
    int found = 0;
    for (uint32_t t = 0; t < 8000; t += DT_MS) {
        float v = 0.0f;
        for (uint32_t shock = 2000; shock <= 3000; shock += 1000) {
            if (t >= shock) {
                float dt = (float)(t - shock) / 1000.0f;
                v += 20.0f * expf(-dt / 0.2f) * cosf(2.0f * PI_F * 12.0f * dt);
            }
        }
        umi_imu_sample_t s = sample(t, 0.0f, 0.0f, G + v);
        float vertical = umi_vibration_update(&vib, &s);
        umi_pothole_update(&pothole, t, vertical, umi_vibration_rms(&vib));
        found += umi_pothole_poll(&pothole, &d);
    }
    TEST_ASSERT_EQUAL_INT(1, found);
}

int main(void)
{
    UNITY_BEGIN();
    RUN_TEST(test_vibration_rms_of_a_vertical_sine);
    RUN_TEST(test_vibration_follows_gravity_on_a_tilted_mount);
    RUN_TEST(test_vibration_at_rest_is_zero);
    RUN_TEST(test_sustained_deceleration_is_a_hard_brake);
    RUN_TEST(test_short_deceleration_is_not_a_brake);
    RUN_TEST(test_gentle_deceleration_is_not_a_brake);
    RUN_TEST(test_gnss_rejects_a_brake_without_speed_loss);
    RUN_TEST(test_without_gnss_the_imu_decides_after_a_wait);
    RUN_TEST(test_refractory_period_after_a_brake);
    RUN_TEST(test_long_brake_is_not_absorbed_by_the_baseline);
    RUN_TEST(test_shock_with_energy_is_a_pothole);
    RUN_TEST(test_lone_spike_is_not_a_pothole);
    RUN_TEST(test_rough_road_without_impact_is_not_a_pothole);
    RUN_TEST(test_pothole_refractory);
    return UNITY_END();
}
