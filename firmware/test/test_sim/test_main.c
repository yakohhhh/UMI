/* Simulated parts: SHA-256, software signer, scenario parser, simulated world. */
#include <stdio.h>
#include <string.h>
#include <unity.h>

#include "umi/core/spl.h"
#include "umi/sim/scenario.h"
#include "umi/sim/sha256.h"
#include "umi/sim/soft_signer.h"
#include "umi/sim/world.h"

void setUp(void) {}
void tearDown(void) {}

static void hex_to_bytes(const char *hex, uint8_t *out, size_t n)
{
    for (size_t i = 0; i < n; i++) {
        unsigned v;
        sscanf(hex + 2 * i, "%2x", &v);
        out[i] = (uint8_t)v;
    }
}

static void assert_hex(const char *hex, const uint8_t *data, size_t n)
{
    uint8_t expected[128];
    hex_to_bytes(hex, expected, n);
    TEST_ASSERT_EQUAL_HEX8_ARRAY(expected, data, n);
}

/* ---------------------------------------------------------------- SHA-256 */

static void test_sha256_fips_vectors(void)
{
    uint8_t d[UMI_SHA256_LEN];
    umi_sha256("", 0, d);
    assert_hex("e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", d, 32);
    umi_sha256("abc", 3, d);
    assert_hex("ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad", d, 32);
    const char *two_blocks = "abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq";
    umi_sha256(two_blocks, strlen(two_blocks), d);
    assert_hex("248d6a61d20638b8e5c026930c3e6039a33ce45964ff2167f6ecedd419db06c1", d, 32);
}

static void test_sha256_streaming_a_million_a(void)
{
    umi_sha256_t h;
    umi_sha256_init(&h);
    char chunk[1000];
    memset(chunk, 'a', sizeof chunk);
    for (int i = 0; i < 1000; i++) {
        umi_sha256_update(&h, chunk, sizeof chunk);
    }
    uint8_t d[UMI_SHA256_LEN];
    umi_sha256_final(&h, d);
    assert_hex("cdc76e5c9914fb9281a1c7e284d73e67f1809a48a497200e046d39ccc7112cd0", d, 32);
}

/* ---------------------------------------------------------------- signer */

static void test_signer_matches_rfc6979_p256_sha256(void)
{
    /* RFC 6979 A.2.5: deterministic ECDSA, P-256, SHA-256, message "sample". */
    uint8_t key[UMI_PRIVATE_KEY_LEN];
    hex_to_bytes("c9afa9d845ba75166b5c215767b1d6934e50c3db36e89b127b8a622b120f6721", key, 32);
    umi_soft_signer_t s;
    TEST_ASSERT_TRUE(umi_soft_signer_init(&s, key));
    umi_hal_signer_t hal = umi_soft_signer_hal(&s);
    TEST_ASSERT_EQUAL_UINT8(UMI_SIG_ALG_ECDSA_P256, hal.alg);

    uint8_t pub[UMI_PUBLIC_KEY_LEN];
    TEST_ASSERT_TRUE(hal.public_key(hal.ctx, pub));
    assert_hex("0460fed4ba255a9d31c961eb74c6356d68c049b8923b61fa6ce669622e60f29fb6"
               "7903fe1008b8bc99a41ae9e95628bc64f2f1b20c2d7e9f5177a3c294d4462299",
               pub, 65);

    uint8_t sig[64];
    TEST_ASSERT_TRUE(hal.sign(hal.ctx, (const uint8_t *)"sample", 6, sig));
    assert_hex("efd48b2aacb6a8fd1140dd9cd45e81d69d2c877b56aaf991c34d0ea84eaf3716"
               "f7cb1c942d657c41d436c7a1b6e29f65f3e900dbb9aff4064dc4ab2f843acda8",
               sig, 64);
    TEST_ASSERT_TRUE(hal.sign(hal.ctx, (const uint8_t *)"test", 4, sig));
    assert_hex("f1abb023518351cd71d881567b1ea663ed3efcf6c5132b354f28d3b0b7d38367"
               "019f4113742a2b14bd25926b49c649155f267e60d3814b4c0cc84250e46f0083",
               sig, 64);
}

static void test_signer_refuses_an_invalid_key(void)
{
    uint8_t zero[UMI_PRIVATE_KEY_LEN] = {0};
    umi_soft_signer_t s;
    TEST_ASSERT_FALSE(umi_soft_signer_init(&s, zero));
}

