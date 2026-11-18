/* Session recorder: motion start, auto-pause, auto-stop, periodic records and
 * ordering ([detection], [rates]). Also the AIR aggregation and reorder queue. */
#include <math.h>
#include <unity.h>

#include "fakes.h"
#include "umi/core/air.h"
#include "umi/core/record_queue.h"
#include "umi/core/recorder.h"

#define BASE_UNIX_MS 1794988320000LL /* 2026-11-18T07:52:00Z */
#define CRUISE_CMS 500
#define STEP_MS 10u

static const umi_identity_t ID = {
    .device_id = 0x00a1b2c3d4e5f601ull,
    .fw_version = {0, 1, 0},
    .header_flags = UMI_HEADER_FLAG_SIMULATED,
    .activity = UMI_ACTIVITY_RIDE,
};

static fake_storage_t storage;
static umi_recorder_t rec;
static umi_sensor_state_t sensors;
static fake_log_t log_;
static uint32_t now;
static int started, paused, resumed, stopped;

void setUp(void)
{
    fake_storage_init(&storage, 100);
    umi_recorder_init(&rec, &ID, fake_storage_hal(&storage));
    sensors = (umi_sensor_state_t){.vib_mms2 = 800, .noise_cdba = 6500};
    now = 0;
    started = paused = resumed = stopped = 0;
}

void tearDown(void) {}

/* Runs to `until` with a 1 Hz GNSS at `speed_cms` (no GNSS if speed < 0). */
static void drive(uint32_t until, int speed_cms)
{
    for (; now < until; now += STEP_MS) {
        if (speed_cms >= 0 && now % 1000 == 0) {
            sensors.has_fix = true;
            sensors.fix = (umi_gnss_fix_t){
                .t_ms = now, .fix = UMI_FIX_THREE_D, .lat_e7 = 413950000 + (int32_t)now,
                .lon_e7 = 21610000, .speed_cms = (uint16_t)speed_cms, .heading_cdeg = 13460,
                .hdop_d = 8, .sats = 12, .has_utc = true, .unix_ms = BASE_UNIX_MS + now};
            umi_recorder_on_fix(&rec, &sensors.fix);
        }
        if (now % 1000 == 0) {
            umi_recorder_add_pm(&rec, &(umi_pm_reading_t){now, 9, 14, 20});
        }
        switch (umi_recorder_tick(&rec, now, &sensors)) {
        case UMI_RECORDER_STARTED:
            started++;
            break;
        case UMI_RECORDER_PAUSED_NOW:
            paused++;
            break;
        case UMI_RECORDER_RESUMED:
            resumed++;
            break;
        case UMI_RECORDER_STOPPED:
            stopped++;
            break;
        case UMI_RECORDER_NO_CHANGE:
            break;
        }
        umi_recorder_flush(&rec, now);
    }
}

static void read_log(void)
{
    fake_log_read(&log_, storage.data, storage.len);
}

static void assert_ordered(void)
{
    for (size_t i = 1; i < log_.count; i++) {
        TEST_ASSERT_TRUE(umi_record_t_ms(&log_.records[i - 1]) <= umi_record_t_ms(&log_.records[i]));
    }
}

static void test_starts_after_five_seconds_of_motion(void)
{
    drive(10000, 0);
    TEST_ASSERT_EQUAL_INT(0, started);
    drive(14990, CRUISE_CMS);
    TEST_ASSERT_EQUAL_INT(0, started);
    drive(15010, CRUISE_CMS);
    TEST_ASSERT_EQUAL_INT(1, started);
    TEST_ASSERT_EQUAL_UINT32(100, rec.session_id);
    TEST_ASSERT_EQUAL_UINT32(10000 + UMI_DETECTION_MOTION_START_S * 1000, rec.start_ms);
}

static void test_slow_walk_does_not_start(void)
{
    drive(60000, 150); /* 5.4 km/h, under motion_start_speed_kmh */
    TEST_ASSERT_EQUAL_INT(0, started);
}

