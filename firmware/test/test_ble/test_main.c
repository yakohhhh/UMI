/* Geo helpers, warn-ahead, settings TLV and BLE payloads (protocol/README.md §4). */
#include <math.h>
#include <string.h>
#include <unity.h>

#include "umi/bytes.h"
#include "umi/core/ble_payloads.h"
#include "umi/core/geo.h"
#include "umi/core/settings.h"
#include "umi/core/warn_ahead.h"
#include "umi/protocol_gen.h"

/* Passeig de Gràcia x Carrer de Provença, and the Cerdà grid's south-east axis. */
#define LAT 413952000
#define LON 21611000
#define COURSE_CDEG 13460

static umi_warn_ahead_t warn;

void setUp(void)
{
    umi_warn_ahead_init(&warn);
}

void tearDown(void) {}

/* A point `m` metres from (LAT, LON) along `bearing_deg`, flat-earth: exact
 * enough at these distances for the tests below. */
static umi_geo_point_t offset(double m, double bearing_deg)
{
    double rad = bearing_deg * 3.14159265358979 / 180.0;
    double dlat = m * cos(rad) / UMI_GEO_EARTH_RADIUS_M;
    double dlon = m * sin(rad) / (UMI_GEO_EARTH_RADIUS_M * cos(LAT * 1e-7 * 3.14159265358979 / 180.0));
    return (umi_geo_point_t){LAT + (int32_t)lround(dlat * 180.0 / 3.14159265358979 * 1e7),
                             LON + (int32_t)lround(dlon * 180.0 / 3.14159265358979 * 1e7)};
}

static umi_gnss_fix_t riding(uint16_t speed_cms)
{
    return (umi_gnss_fix_t){.fix = UMI_FIX_THREE_D, .lat_e7 = LAT, .lon_e7 = LON,
                            .speed_cms = speed_cms, .heading_cdeg = COURSE_CDEG};
}

static void load(const umi_hazard_t *hazards, uint16_t n)
{
    TEST_ASSERT_TRUE(umi_warn_ahead_begin(&warn, n));
    TEST_ASSERT_TRUE(umi_warn_ahead_add(&warn, hazards, n));
    TEST_ASSERT_TRUE(umi_warn_ahead_commit(&warn));
}

static umi_hazard_t hazard_at(uint32_t id, double m, double bearing_deg)
{
    umi_geo_point_t p = offset(m, bearing_deg);
    return (umi_hazard_t){id, p.lat_e7, p.lon_e7, UMI_HAZARD_KIND_ROADWORKS};
}

/* ---------------------------------------------------------------- geo */

static void test_distance_and_bearing(void)
{
    umi_geo_point_t a = {LAT, LON};
    umi_geo_point_t b = offset(100.0, 90.0);
    TEST_ASSERT_DOUBLE_WITHIN(0.2, 100.0, umi_geo_distance_m(a, b));
    TEST_ASSERT_DOUBLE_WITHIN(0.2, 90.0, umi_geo_bearing_deg(a, b));
    /* One degree of latitude on the [geo] sphere. */
    umi_geo_point_t north = {LAT + 10000000, LON};
    TEST_ASSERT_DOUBLE_WITHIN(0.5, 111195.1, umi_geo_distance_m(a, north));
    TEST_ASSERT_DOUBLE_WITHIN(1e-6, 0.0, umi_geo_bearing_deg(a, north));
}

static void test_heading_difference_wraps(void)
{
    TEST_ASSERT_DOUBLE_WITHIN(1e-9, 20.0, umi_geo_heading_diff_deg(350.0, 10.0));
    TEST_ASSERT_DOUBLE_WITHIN(1e-9, -20.0, umi_geo_heading_diff_deg(10.0, 350.0));
    TEST_ASSERT_DOUBLE_WITHIN(1e-9, 180.0, umi_geo_heading_diff_deg(0.0, 180.0));
}

static void test_prefilter_never_rejects_a_point_in_range(void)
{
    umi_geo_point_t a = {LAT, LON};
    for (int bearing = 0; bearing < 360; bearing += 15) {
        TEST_ASSERT_TRUE(umi_geo_maybe_within(a, offset(79.0, bearing), 80.0));
    }
    TEST_ASSERT_FALSE(umi_geo_maybe_within(a, offset(500.0, 0.0), 80.0));
}