/* ---------------------------------------------------------------- scenario */

static uint32_t warnings;
static uint32_t last_warning_line;

static void count_warning(void *ctx, uint32_t line_no, const char *reason)
{
    (void)ctx, (void)reason;
    warnings++;
    last_warning_line = line_no;
}

static void test_scenario_needs_the_header(void)
{
    umi_scenario_t s;
    TEST_ASSERT_FALSE(umi_scenario_open(&s, "0,imu,0,0,9.8,0,0,0\n", NULL, NULL));
    TEST_ASSERT_FALSE(umi_scenario_open(&s, "# umi-sil-scenario v2\n", NULL, NULL));
    TEST_ASSERT_TRUE(umi_scenario_open(&s, "# umi-sil-scenario v1\r\n", NULL, NULL));
}

static void test_scenario_reads_every_kind(void)
{
    const char *text =
        "# umi-sil-scenario v1\n"
        "# a comment\n"
        "\n"
        "0,imu,0.02,-0.01,9.81,0.000,0.001,-0.5\n"
        "1000,gnss,$GNRMC,075200.00,A,4124.0000,N,00209.6000,E,10.80,92.5,181126,,,A*6C\r\n"
        "1000,pm,424d001c00090011001500080010001400000000000000000000000000000106\n"
        "1000,spl,64.2\n"
        "1000,env,19.5,61.0\n"
        "1000,battery,3980,82\n"
        "1200,button,down\n"
        "1300,keyword,blocked_lane,92,ca";
    umi_scenario_t s;
    TEST_ASSERT_TRUE(umi_scenario_open(&s, text, NULL, NULL));
    umi_scenario_line_t l;
    TEST_ASSERT_TRUE(umi_scenario_next(&s, &l));
    TEST_ASSERT_EQUAL(UMI_SCN_IMU, l.kind);
    TEST_ASSERT_EQUAL_FLOAT(9.81f, l.as.imu.az);
    TEST_ASSERT_EQUAL_FLOAT(-0.5f, l.as.imu.gz);
    TEST_ASSERT_TRUE(umi_scenario_next(&s, &l));
    TEST_ASSERT_EQUAL(UMI_SCN_GNSS, l.kind);
    TEST_ASSERT_EQUAL_UINT32(1000, l.t_ms);
    TEST_ASSERT_EQUAL_size_t(strlen("$GNRMC,075200.00,A,4124.0000,N,00209.6000,E,10.80,92.5,181126,,,A*6C"),
                             l.as.gnss.len);
    TEST_ASSERT_TRUE(umi_scenario_next(&s, &l));
    TEST_ASSERT_EQUAL(UMI_SCN_PM, l.kind);
    TEST_ASSERT_EQUAL_HEX8(0x42, l.as.pm[0]);
    TEST_ASSERT_EQUAL_HEX8(0x06, l.as.pm[31]);
    TEST_ASSERT_TRUE(umi_scenario_next(&s, &l));
    TEST_ASSERT_EQUAL_FLOAT(64.2f, l.as.spl_dba);
    TEST_ASSERT_TRUE(umi_scenario_next(&s, &l));
    TEST_ASSERT_EQUAL_FLOAT(61.0f, l.as.env.rh_pct);
    TEST_ASSERT_TRUE(umi_scenario_next(&s, &l));
    TEST_ASSERT_EQUAL_UINT16(3980, l.as.battery.mv);
    TEST_ASSERT_EQUAL_UINT8(82, l.as.battery.pct);
    TEST_ASSERT_TRUE(umi_scenario_next(&s, &l));
    TEST_ASSERT_TRUE(l.as.button_pressed);
    TEST_ASSERT_TRUE(umi_scenario_next(&s, &l));
    TEST_ASSERT_EQUAL(UMI_SCN_KEYWORD, l.kind);
    TEST_ASSERT_EQUAL_UINT8(UMI_HAZARD_KIND_BLOCKED_LANE, l.as.keyword.kind);
    TEST_ASSERT_EQUAL_UINT8(92, l.as.keyword.confidence);
    TEST_ASSERT_EQUAL_UINT8(UMI_LANG_CA, l.as.keyword.lang);
    TEST_ASSERT_FALSE(umi_scenario_next(&s, &l));
    TEST_ASSERT_EQUAL_UINT32(0, s.skipped);
}

