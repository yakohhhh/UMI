/* Session log codec: CRCs, header, records, writer and reader
 * (protocol/README.md §1). */
#include <string.h>
#include <unity.h>

#include "fakes.h"
#include "umi/bytes.h"
#include "umi/crc.h"
#include "umi/flag_signing.h"
#include "umi/session_log.h"

static const umi_header_t HEADER = {
    .flags = UMI_HEADER_FLAG_SIMULATED,
    .device_id = 0x00a1b2c3d4e5f601ull,
    .session_id = 42,
    .activity = UMI_ACTIVITY_RIDE,
    .hw_rev = 0,
    .fw_version = {0, 1, 0},
};

typedef struct {
    uint8_t data[4096];
    size_t len;
    bool fail;
} buffer_t;

static bool buffer_write(void *ctx, const uint8_t *data, size_t len)
{
    buffer_t *b = ctx;
    if (b->fail || b->len + len > sizeof b->data) {
        return false;
    }
    memcpy(b->data + b->len, data, len);
    b->len += len;
    return true;
}

static buffer_t buf;
static umi_log_writer_t writer;
static fake_log_t log_;

void setUp(void)
{
    memset(&buf, 0, sizeof buf);
    TEST_ASSERT_TRUE(umi_log_writer_begin(&writer, (umi_byte_sink_t){buffer_write, &buf}, &HEADER));
}

void tearDown(void) {}

static void append_state(uint32_t t_ms, uint8_t state)
{
    umi_record_t rec;
    umi_state_encode(&(umi_state_t){.t_ms = t_ms, .state = state}, &rec);
    TEST_ASSERT_TRUE(umi_log_writer_append(&writer, &rec));
}

static void test_crc_check_values(void)
{
    /* The catalogue check value of each algorithm, over "123456789". */
    TEST_ASSERT_EQUAL_HEX16(0x29B1, umi_crc16_update(UMI_CRC16_INIT, "123456789", 9));
    TEST_ASSERT_EQUAL_HEX32(0xCBF43926, umi_crc32_update(UMI_CRC32_INIT, "123456789", 9));
}

static void test_crc_is_incremental(void)
{
    uint32_t whole = umi_crc32_update(UMI_CRC32_INIT, "123456789", 9);
    uint32_t split = umi_crc32_update(umi_crc32_update(UMI_CRC32_INIT, "1234", 4), "56789", 5);
    TEST_ASSERT_EQUAL_HEX32(whole, split);
}

static void test_header_layout(void)
{
    uint8_t h[UMI_FORMAT_HEADER_LEN];
    umi_header_encode(&HEADER, h);
    TEST_ASSERT_EQUAL_MEMORY("UMIS", h, 4);
    TEST_ASSERT_EQUAL_UINT8(1, h[4]);
    TEST_ASSERT_EQUAL_UINT8(32, h[5]);
    TEST_ASSERT_EQUAL_UINT16(UMI_HEADER_FLAG_SIMULATED, umi_get_u16le(h + 6));
    TEST_ASSERT_EQUAL_HEX64(0x00a1b2c3d4e5f601ull, umi_get_u64le(h + 8));
    TEST_ASSERT_EQUAL_UINT32(42, umi_get_u32le(h + 16));
    TEST_ASSERT_EQUAL_UINT8(UMI_ACTIVITY_RIDE, h[20]);
    TEST_ASSERT_EQUAL_UINT8(1, h[23]);
    TEST_ASSERT_EQUAL_UINT8(0, h[25] | h[26] | h[27]);
    TEST_ASSERT_EQUAL_HEX32(umi_crc32_update(0, h, 28), umi_get_u32le(h + 28));
}

static void test_record_framing(void)
{
    append_state(1234, UMI_RECORDER_STATE_RECORDING);
    const uint8_t *r = buf.data + UMI_FORMAT_HEADER_LEN;
    TEST_ASSERT_EQUAL_UINT8(UMI_RECORD_TYPE_STATE, r[0]);
    TEST_ASSERT_EQUAL_UINT8(UMI_STATE_LEN, r[1]);
    TEST_ASSERT_EQUAL_UINT32(1234, umi_get_u32le(r + 2));
    TEST_ASSERT_EQUAL_HEX16(umi_crc16_update(UMI_CRC16_INIT, r, 2 + UMI_STATE_LEN),
                            umi_get_u16le(r + 2 + UMI_STATE_LEN));
    TEST_ASSERT_EQUAL_size_t(UMI_FORMAT_HEADER_LEN + UMI_STATE_LEN + 4, buf.len);
}

