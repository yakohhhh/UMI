/* Pure-C frame parsers of the real drivers: NMEA, Plantower, SHT4x, MAX17048. */
#include <string.h>
#include <unity.h>

#include "umi/drivers/lsm6dso32.h"
#include "umi/drivers/max17048.h"
#include "umi/drivers/nmea.h"
#include "umi/drivers/pms.h"
#include "umi/drivers/sht4x.h"
#include "umi/protocol_gen.h"

#define RMC "$GNRMC,075200.00,A,4123.71200,N,00209.66600,E,9.72,134.6,181126,,,A*7C"
#define GGA "$GNGGA,075200.00,4123.71200,N,00209.66600,E,1,12,0.8,42.0,M,49.5,M,,*4A"
#define RMC_SW "$GPRMC,235959.50,A,3351.12345,S,15112.54321,W,0.00,,010100,,,A*49"
#define GGA_SW "$GPGGA,235959.50,3351.12345,S,15112.54321,W,1,3,,10.0,M,0.0,M,,*79"
#define RMC_VOID "$GARMC,075201.00,V,,,,,,,181126,,,N*60"
#define GGA_VOID "$GAGGA,075201.00,,,,,0,0,99.9,,M,,M,,*7F"
#define GSV "$GNGSV,1,1,01,05,40,083,46*5E"
#define GGA_T2 "$GNGGA,075202.00,4123.71200,N,00209.66600,E,1,12,0.8,42.0,M,49.5,M,,*48"
#define RMC_T3 "$GNRMC,075203.00,A,4123.71200,N,00209.66600,E,9.72,134.6,181126,,,A*7F"

static umi_nmea_t nmea;
static umi_gnss_fix_t fix;

void setUp(void)
{
    umi_nmea_init(&nmea);
    memset(&fix, 0, sizeof fix);
}

void tearDown(void) {}

static bool feed(const char *sentence, uint32_t t_ms)
{
    return umi_nmea_feed_sentence(&nmea, sentence, strlen(sentence), t_ms, &fix);
}

/* ---------------------------------------------------------------- NMEA */

static void test_rmc_then_gga_make_a_fix(void)
{
    TEST_ASSERT_FALSE(feed(RMC, 1000));
    TEST_ASSERT_TRUE(feed(GGA, 1005));
    TEST_ASSERT_EQUAL_UINT32(1005, fix.t_ms);
    TEST_ASSERT_EQUAL_UINT8(UMI_FIX_THREE_D, fix.fix);
    TEST_ASSERT_EQUAL_INT32(413952000, fix.lat_e7);
    TEST_ASSERT_EQUAL_INT32(21611000, fix.lon_e7);
    TEST_ASSERT_EQUAL_UINT16(500, fix.speed_cms); /* 9.72 kn */
    TEST_ASSERT_EQUAL_UINT16(13460, fix.heading_cdeg);
    TEST_ASSERT_EQUAL_UINT8(8, fix.hdop_d);
    TEST_ASSERT_EQUAL_UINT8(12, fix.sats);
    TEST_ASSERT_TRUE(fix.has_utc);
    TEST_ASSERT_EQUAL_INT64(1794988320000LL, fix.unix_ms);
}

static void test_gga_then_rmc_also_make_a_fix(void)
{
    TEST_ASSERT_FALSE(feed(GGA, 1000));
    TEST_ASSERT_TRUE(feed(RMC, 1001));
}

static void test_gps_talker_southern_western_hemispheres(void)
{
    feed(RMC_SW, 0);
    TEST_ASSERT_TRUE(feed(GGA_SW, 0));
    TEST_ASSERT_EQUAL_INT32(-338520575, fix.lat_e7);
    TEST_ASSERT_EQUAL_INT32(-1512090535, fix.lon_e7);
    TEST_ASSERT_EQUAL_UINT16(0, fix.heading_cdeg); /* empty course */
    TEST_ASSERT_EQUAL_UINT8(UMI_FIX_TWO_D, fix.fix);   /* three satellites */
    TEST_ASSERT_EQUAL_UINT8(UMI_FORMAT_HDOP_UNKNOWN, fix.hdop_d);
    TEST_ASSERT_EQUAL_INT64(946771199500LL, fix.unix_ms);
}

static void test_no_fix_zeroes_position(void)
{
    feed(RMC_VOID, 0);
    TEST_ASSERT_TRUE(feed(GGA_VOID, 0));
    TEST_ASSERT_EQUAL_UINT8(UMI_FIX_NONE, fix.fix);
    TEST_ASSERT_EQUAL_INT32(0, fix.lat_e7);
    TEST_ASSERT_EQUAL_UINT16(0, fix.speed_cms);
    TEST_ASSERT_EQUAL_UINT8(254, fix.hdop_d); /* 99.9 saturates below "unknown" */
}