static void test_session_records_follow_the_schedule(void)
{
    drive(5000 + 125000 + STEP_MS, CRUISE_CMS); /* start at 5 s, then 125 s of riding */
    umi_recorder_stop(&rec, now);
    read_log();
    TEST_ASSERT_EQUAL(UMI_LOG_END, log_.result);
    assert_ordered();

    umi_state_t state;
    TEST_ASSERT_TRUE(umi_state_decode(&log_.records[0], &state));
    TEST_ASSERT_EQUAL_UINT32(0, state.t_ms);
    TEST_ASSERT_EQUAL_UINT8(UMI_RECORDER_STATE_RECORDING, state.state);

    TEST_ASSERT_EQUAL_size_t(125, fake_log_count(&log_, UMI_RECORD_TYPE_SAMPLE));
    TEST_ASSERT_EQUAL_size_t(12, fake_log_count(&log_, UMI_RECORD_TYPE_AIR));
    TEST_ASSERT_EQUAL_size_t(3, fake_log_count(&log_, UMI_RECORD_TYPE_STATUS)); /* 0, 60, 120 s */
    TEST_ASSERT_EQUAL_size_t(1, fake_log_count(&log_, UMI_RECORD_TYPE_TIME_SYNC));

    umi_sample_t s;
    TEST_ASSERT_TRUE(umi_sample_decode(fake_log_find(&log_, UMI_RECORD_TYPE_SAMPLE, 0), &s));
    TEST_ASSERT_EQUAL_UINT32(1000, s.t_ms);
    TEST_ASSERT_EQUAL_UINT8(UMI_FIX_THREE_D, s.fix);
    TEST_ASSERT_EQUAL_UINT16(CRUISE_CMS, s.speed_cms);
    TEST_ASSERT_EQUAL_UINT16(800, s.vib_mms2);
    TEST_ASSERT_EQUAL_UINT16(6500, s.noise_cdba);
    TEST_ASSERT_EQUAL_UINT8(12, s.sats);
}

static void test_time_sync_maps_session_time_to_utc(void)
{
    drive(20000, CRUISE_CMS);
    umi_recorder_stop(&rec, now);
    read_log();
    umi_time_sync_t sync;
    TEST_ASSERT_TRUE(umi_time_sync_decode(fake_log_find(&log_, UMI_RECORD_TYPE_TIME_SYNC, 0), &sync));
    /* First fix after the start (at 5 s) is the one at 6 s. */
    TEST_ASSERT_EQUAL_UINT32(1000, sync.t_ms);
    TEST_ASSERT_EQUAL_INT64(BASE_UNIX_MS + 6000, sync.unix_ms);
}

static void test_still_pauses_then_resumes(void)
{
    drive(20000, CRUISE_CMS);
    drive(20000 + UMI_DETECTION_AUTO_PAUSE_S * 1000 - 100, 0);
    TEST_ASSERT_EQUAL_INT(0, paused);
    drive(20000 + UMI_DETECTION_AUTO_PAUSE_S * 1000 + 100, 0);
    TEST_ASSERT_EQUAL_INT(1, paused);
    TEST_ASSERT_EQUAL(UMI_RECORDER_PAUSED, rec.phase);
    drive(70000, 0);
    drive(80000, CRUISE_CMS);
    TEST_ASSERT_EQUAL_INT(1, resumed);
    umi_recorder_stop(&rec, now);
    read_log();
    assert_ordered();
    TEST_ASSERT_EQUAL_size_t(3, fake_log_count(&log_, UMI_RECORD_TYPE_STATE));
    /* No SAMPLE while paused: from 50 s to 70 s of device time. */
    for (size_t i = 0; i < log_.count; i++) {
        if (log_.records[i].type == UMI_RECORD_TYPE_SAMPLE) {
            uint32_t device_t = umi_record_t_ms(&log_.records[i]) + 5000;
            TEST_ASSERT_FALSE(device_t > 50100 && device_t < 70000);
        }
    }
}

static void test_still_long_enough_stops_with_end(void)
{
    drive(20000, CRUISE_CMS);
    drive(20000 + UMI_DETECTION_AUTO_STOP_S * 1000 + 100, 0);
    TEST_ASSERT_EQUAL_INT(1, stopped);
    TEST_ASSERT_EQUAL(UMI_RECORDER_IDLE, rec.phase);
    TEST_ASSERT_EQUAL_UINT32(1, storage.closed);
    read_log();
    TEST_ASSERT_EQUAL(UMI_LOG_END, log_.result);
    assert_ordered();
}

static void test_next_session_gets_a_new_id(void)
{
    drive(20000, CRUISE_CMS);
    drive(20000 + UMI_DETECTION_AUTO_STOP_S * 1000 + 100, 0);
    drive(now + 10000, CRUISE_CMS);
    TEST_ASSERT_EQUAL_INT(2, started);
    TEST_ASSERT_EQUAL_UINT32(101, rec.session_id);
    umi_recorder_stop(&rec, now);
    read_log();
    TEST_ASSERT_EQUAL_UINT32(101, log_.header.session_id);
}

static void test_quiet_clip_without_gnss_is_still(void)
{
    drive(20000, CRUISE_CMS);
    sensors.has_fix = false;
    sensors.vib_mms2 = 50;
    drive(20000 + UMI_DETECTION_AUTO_PAUSE_S * 1000 + 100, -1);
    TEST_ASSERT_EQUAL_INT(1, paused);
}