/* ---------------------------------------------------------------- warn-ahead */

static void test_hazard_ahead_in_radius_warns(void)
{
    umi_hazard_t h[] = {hazard_at(7, 60.0, 134.6)};
    load(h, 1);
    umi_gnss_fix_t fix = riding(500);
    umi_hazard_t out;
    TEST_ASSERT_TRUE(umi_warn_ahead_check(&warn, 1000, &fix, &out));
    TEST_ASSERT_EQUAL_UINT32(7, out.id);
}

static void test_hazard_behind_or_far_is_quiet(void)
{
    umi_hazard_t h[] = {hazard_at(1, 60.0, 314.6), hazard_at(2, UMI_FEEDBACK_WARN_AHEAD_RADIUS_M + 20.0, 134.6)};
    load(h, 2);
    umi_gnss_fix_t fix = riding(500);
    umi_hazard_t out;
    TEST_ASSERT_FALSE(umi_warn_ahead_check(&warn, 1000, &fix, &out));
}

static void test_standing_next_to_a_hazard_is_quiet(void)
{
    umi_hazard_t h[] = {hazard_at(1, 30.0, 134.6)};
    load(h, 1);
    umi_gnss_fix_t fix = riding(50);
    umi_hazard_t out;
    TEST_ASSERT_FALSE(umi_warn_ahead_check(&warn, 1000, &fix, &out));
}

static void test_cooldown_is_per_hazard(void)
{
    umi_hazard_t h[] = {hazard_at(1, 50.0, 134.6), hazard_at(2, 70.0, 134.6)};
    load(h, 2);
    umi_gnss_fix_t fix = riding(500);
    umi_hazard_t out;
    TEST_ASSERT_TRUE(umi_warn_ahead_check(&warn, 1000, &fix, &out));
    TEST_ASSERT_EQUAL_UINT32(1, out.id); /* the nearest first */
    TEST_ASSERT_TRUE(umi_warn_ahead_check(&warn, 2000, &fix, &out));
    TEST_ASSERT_EQUAL_UINT32(2, out.id);
    TEST_ASSERT_FALSE(umi_warn_ahead_check(&warn, 3000, &fix, &out));
    uint32_t after = 1000 + UMI_FEEDBACK_WARN_AHEAD_COOLDOWN_S * 1000;
    TEST_ASSERT_TRUE(umi_warn_ahead_check(&warn, after, &fix, &out));
    TEST_ASSERT_EQUAL_UINT32(1, out.id);
}

static void test_refreshing_the_list_keeps_cooldowns(void)
{
    umi_hazard_t h[] = {hazard_at(1, 50.0, 134.6)};
    load(h, 1);
    umi_gnss_fix_t fix = riding(500);
    umi_hazard_t out;
    TEST_ASSERT_TRUE(umi_warn_ahead_check(&warn, 1000, &fix, &out));
    load(h, 1);
    TEST_ASSERT_FALSE(umi_warn_ahead_check(&warn, 2000, &fix, &out));
}

static void test_incomplete_upload_keeps_the_old_list(void)
{
    umi_hazard_t h[] = {hazard_at(1, 50.0, 134.6), hazard_at(2, 60.0, 134.6)};
    load(h, 1);
    TEST_ASSERT_TRUE(umi_warn_ahead_begin(&warn, 2));
    TEST_ASSERT_TRUE(umi_warn_ahead_add(&warn, &h[1], 1));
    TEST_ASSERT_FALSE(umi_warn_ahead_commit(&warn));
    TEST_ASSERT_EQUAL_size_t(1, warn.count);
    TEST_ASSERT_EQUAL_UINT32(1, warn.active[0].hazard.id);
    TEST_ASSERT_FALSE(umi_warn_ahead_begin(&warn, UMI_WARN_AHEAD_MAX_HAZARDS + 1));
    TEST_ASSERT_FALSE(umi_warn_ahead_add(&warn, h, 1)); /* no upload open */
}

/* ---------------------------------------------------------------- settings */

static void test_settings_defaults_are_opt_in(void)
{
    umi_settings_t s = umi_settings_default();
    TEST_ASSERT_FALSE(s.voice);
    TEST_ASSERT_FALSE(s.warn_ahead);
    TEST_ASSERT_TRUE(s.chirp);
    TEST_ASSERT_EQUAL_HEX8(UMI_LANG_BIT(UMI_LANG_CA) | UMI_LANG_BIT(UMI_LANG_ES) |
                               UMI_LANG_BIT(UMI_LANG_EN),
                           s.languages);
}