static void test_scenario_skips_what_it_cannot_use(void)
{
    const char *text = "# umi-sil-scenario v1\n"
                       "0,imu,0,0,9.8,0,0,0\n"
                       "10,lidar,1,2,3\n"           /* unknown kind: the format grows */
                       "20,imu,0,0,9.8\n"           /* too few fields */
                       "30,button,pressed\n"        /* bad value */
                       "40,keyword,pothole,101,ca\n" /* confidence out of range */
                       "abc,imu,0,0,9.8,0,0,0\n"    /* bad time */
                       "50,imu,0,0,9.8,0,0,0\n"
                       "45,imu,0,0,9.8,0,0,0\n";    /* back in time */
    warnings = 0;
    umi_scenario_t s;
    TEST_ASSERT_TRUE(umi_scenario_open(&s, text, count_warning, NULL));
    umi_scenario_line_t l;
    int lines = 0;
    while (umi_scenario_next(&s, &l)) {
        lines++;
    }
    TEST_ASSERT_EQUAL_INT(2, lines);
    TEST_ASSERT_EQUAL_UINT32(6, warnings);
    TEST_ASSERT_EQUAL_UINT32(9, last_warning_line);
}

/* ---------------------------------------------------------------- world */

#define PM_LINE "pm,424d001c00090011001500080010001400000000000000000000000000000106"

static char text[64 * 1024];

static void build_world_text(void)
{
    size_t n = (size_t)snprintf(text, sizeof text, "# umi-sil-scenario v1\n");
    for (uint32_t t = 0; t <= 2000; t += 10) {
        n += (size_t)snprintf(text + n, sizeof text - n, "%u,imu,0.1,0,9.8,0,0,0\n", t);
        if (t % 100 == 0) {
            n += (size_t)snprintf(text + n, sizeof text - n, "%u,spl,70.0\n", t);
        }
        if (t == 1000) {
            n += (size_t)snprintf(
                text + n, sizeof text - n,
                "1000,gnss,$GNRMC,075200.00,A,4123.71200,N,00209.66600,E,9.72,134.6,181126,,,A*7C\n"
                "1000,gnss,$GNGGA,075200.00,4123.71200,N,00209.66600,E,1,12,0.8,42.0,M,49.5,M,,*4A\n"
                "1000," PM_LINE "\n"
                "1000,env,21.0,55.0\n"
                "1000,battery,3900,70\n"
                "1000,button,down\n"
                "1100,button,up\n"
                "1200,keyword,roadworks,90,es\n"
                "1600,keyword,obstacle,80,en\n");
        }
    }
}

static void test_world_delivers_up_to_now(void)
{
    build_world_text();
    static umi_sim_world_t w;
    TEST_ASSERT_TRUE(umi_sim_world_init(&w, text, NULL, NULL));
    umi_hal_t hal = {0};
    umi_sim_world_bind(&w, &hal);

    umi_sim_world_advance(&w, 15);
    umi_imu_sample_t imu[8];
    TEST_ASSERT_EQUAL_size_t(2, hal.imu.read(hal.imu.ctx, imu, 8));
    TEST_ASSERT_EQUAL_UINT32(10, imu[1].t_ms);

    umi_gnss_fix_t fix;
    TEST_ASSERT_FALSE(hal.gnss.poll(hal.gnss.ctx, &fix));
    umi_sim_world_advance(&w, 1000);
    TEST_ASSERT_TRUE(hal.gnss.poll(hal.gnss.ctx, &fix));
    TEST_ASSERT_EQUAL_INT32(413952000, fix.lat_e7);
    TEST_ASSERT_EQUAL_UINT32(1000, fix.t_ms);

    umi_pm_reading_t pm;
    TEST_ASSERT_TRUE(hal.pm.poll(hal.pm.ctx, &pm));
    TEST_ASSERT_EQUAL_UINT16(16, pm.pm25_ugm3);
    TEST_ASSERT_FALSE(hal.pm.poll(hal.pm.ctx, &pm));

    umi_env_reading_t env;
    TEST_ASSERT_TRUE(hal.env.poll(hal.env.ctx, &env));
    TEST_ASSERT_EQUAL_FLOAT(55.0f, env.rh_pct);
    TEST_ASSERT_FALSE(hal.env.poll(hal.env.ctx, &env));
    int16_t board;
    TEST_ASSERT_TRUE(hal.board.temp_cc(hal.board.ctx, &board));
    TEST_ASSERT_EQUAL_INT16(2100, board);

    umi_battery_reading_t bat;
    TEST_ASSERT_TRUE(hal.battery.poll(hal.battery.ctx, &bat));
    TEST_ASSERT_EQUAL_UINT8(70, bat.pct);

    umi_button_edge_t edge;
    TEST_ASSERT_TRUE(hal.button.poll(hal.button.ctx, &edge));
    TEST_ASSERT_TRUE(edge.pressed);
    TEST_ASSERT_FALSE(hal.button.poll(hal.button.ctx, &edge));
}