static void test_shaking_clip_without_gnss_keeps_recording(void)
{
    /* A tunnel: no fix, but the road still shakes the Clip. */
    drive(20000, CRUISE_CMS);
    sensors.has_fix = false;
    sensors.vib_mms2 = 1500;
    drive(20000 + UMI_DETECTION_AUTO_STOP_S * 1000, -1);
    TEST_ASSERT_EQUAL_INT(0, paused);
    umi_recorder_stop(&rec, now);
    read_log();
    umi_sample_t s;
    TEST_ASSERT_TRUE(umi_sample_decode(fake_log_find(&log_, UMI_RECORD_TYPE_SAMPLE, 30), &s));
    TEST_ASSERT_EQUAL_UINT8(UMI_FIX_NONE, s.fix);
    TEST_ASSERT_EQUAL_INT32(0, s.lat_e7);
    TEST_ASSERT_EQUAL_UINT16(0, s.speed_cms);
}

/* Like drive(), but flushing only up to a producer's pending time. */
static void drive_held(uint32_t until, uint32_t pending_since)
{
    for (; now < until; now += STEP_MS) {
        umi_recorder_tick(&rec, now, &sensors);
        umi_recorder_flush(&rec, pending_since);
    }
}

static void test_late_records_are_written_in_order(void)
{
    drive(10000, CRUISE_CMS);
    /* A press at 10 s is decided 2 s later; its producer holds the horizon. */
    drive_held(12000, 10000);
    umi_record_t flag;
    umi_flag_encode(&(umi_flag_t){.t_ms = umi_recorder_session_ms(&rec, 10000)}, &flag);
    umi_recorder_push(&rec, &flag);
    umi_recorder_stop(&rec, now);
    read_log();
    TEST_ASSERT_EQUAL_size_t(1, fake_log_count(&log_, UMI_RECORD_TYPE_FLAG));
    TEST_ASSERT_EQUAL_UINT32(0, rec.dropped);
    assert_ordered();
}

static void test_unannounced_late_record_is_dropped_not_misordered(void)
{
    drive(12000, CRUISE_CMS);
    umi_record_t flag;
    umi_flag_encode(&(umi_flag_t){.t_ms = umi_recorder_session_ms(&rec, 10000)}, &flag);
    umi_recorder_push(&rec, &flag);
    umi_recorder_stop(&rec, now);
    read_log();
    TEST_ASSERT_EQUAL_size_t(0, fake_log_count(&log_, UMI_RECORD_TYPE_FLAG));
    TEST_ASSERT_EQUAL_UINT32(1, rec.dropped);
    TEST_ASSERT_EQUAL(UMI_LOG_END, log_.result);
}

static void test_flush_holds_records_after_the_horizon(void)
{
    drive(10000, CRUISE_CMS); /* session started at 5 s */
    size_t written = storage.len;
    umi_record_t state;
    umi_state_encode(&(umi_state_t){.t_ms = 9000, .state = 2}, &state);
    umi_recorder_push(&rec, &state);
    umi_recorder_flush(&rec, 5000 + 8999);
    TEST_ASSERT_EQUAL_size_t(written, storage.len);
    umi_recorder_flush(&rec, 5000 + 9000);
    TEST_ASSERT_TRUE(storage.len > written);
}

static void test_storage_refusal_keeps_idle(void)
{
    storage.fail_writes = true;
    drive(20000, CRUISE_CMS);
    TEST_ASSERT_EQUAL_INT(0, started);
    TEST_ASSERT_EQUAL(UMI_RECORDER_IDLE, rec.phase);
}

static void test_status_flags(void)
{
    sensors.has_battery = true;
    sensors.battery = (umi_battery_reading_t){.mv = 3500, .pct = 9, .charging = true};
    storage.free_kib = 500;
    drive(7000, CRUISE_CMS);
    umi_recorder_stop(&rec, now);
    read_log();
    umi_status_t st;
    TEST_ASSERT_TRUE(umi_status_decode(fake_log_find(&log_, UMI_RECORD_TYPE_STATUS, 0), &st));
    TEST_ASSERT_EQUAL_UINT8(UMI_STATUS_FLAG_CHARGING | UMI_STATUS_FLAG_LOW_BATTERY |
                                UMI_STATUS_FLAG_STORAGE_LOW,
                            st.flags);
    TEST_ASSERT_EQUAL_UINT16(3500, st.battery_mv);
    TEST_ASSERT_EQUAL_UINT16(500, st.free_kib);
    TEST_ASSERT_EQUAL_INT16(INT16_MIN, st.board_temp_cc);
}

/* ---------------------------------------------------------------- air */