static void test_bad_checksum_is_rejected(void)
{
    char broken[] = RMC;
    broken[20] = '5';
    TEST_ASSERT_EQUAL(UMI_NMEA_INVALID, umi_nmea_parse(broken, strlen(broken),
                                                       &(umi_nmea_sentence_t){0}));
    TEST_ASSERT_FALSE(feed(broken, 0));
    TEST_ASSERT_FALSE(feed(GGA, 0));
    TEST_ASSERT_EQUAL_UINT32(1, nmea.rejected);
}

static void test_other_sentences_are_ignored(void)
{
    umi_nmea_sentence_t s;
    TEST_ASSERT_EQUAL(UMI_NMEA_IGNORED, umi_nmea_parse(GSV, strlen(GSV), &s));
    TEST_ASSERT_FALSE(feed(GSV, 0));
    TEST_ASSERT_EQUAL_UINT32(0, nmea.rejected);
}

static void test_epochs_must_match(void)
{
    TEST_ASSERT_FALSE(feed(RMC, 0));
    TEST_ASSERT_FALSE(feed(GGA_T2, 0)); /* a GGA of another second */
    TEST_ASSERT_FALSE(feed(RMC_T3, 0));
    TEST_ASSERT_FALSE(feed(GGA_T2, 0));
}

static void test_uart_bytes_with_noise(void)
{
    const char *stream = "\xff\x01garbage\r\n" RMC "\r\n" GSV "\r\n" GGA "\r\n";
    int fixes = 0;
    for (const char *p = stream; *p != '\0'; p++) {
        fixes += umi_nmea_feed_byte(&nmea, *p, 2000, &fix);
    }
    TEST_ASSERT_EQUAL_INT(1, fixes);
    TEST_ASSERT_EQUAL_INT32(413952000, fix.lat_e7);
}

static void test_overlong_line_is_dropped(void)
{
    char line[UMI_NMEA_MAX_SENTENCE + 20];
    memset(line, 'A', sizeof line);
    line[0] = '$';
    for (size_t i = 0; i < sizeof line; i++) {
        umi_nmea_feed_byte(&nmea, line[i], 0, &fix);
    }
    TEST_ASSERT_EQUAL_UINT32(1, nmea.rejected);
}

/* ---------------------------------------------------------------- Plantower */

static void make_frame(uint8_t frame[UMI_PMS_FRAME_LEN], uint16_t pm25_atm)
{
    const uint16_t words[13] = {9, 17, 21, 8, pm25_atm, 20, 0, 0, 0, 0, 0, 0, 0};
    frame[0] = 0x42;
    frame[1] = 0x4D;
    frame[2] = 0;
    frame[3] = 28;
    for (int i = 0; i < 13; i++) {
        frame[4 + 2 * i] = (uint8_t)(words[i] >> 8);
        frame[5 + 2 * i] = (uint8_t)words[i];
    }
    uint16_t sum = 0;
    for (int i = 0; i < 30; i++) {
        sum = (uint16_t)(sum + frame[i]);
    }
    frame[30] = (uint8_t)(sum >> 8);
    frame[31] = (uint8_t)sum;
}

static void test_plantower_frame(void)
{
    uint8_t frame[UMI_PMS_FRAME_LEN];
    make_frame(frame, 300);
    umi_pms_frame_t out;
    TEST_ASSERT_TRUE(umi_pms_parse(frame, &out));
    TEST_ASSERT_EQUAL_UINT16(17, out.pm25_cf1);
    TEST_ASSERT_EQUAL_UINT16(300, out.pm25_atm);
    TEST_ASSERT_EQUAL_UINT16(20, out.pm10_atm);
    frame[10] ^= 1;
    TEST_ASSERT_FALSE(umi_pms_parse(frame, &out));
}

static void test_plantower_stream_resyncs(void)
{
    uint8_t frame[UMI_PMS_FRAME_LEN];
    make_frame(frame, 16);
    umi_pms_t p;
    umi_pms_init(&p);
    umi_pms_frame_t out;
    const uint8_t noise[] = {0x00, 0x42, 0x42, 0x13, 0x4D};
    int frames = 0;
    for (size_t i = 0; i < sizeof noise; i++) {
        frames += umi_pms_feed(&p, noise[i], &out);
    }
    for (int round = 0; round < 2; round++) {
        for (int i = 0; i < UMI_PMS_FRAME_LEN; i++) {
            frames += umi_pms_feed(&p, frame[i], &out);
        }
    }
    TEST_ASSERT_EQUAL_INT(2, frames);
    TEST_ASSERT_EQUAL_UINT16(16, out.pm25_atm);
}