/* encode -> decode -> encode must give the same bytes: every field survives. */
#define ASSERT_ROUND_TRIP(kind, value, expected_len)                         \
    do {                                                                     \
        umi_record_t first_, second_;                                        \
        umi_##kind##_t decoded_;                                             \
        umi_##kind##_encode(&(value), &first_);                              \
        TEST_ASSERT_EQUAL_UINT8((expected_len), first_.len);                 \
        TEST_ASSERT_TRUE(umi_##kind##_decode(&first_, &decoded_));           \
        umi_##kind##_encode(&decoded_, &second_);                            \
        TEST_ASSERT_EQUAL_UINT8(first_.type, second_.type);                  \
        TEST_ASSERT_EQUAL_MEMORY(first_.payload, second_.payload, first_.len); \
    } while (0)

static void test_every_record_round_trips(void)
{
    umi_sample_t sample = {1000, 413950130, -21613528, 501, 13460, 1392, 6681, 8, 3, 12};
    ASSERT_ROUND_TRIP(sample, sample, UMI_SAMPLE_LEN);
    umi_air_t air = {10000, 89, 87, 199, -150, 610};
    ASSERT_ROUND_TRIP(air, air, UMI_AIR_LEN);
    umi_event_t event = {11360, UMI_EVENT_KIND_HARD_BRAKE, 4346, 5080, 770, -413946622, 21618272};
    ASSERT_ROUND_TRIP(event, event, UMI_EVENT_LEN);
    umi_flag_t flag = {.t_ms = 5, .seq = 3, .source = UMI_FLAG_SOURCE_VOICE, .kind = 4,
                       .confidence = 88, .lang = UMI_LANG_ES, .lat_e7 = 1, .lon_e7 = -2,
                       .speed_cms = 501, .vib_mms2 = 7, .noise_cdba = 6558,
                       .sig_alg = UMI_SIG_ALG_ECDSA_P256, .sig_len = 64};
    for (int i = 0; i < 64; i++) {
        flag.signature[i] = (uint8_t)(i + 1);
    }
    ASSERT_ROUND_TRIP(flag, flag, UMI_FLAG_LEN);
    umi_flag_undo_t undo = {86000, 1};
    ASSERT_ROUND_TRIP(flag_undo, undo, UMI_FLAG_UNDO_LEN);
    umi_status_t status = {60000, 82, UMI_STATUS_FLAG_CHARGING, 3974, -1950, 10110};
    ASSERT_ROUND_TRIP(status, status, UMI_STATUS_LEN);
    umi_time_sync_t sync = {1000, 1794988330000LL};
    ASSERT_ROUND_TRIP(time_sync, sync, UMI_TIME_SYNC_LEN);
    umi_state_t state = {69000, UMI_RECORDER_STATE_AUTO_PAUSE};
    ASSERT_ROUND_TRIP(state, state, UMI_STATE_LEN);
    umi_trim_t trim = {0, 200, 215};
    ASSERT_ROUND_TRIP(trim, trim, UMI_TRIM_LEN);
    umi_end_t end = {103500, 114, 0x814CDA43};
    ASSERT_ROUND_TRIP(end, end, UMI_END_LEN);
}

static void test_flag_payload_offsets(void)
{
    umi_record_t rec;
    umi_flag_t flag = {.t_ms = 0x11223344, .seq = 0x5566, .source = 2, .kind = 3, .confidence = 77,
                       .lang = 1, .lat_e7 = 413950130, .lon_e7 = 21613528, .speed_cms = 501,
                       .vib_mms2 = 1232, .noise_cdba = 6558, .sig_alg = 1, .sig_len = 64};
    flag.signature[63] = 0xEE;
    umi_flag_encode(&flag, &rec);
    const uint8_t *p = rec.payload;
    TEST_ASSERT_EQUAL_HEX16(0x5566, umi_get_u16le(p + 4));
    TEST_ASSERT_EQUAL_UINT8(77, p[8]);
    TEST_ASSERT_EQUAL_INT32(413950130, umi_get_i32le(p + 12));
    TEST_ASSERT_EQUAL_UINT16(6558, umi_get_u16le(p + 24));
    TEST_ASSERT_EQUAL_UINT8(0, p[10] | p[11] | p[26] | p[27]);
    TEST_ASSERT_EQUAL_UINT8(1, p[28]);
    TEST_ASSERT_EQUAL_UINT8(64, p[29]);
    TEST_ASSERT_EQUAL_HEX8(0xEE, p[93]);
}

static void test_decoders_accept_longer_payloads_and_refuse_shorter(void)
{
    umi_record_t rec;
    umi_state_t state;
    umi_state_encode(&(umi_state_t){.t_ms = 9, .state = 2}, &rec);
    rec.len = UMI_STATE_LEN + 10; /* a later version appended fields */
    TEST_ASSERT_TRUE(umi_state_decode(&rec, &state));
    TEST_ASSERT_EQUAL_UINT8(2, state.state);
    rec.len = UMI_STATE_LEN - 1;
    TEST_ASSERT_FALSE(umi_state_decode(&rec, &state));
    rec.type = UMI_RECORD_TYPE_AIR;
    rec.len = UMI_STATE_LEN;
    TEST_ASSERT_FALSE(umi_state_decode(&rec, &state));
}

static void test_complete_log_reads_back(void)
{
    append_state(0, UMI_RECORDER_STATE_RECORDING);
    append_state(500, UMI_RECORDER_STATE_AUTO_PAUSE);
    TEST_ASSERT_TRUE(umi_log_writer_finish(&writer, 900));

    fake_log_read(&log_, buf.data, buf.len);
    TEST_ASSERT_EQUAL(UMI_LOG_END, log_.result);
    TEST_ASSERT_EQUAL_size_t(2, log_.count);
    TEST_ASSERT_EQUAL_UINT32(42, log_.header.session_id);
    TEST_ASSERT_EQUAL_HEX64(HEADER.device_id, log_.header.device_id);

    /* END: duration, record count, CRC of everything before its type byte. */
    const uint8_t *end = buf.data + buf.len - (UMI_END_LEN + 4);
    TEST_ASSERT_EQUAL_UINT8(UMI_RECORD_TYPE_END, end[0]);
    TEST_ASSERT_EQUAL_UINT32(900, umi_get_u32le(end + 2));
    TEST_ASSERT_EQUAL_UINT32(2, umi_get_u32le(end + 6));
    TEST_ASSERT_EQUAL_HEX32(umi_crc32_update(0, buf.data, (size_t)(end - buf.data)),
                            umi_get_u32le(end + 14));
}

static void test_writer_refuses_going_back_in_time(void)
{
    append_state(500, UMI_RECORDER_STATE_RECORDING);
    umi_record_t rec;
    umi_state_encode(&(umi_state_t){.t_ms = 499, .state = 2}, &rec);
    TEST_ASSERT_FALSE(umi_log_writer_append(&writer, &rec));
    umi_state_encode(&(umi_state_t){.t_ms = 500, .state = 2}, &rec);
    TEST_ASSERT_TRUE(umi_log_writer_append(&writer, &rec));
}

static void test_cut_log_is_truncated_but_readable(void)
{
    append_state(0, 1);
    append_state(100, 2);
    size_t cut = buf.len - 3; /* power lost in the middle of the second record */
    fake_log_read(&log_, buf.data, cut);
    TEST_ASSERT_EQUAL(UMI_LOG_TRUNCATED, log_.result);
    TEST_ASSERT_EQUAL_size_t(1, log_.count);
}

static void test_reader_stops_at_first_bad_crc(void)
{
    append_state(0, 1);
    append_state(100, 2);
    append_state(200, 3);
    TEST_ASSERT_TRUE(umi_log_writer_finish(&writer, 300));
    buf.data[UMI_FORMAT_HEADER_LEN + (UMI_STATE_LEN + 4) + 3] ^= 0x40; /* second record */
    fake_log_read(&log_, buf.data, buf.len);
    TEST_ASSERT_EQUAL(UMI_LOG_TRUNCATED, log_.result);
    TEST_ASSERT_EQUAL_size_t(1, log_.count);
}

static void test_reader_returns_unknown_types(void)
{
    umi_record_t rec = {.type = 0x55, .len = 6};
    umi_put_u32le(rec.payload, 10);
    TEST_ASSERT_TRUE(umi_log_writer_append(&writer, &rec));
    append_state(20, 1);
    TEST_ASSERT_TRUE(umi_log_writer_finish(&writer, 30));
    fake_log_read(&log_, buf.data, buf.len);
    TEST_ASSERT_EQUAL(UMI_LOG_END, log_.result);
    TEST_ASSERT_EQUAL_size_t(2, log_.count);
    TEST_ASSERT_EQUAL_UINT8(0x55, log_.records[0].type);
}

static void test_reader_rejects_bad_headers(void)
{
    TEST_ASSERT_TRUE(umi_log_writer_finish(&writer, 0));
    umi_log_reader_t r;
    umi_header_t h;
    buf.data[28] ^= 1;
    TEST_ASSERT_EQUAL(UMI_LOG_BAD_HEADER_CRC, umi_log_reader_open(&r, buf.data, buf.len, &h));
    buf.data[28] ^= 1;
    buf.data[4] = 2;
    TEST_ASSERT_EQUAL(UMI_LOG_BAD_VERSION, umi_log_reader_open(&r, buf.data, buf.len, &h));
    TEST_ASSERT_EQUAL(UMI_LOG_BAD_MAGIC, umi_log_reader_open(&r, buf.data, 10, &h));
}

static void test_end_with_wrong_count_is_truncated(void)
{
    append_state(0, 1);
    TEST_ASSERT_TRUE(umi_log_writer_finish(&writer, 10));
    /* Drop the record, splice the END right after the header. */
    size_t end_at = buf.len - (UMI_END_LEN + 4);
    memmove(buf.data + UMI_FORMAT_HEADER_LEN, buf.data + end_at, UMI_END_LEN + 4);
    fake_log_read(&log_, buf.data, UMI_FORMAT_HEADER_LEN + UMI_END_LEN + 4);
    TEST_ASSERT_EQUAL(UMI_LOG_TRUNCATED, log_.result);
}

static void test_sink_failure_marks_writer(void)
{
    buf.fail = true;
    umi_record_t rec;
    umi_state_encode(&(umi_state_t){.t_ms = 0, .state = 1}, &rec);
    TEST_ASSERT_FALSE(umi_log_writer_append(&writer, &rec));
    TEST_ASSERT_TRUE(writer.failed);
}

static void test_flag_signing_message_layout(void)
{
    umi_record_t rec;
    umi_flag_encode(&(umi_flag_t){.t_ms = 0x01020304, .seq = 7, .source = 1, .sig_alg = 1,
                                  .sig_len = 64},
                    &rec);
    uint8_t msg[UMI_FLAG_MESSAGE_LEN];
    umi_flag_signing_message(0x1122334455667788ull, 0xAABBCCDD, &rec, msg);
    TEST_ASSERT_EQUAL_size_t(51, sizeof msg);
    TEST_ASSERT_EQUAL_MEMORY("UMI-FLAG-v1", msg, 11);
    TEST_ASSERT_EQUAL_HEX64(0x1122334455667788ull, umi_get_u64le(msg + 11));
    TEST_ASSERT_EQUAL_HEX32(0xAABBCCDD, umi_get_u32le(msg + 19));
    TEST_ASSERT_EQUAL_MEMORY(rec.payload, msg + 23, 28);
}

int main(void)
{
    UNITY_BEGIN();
    RUN_TEST(test_crc_check_values);
    RUN_TEST(test_crc_is_incremental);
    RUN_TEST(test_header_layout);
    RUN_TEST(test_record_framing);
    RUN_TEST(test_every_record_round_trips);
    RUN_TEST(test_flag_payload_offsets);
    RUN_TEST(test_decoders_accept_longer_payloads_and_refuse_shorter);
    RUN_TEST(test_complete_log_reads_back);
    RUN_TEST(test_writer_refuses_going_back_in_time);
    RUN_TEST(test_cut_log_is_truncated_but_readable);
    RUN_TEST(test_reader_stops_at_first_bad_crc);
    RUN_TEST(test_reader_returns_unknown_types);
    RUN_TEST(test_reader_rejects_bad_headers);
    RUN_TEST(test_end_with_wrong_count_is_truncated);
    RUN_TEST(test_sink_failure_marks_writer);
    RUN_TEST(test_flag_signing_message_layout);
    return UNITY_END();
}