static void test_settings_tlv_round_trip(void)
{
    umi_settings_t s = umi_settings_default();
    s.voice = true;
    s.sensors = UMI_SENSOR_AIR;
    uint8_t tlv[32];
    size_t len = umi_settings_encode(&s, tlv, sizeof tlv);
    TEST_ASSERT_EQUAL_size_t(15, len);
    TEST_ASSERT_EQUAL_HEX8(UMI_SETTING_VOICE, tlv[0]);
    TEST_ASSERT_EQUAL_UINT8(1, tlv[1]);
    TEST_ASSERT_EQUAL_UINT8(1, tlv[2]);
    umi_settings_t back = umi_settings_default();
    TEST_ASSERT_TRUE(umi_settings_apply(&back, tlv, len));
    TEST_ASSERT_TRUE(back.voice);
    TEST_ASSERT_EQUAL_HEX8(UMI_SENSOR_AIR, back.sensors);
    TEST_ASSERT_EQUAL_size_t(0, umi_settings_encode(&s, tlv, 10));
}

static void test_settings_skip_unknown_and_reject_truncated(void)
{
    umi_settings_t s = umi_settings_default();
    const uint8_t write[] = {0x7F, 2, 0xAA, 0xBB, UMI_SETTING_WARN_AHEAD, 1, 1};
    TEST_ASSERT_TRUE(umi_settings_apply(&s, write, sizeof write));
    TEST_ASSERT_TRUE(s.warn_ahead);
    const uint8_t truncated[] = {UMI_SETTING_CHIRP, 1, 0, UMI_SETTING_VOICE, 2, 1};
    TEST_ASSERT_FALSE(umi_settings_apply(&s, truncated, sizeof truncated));
    TEST_ASSERT_TRUE(s.chirp); /* nothing applied */
}

/* ---------------------------------------------------------------- BLE */

static void test_uuid_layout(void)
{
    /* b6d20002-6a1e-4c3f-9a9e-2f1c0b5e4d01, little-endian on the air. */
    const uint8_t expected[16] = {0x01, 0x4d, 0x5e, 0x0b, 0x1c, 0x2f, 0x9e, 0x9a,
                                  0x3f, 0x4c, 0x1e, 0x6a, 0x02, 0x00, 0xd2, 0xb6};
    uint8_t uuid[16];
    umi_ble_uuid128(UMI_BLE_LIVE_STATUS, uuid);
    TEST_ASSERT_EQUAL_HEX8_ARRAY(expected, uuid, 16);
}

static void test_live_status_layout(void)
{
    umi_live_status_t s = {82, UMI_STATUS_FLAG_CHARGING, UMI_RECORDER_STATE_RECORDING,
                           UMI_FIX_THREE_D, 0x0102};
    uint8_t out[UMI_BLE_LIVE_STATUS_LEN];
    umi_live_status_encode(&s, out);
    const uint8_t expected[] = {82, 1, 1, 3, 0x02, 0x01};
    TEST_ASSERT_EQUAL_HEX8_ARRAY(expected, out, sizeof expected);
}

static void test_device_info_layout(void)
{
    umi_device_info_t info = {.device_id = 0x00a1b2c3d4e5f601ull, .hw_rev = 1,
                              .fw_version = {0, 1, 0}, .serial = "UMI-0001"};
    info.public_key[0] = 0x04;
    info.public_key[64] = 0x99;
    uint8_t out[128];
    size_t len = umi_device_info_encode(&info, out, sizeof out);
    TEST_ASSERT_EQUAL_size_t(8 + 1 + 3 + 65 + 8, len);
    TEST_ASSERT_EQUAL_HEX64(info.device_id, umi_get_u64le(out));
    TEST_ASSERT_EQUAL_UINT8(1, out[8]);
    TEST_ASSERT_EQUAL_UINT8(0x04, out[12]);
    TEST_ASSERT_EQUAL_UINT8(0x99, out[76]);
    TEST_ASSERT_EQUAL_MEMORY("UMI-0001", out + 77, 8);
    TEST_ASSERT_EQUAL_size_t(0, umi_device_info_encode(&info, out, 80));
}