/* ---------------------------------------------------------------- SHT4x */

static void test_sht4x_crc_datasheet_example(void)
{
    const uint8_t word[] = {0xBE, 0xEF};
    TEST_ASSERT_EQUAL_HEX8(0x92, umi_sht4x_crc8(word, 2));
}

static void test_sht4x_conversion(void)
{
    uint8_t raw[6] = {0x66, 0x66, 0, 0x80, 0x00, 0};
    raw[2] = umi_sht4x_crc8(raw, 2);
    raw[5] = umi_sht4x_crc8(raw + 3, 2);
    float t, rh;
    TEST_ASSERT_TRUE(umi_sht4x_decode(raw, &t, &rh));
    TEST_ASSERT_FLOAT_WITHIN(0.01f, -45.0f + 175.0f * 0x6666 / 65535.0f, t);
    TEST_ASSERT_FLOAT_WITHIN(0.01f, -6.0f + 125.0f * 0x8000 / 65535.0f, rh);
    raw[5] ^= 1;
    TEST_ASSERT_FALSE(umi_sht4x_decode(raw, &t, &rh));
}

static void test_sht4x_humidity_is_clamped(void)
{
    uint8_t raw[6] = {0x66, 0x66, 0, 0xFF, 0xFF, 0};
    raw[2] = umi_sht4x_crc8(raw, 2);
    raw[5] = umi_sht4x_crc8(raw + 3, 2);
    float t, rh;
    TEST_ASSERT_TRUE(umi_sht4x_decode(raw, &t, &rh));
    TEST_ASSERT_EQUAL_FLOAT(100.0f, rh);
}

/* ---------------------------------------------------------------- MAX17048 */

static void test_fuel_gauge_registers(void)
{
    TEST_ASSERT_EQUAL_UINT16(3980, umi_max17048_mv(50944)); /* 50944 x 78.125 µV */
    TEST_ASSERT_EQUAL_UINT8(82, umi_max17048_pct(82 << 8));
    TEST_ASSERT_EQUAL_UINT8(100, umi_max17048_pct(0x6500));
    TEST_ASSERT_EQUAL_INT32(-208, umi_max17048_crate_milli_pct_h(0xFFFF));
}

/* ---------------------------------------------------------------- LSM6DSO32 */

static void test_imu_word_decoding(void)
{
    TEST_ASSERT_EQUAL_UINT8(UMI_LSM6DSO32_TAG_ACCEL, umi_lsm6dso32_tag(0x13)); /* tag 2, counter 1, parity 1 */
    TEST_ASSERT_EQUAL_UINT8(UMI_LSM6DSO32_TAG_GYRO, umi_lsm6dso32_tag(0x0A));
    /* 1 g at ±8 g full scale is 4098 LSB. */
    TEST_ASSERT_FLOAT_WITHIN(0.01f, 9.807f, umi_lsm6dso32_accel_mps2(4098));
    TEST_ASSERT_FLOAT_WITHIN(0.01f, -9.807f, umi_lsm6dso32_accel_mps2(-4098));
    /* 1000 LSB x 70 mdps = 70 °/s. */
    TEST_ASSERT_FLOAT_WITHIN(0.001f, 1.2217f, umi_lsm6dso32_gyro_rads(1000));
}

int main(void)
{
    UNITY_BEGIN();
    RUN_TEST(test_rmc_then_gga_make_a_fix);
    RUN_TEST(test_gga_then_rmc_also_make_a_fix);
    RUN_TEST(test_gps_talker_southern_western_hemispheres);
    RUN_TEST(test_no_fix_zeroes_position);
    RUN_TEST(test_bad_checksum_is_rejected);
    RUN_TEST(test_other_sentences_are_ignored);
    RUN_TEST(test_epochs_must_match);
    RUN_TEST(test_uart_bytes_with_noise);
    RUN_TEST(test_overlong_line_is_dropped);
    RUN_TEST(test_plantower_frame);
    RUN_TEST(test_plantower_stream_resyncs);
    RUN_TEST(test_sht4x_crc_datasheet_example);
    RUN_TEST(test_sht4x_conversion);
    RUN_TEST(test_sht4x_humidity_is_clamped);
    RUN_TEST(test_fuel_gauge_registers);
    RUN_TEST(test_imu_word_decoding);
    return UNITY_END();
}