static void test_air_averages_and_corrects_pm25_only(void)
{
    umi_air_acc_t acc;
    umi_air_reset(&acc);
    umi_air_add(&acc, &(umi_pm_reading_t){0, 10, 20, 30});
    umi_air_add(&acc, &(umi_pm_reading_t){1000, 12, 22, 34});
    umi_env_reading_t env = {0, 19.5f, 61.0f};
    umi_air_t air;
    umi_air_make(&acc, &env, 10000, &air);
    TEST_ASSERT_EQUAL_UINT16(110, air.pm1_dug);
    TEST_ASSERT_EQUAL_UINT16(320, air.pm10_dug);
    TEST_ASSERT_EQUAL_UINT16((uint16_t)lroundf(umi_pm25_dry(21.0f, 61.0f) * 10.0f), air.pm25_dug);
    TEST_ASSERT_TRUE(air.pm25_dug < 210);
    TEST_ASSERT_EQUAL_INT16(1950, air.temp_cc);
    TEST_ASSERT_EQUAL_UINT16(610, air.rh_dpct);
}

static void test_air_without_readings_is_not_available(void)
{
    umi_air_acc_t acc;
    umi_air_reset(&acc);
    umi_air_t air;
    umi_air_make(&acc, NULL, 10000, &air);
    TEST_ASSERT_EQUAL_UINT16(UMI_FORMAT_NOT_AVAILABLE_U16, air.pm25_dug);
    TEST_ASSERT_EQUAL_UINT16(UMI_FORMAT_NOT_AVAILABLE_U16, air.rh_dpct);
    TEST_ASSERT_EQUAL_INT16(INT16_MIN, air.temp_cc);
}

static void test_humidity_correction_is_bounded(void)
{
    TEST_ASSERT_EQUAL_FLOAT(20.0f, umi_pm25_dry(20.0f, 0.0f));
    TEST_ASSERT_TRUE(umi_pm25_dry(20.0f, 100.0f) > 0.5f); /* capped, never divides by zero */
    TEST_ASSERT_TRUE(umi_pm25_dry(20.0f, 90.0f) < umi_pm25_dry(20.0f, 50.0f));
}

/* ---------------------------------------------------------------- queue */

static void push_t(umi_record_queue_t *q, uint32_t t_ms, uint8_t tag)
{
    umi_record_t r;
    umi_state_encode(&(umi_state_t){.t_ms = t_ms, .state = tag}, &r);
    TEST_ASSERT_TRUE(umi_record_queue_push(q, &r));
}

static void test_queue_sorts_and_keeps_ties_in_arrival_order(void)
{
    umi_record_queue_t q;
    umi_record_queue_init(&q);
    push_t(&q, 300, 1);
    push_t(&q, 100, 2);
    push_t(&q, 300, 3);
    push_t(&q, 200, 4);
    uint8_t expected[] = {2, 4, 1, 3};
    umi_record_t r;
    for (size_t i = 0; i < 4; i++) {
        TEST_ASSERT_TRUE(umi_record_queue_pop_until(&q, 1000, &r));
        TEST_ASSERT_EQUAL_UINT8(expected[i], r.payload[4]);
    }
    TEST_ASSERT_FALSE(umi_record_queue_pop(&q, &r));
}

static void test_queue_full(void)
{
    umi_record_queue_t q;
    umi_record_queue_init(&q);
    for (uint32_t i = 0; i < UMI_RECORD_QUEUE_LEN; i++) {
        push_t(&q, i, 0);
    }
    umi_record_t r;
    umi_state_encode(&(umi_state_t){.t_ms = 1, .state = 0}, &r);
    TEST_ASSERT_FALSE(umi_record_queue_push(&q, &r));
}

int main(void)
{
    UNITY_BEGIN();
    RUN_TEST(test_starts_after_five_seconds_of_motion);
    RUN_TEST(test_slow_walk_does_not_start);
    RUN_TEST(test_session_records_follow_the_schedule);
    RUN_TEST(test_time_sync_maps_session_time_to_utc);
    RUN_TEST(test_still_pauses_then_resumes);
    RUN_TEST(test_still_long_enough_stops_with_end);
    RUN_TEST(test_next_session_gets_a_new_id);
    RUN_TEST(test_quiet_clip_without_gnss_is_still);
    RUN_TEST(test_shaking_clip_without_gnss_keeps_recording);
    RUN_TEST(test_late_records_are_written_in_order);
    RUN_TEST(test_unannounced_late_record_is_dropped_not_misordered);
    RUN_TEST(test_flush_holds_records_after_the_horizon);
    RUN_TEST(test_storage_refusal_keeps_idle);
    RUN_TEST(test_status_flags);
    RUN_TEST(test_air_averages_and_corrects_pm25_only);
    RUN_TEST(test_air_without_readings_is_not_available);
    RUN_TEST(test_humidity_correction_is_bounded);
    RUN_TEST(test_queue_sorts_and_keeps_ties_in_arrival_order);
    RUN_TEST(test_queue_full);
    return UNITY_END();
}