static void test_control_point_commands(void)
{
    umi_ble_command_t cmd;
    const uint8_t start[] = {0x01, 7, 0, 0, 0, 0x00, 0x10, 0, 0};
    TEST_ASSERT_TRUE(umi_ble_command_parse(start, sizeof start, &cmd));
    TEST_ASSERT_EQUAL_UINT32(7, cmd.arg.start_transfer.session_id);
    TEST_ASSERT_EQUAL_UINT32(4096, cmd.arg.start_transfer.offset);

    uint8_t set_time[9] = {0x04};
    umi_put_i64le(set_time + 1, 1794988320000LL);
    TEST_ASSERT_TRUE(umi_ble_command_parse(set_time, sizeof set_time, &cmd));
    TEST_ASSERT_EQUAL_INT64(1794988320000LL, cmd.arg.set_time_unix_ms);

    const uint8_t begin[] = {0x05, 3, 0};
    TEST_ASSERT_TRUE(umi_ble_command_parse(begin, sizeof begin, &cmd));
    TEST_ASSERT_EQUAL_UINT16(3, cmd.arg.hazards_count);

    const uint8_t end[] = {0x06};
    TEST_ASSERT_TRUE(umi_ble_command_parse(end, sizeof end, &cmd));
    TEST_ASSERT_EQUAL_UINT8(UMI_BLE_OP_HAZARDS_END, cmd.opcode);

    const uint8_t bad_len[] = {0x03, 1, 2};
    TEST_ASSERT_FALSE(umi_ble_command_parse(bad_len, sizeof bad_len, &cmd));
    const uint8_t unknown[] = {0x42};
    TEST_ASSERT_FALSE(umi_ble_command_parse(unknown, sizeof unknown, &cmd));
    TEST_ASSERT_FALSE(umi_ble_command_parse(unknown, 0, &cmd));
}

static void test_hazards_write(void)
{
    uint8_t data[2 * UMI_BLE_HAZARD_LEN];
    umi_put_u32le(data, 11);
    umi_put_i32le(data + 4, LAT);
    umi_put_i32le(data + 8, -LON);
    data[12] = UMI_HAZARD_KIND_POTHOLE;
    umi_put_u32le(data + 13, 12);
    umi_put_i32le(data + 17, LAT + 1);
    umi_put_i32le(data + 21, LON);
    data[25] = UMI_HAZARD_KIND_OBSTACLE;
    umi_hazard_t out[4];
    TEST_ASSERT_EQUAL_INT(2, umi_ble_hazards_parse(data, sizeof data, out, 4));
    TEST_ASSERT_EQUAL_UINT32(11, out[0].id);
    TEST_ASSERT_EQUAL_INT32(-LON, out[0].lon_e7);
    TEST_ASSERT_EQUAL_UINT8(UMI_HAZARD_KIND_OBSTACLE, out[1].kind);
    TEST_ASSERT_EQUAL_INT(-1, umi_ble_hazards_parse(data, sizeof data - 1, out, 4));
    TEST_ASSERT_EQUAL_INT(-1, umi_ble_hazards_parse(data, sizeof data, out, 1));
}

int main(void)
{
    UNITY_BEGIN();
    RUN_TEST(test_distance_and_bearing);
    RUN_TEST(test_heading_difference_wraps);
    RUN_TEST(test_prefilter_never_rejects_a_point_in_range);
    RUN_TEST(test_hazard_ahead_in_radius_warns);
    RUN_TEST(test_hazard_behind_or_far_is_quiet);
    RUN_TEST(test_standing_next_to_a_hazard_is_quiet);
    RUN_TEST(test_cooldown_is_per_hazard);
    RUN_TEST(test_refreshing_the_list_keeps_cooldowns);
    RUN_TEST(test_incomplete_upload_keeps_the_old_list);
    RUN_TEST(test_settings_defaults_are_opt_in);
    RUN_TEST(test_settings_tlv_round_trip);
    RUN_TEST(test_settings_skip_unknown_and_reject_truncated);
    RUN_TEST(test_uuid_layout);
    RUN_TEST(test_live_status_layout);
    RUN_TEST(test_device_info_layout);
    RUN_TEST(test_control_point_commands);
    RUN_TEST(test_hazards_write);
    return UNITY_END();
}