static void test_keywords_only_reach_an_open_window(void)
{
    build_world_text();
    static umi_sim_world_t w;
    TEST_ASSERT_TRUE(umi_sim_world_init(&w, text, NULL, NULL));
    umi_hal_t hal = {0};
    umi_sim_world_bind(&w, &hal);
    umi_keyword_result_t kw;

    umi_sim_world_advance(&w, 1300); /* the 1200 ms keyword: nobody listening */
    TEST_ASSERT_EQUAL_UINT32(1, w.stray_keywords);
    hal.keyword.start(hal.keyword.ctx);
    TEST_ASSERT_FALSE(hal.keyword.poll(hal.keyword.ctx, &kw));
    umi_sim_world_advance(&w, 1700);
    TEST_ASSERT_TRUE(hal.keyword.poll(hal.keyword.ctx, &kw));
    TEST_ASSERT_EQUAL_UINT8(UMI_HAZARD_KIND_OBSTACLE, kw.kind);
    TEST_ASSERT_EQUAL_UINT8(UMI_LANG_EN, kw.lang);
    TEST_ASSERT_FALSE(hal.keyword.poll(hal.keyword.ctx, &kw));
    hal.keyword.stop(hal.keyword.ctx);
}

static void test_mic_synthesises_the_scripted_level(void)
{
    build_world_text();
    static umi_sim_world_t w;
    TEST_ASSERT_TRUE(umi_sim_world_init(&w, text, NULL, NULL));
    umi_hal_t hal = {0};
    umi_sim_world_bind(&w, &hal);
    TEST_ASSERT_EQUAL_UINT32(UMI_SIM_MIC_RATE_HZ, hal.mic.sample_rate_hz);

    umi_spl_t meter;
    umi_spl_init(&meter, hal.mic.sample_rate_hz, 0.0f);
    int32_t pcm[256];
    uint64_t samples = 0;
    for (uint32_t now = 0; now <= 2000; now += 10) {
        umi_sim_world_advance(&w, now);
        size_t n;
        while ((n = hal.mic.read(hal.mic.ctx, pcm, 256)) > 0) {
            umi_spl_process(&meter, pcm, n);
            samples += n;
        }
    }
    TEST_ASSERT_EQUAL_UINT64(2000u * UMI_SIM_MIC_RATE_HZ / 1000u, samples);
    float dba;
    TEST_ASSERT_TRUE(umi_spl_laeq_1s(&meter, &dba));
    TEST_ASSERT_FLOAT_WITHIN(0.1f, 70.0f, dba);
}

static void test_world_reports_the_end(void)
{
    build_world_text();
    static umi_sim_world_t w;
    TEST_ASSERT_TRUE(umi_sim_world_init(&w, text, NULL, NULL));
    umi_sim_world_advance(&w, 1999);
    TEST_ASSERT_FALSE(umi_sim_world_finished(&w));
    umi_sim_world_advance(&w, 2000);
    TEST_ASSERT_TRUE(umi_sim_world_finished(&w));
    TEST_ASSERT_EQUAL_UINT32(2000, umi_sim_world_last_ms(&w));
}

int main(void)
{
    UNITY_BEGIN();
    RUN_TEST(test_sha256_fips_vectors);
    RUN_TEST(test_sha256_streaming_a_million_a);
    RUN_TEST(test_signer_matches_rfc6979_p256_sha256);
    RUN_TEST(test_signer_refuses_an_invalid_key);
    RUN_TEST(test_scenario_needs_the_header);
    RUN_TEST(test_scenario_reads_every_kind);
    RUN_TEST(test_scenario_skips_what_it_cannot_use);
    RUN_TEST(test_world_delivers_up_to_now);
    RUN_TEST(test_keywords_only_reach_an_open_window);
    RUN_TEST(test_mic_synthesises_the_scripted_level);
    RUN_TEST(test_world_reports_the_end);
    return UNITY_END();
}
