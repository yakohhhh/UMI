/* The golden vectors of protocol/vectors, read from disk (UMI_VECTORS_DIR):
 * the C codec must encode the inputs of minimal and full byte for byte, sign
 * flags exactly like the reference (RFC 6979), and decode every file to the
 * values of its canonical JSON. */
#include <inttypes.h>
#include <stdio.h>
#include <string.h>
#include <unity.h>

#include "umi/core/flags.h"
#include "umi/flag_signing.h"
#include "umi/session_log.h"
#include "umi/sim/soft_signer.h"
#include "vector_json.h"

#ifndef UMI_VECTORS_DIR
#error "UMI_VECTORS_DIR must name protocol/vectors (platformio.ini, env:native)"
#endif

/* The shared inputs of every vector (protocol/vectors/README.md). */
static const umi_header_t VECTOR_HEADER = {
    .flags = UMI_HEADER_FLAG_SIMULATED,
    .device_id = 0x00000000c11b0001ull,
    .session_id = 1,
    .activity = UMI_ACTIVITY_RIDE,
    .hw_rev = 0,
    .fw_version = {0, 1, 0},
};
static const int64_t SESSION_START_UNIX_MS = 1794988320000LL;
/* TEST ONLY: the private scalar of protocol/vectors/test-key.pem. */
static const char TEST_KEY_HEX[] = "cc9984b4083513ef75c4ac63f128a5f81e7580ea86a99ad8d74a8d727b49a663";

typedef struct {
    uint8_t data[64 * 1024];
    size_t len;
} buffer_t;

static buffer_t encoded;
static buffer_t file;
static char json[256 * 1024];
static umi_log_writer_t writer;
static umi_soft_signer_t soft_signer;

static bool buffer_write(void *ctx, const uint8_t *data, size_t len)
{
    buffer_t *b = ctx;
    if (b->len + len > sizeof b->data) {
        return false;
    }
    memcpy(b->data + b->len, data, len);
    b->len += len;
    return true;
}

static size_t read_vector(const char *name, void *out, size_t cap)
{
    char path[512];
    snprintf(path, sizeof path, "%s/%s", UMI_VECTORS_DIR, name);
    FILE *f = fopen(path, "rb");
    TEST_ASSERT_NOT_NULL_MESSAGE(f, path);
    size_t len = fread(out, 1, cap, f);
    bool whole = feof(f) != 0;
    fclose(f);
    TEST_ASSERT_TRUE_MESSAGE(whole, path);
    return len;
}

static void load(const char *stem)
{
    char name[64];
    snprintf(name, sizeof name, "%s.umis", stem);
    file.len = read_vector(name, file.data, sizeof file.data);
    snprintf(name, sizeof name, "%s.json", stem);
    size_t n = read_vector(name, json, sizeof json - 1);
    json[n] = '\0';
}

static void hex_to_bytes(const char *hex, uint8_t *out, size_t n)
{
    for (size_t i = 0; i < n; i++) {
        unsigned v;
        TEST_ASSERT_EQUAL_INT(1, sscanf(hex + 2 * i, "%2x", &v));
        out[i] = (uint8_t)v;
    }
}

static void bytes_to_hex(const uint8_t *data, size_t n, char *out)
{
    for (size_t i = 0; i < n; i++) {
        snprintf(out + 2 * i, 3, "%02x", data[i]);
    }
    out[2 * n] = '\0';
}

void setUp(void)
{
    encoded.len = 0;
    TEST_ASSERT_TRUE(umi_log_writer_begin(&writer, (umi_byte_sink_t){buffer_write, &encoded}, &VECTOR_HEADER));
    uint8_t key[UMI_PRIVATE_KEY_LEN];
    hex_to_bytes(TEST_KEY_HEX, key, sizeof key);
    TEST_ASSERT_TRUE(umi_soft_signer_init(&soft_signer, key));
}

void tearDown(void) {}

static void append(const umi_record_t *rec)
{
    TEST_ASSERT_TRUE(umi_log_writer_append(&writer, rec));
}

/* Appends one record from its fields in wire order, as the README tables list them. */
#define APPEND(kind, ...)                                       \
    do {                                                        \
        umi_record_t rec_;                                      \
        umi_##kind##_encode(&(umi_##kind##_t){__VA_ARGS__}, &rec_); \
        append(&rec_);                                          \
    } while (0)

static void assert_encoded_equals(const char *stem)
{
    load(stem);
    TEST_ASSERT_EQUAL_size_t(file.len, encoded.len);
    TEST_ASSERT_EQUAL_HEX8_ARRAY(file.data, encoded.data, file.len);
}

/* ---------------------------------------------------------------- encoding */

static void test_minimal_is_encoded_byte_for_byte(void)
{
    APPEND(time_sync, 0, SESSION_START_UNIX_MS);
    APPEND(sample, 1000, 414029000, 21564400, 500, 6500, 850, 6420, 9, 3, 11);
    APPEND(sample, 2000, 414029200, 21565000, 520, 6500, 1210, 6590, 9, 3, 12);
    APPEND(sample, 3000, 414029400, 21565610, 510, 6600, 990, 6475, 8, 3, 12);
    TEST_ASSERT_TRUE(umi_log_writer_finish(&writer, 3000));
    assert_encoded_equals("minimal");
}

static void test_full_is_encoded_byte_for_byte(void)
{
    /* The two signed flags go through the Clip's own flag module and signer:
     * deterministic ECDSA must reproduce the reference's signatures. */
    umi_flags_t flags;
    umi_flags_init(&flags, umi_soft_signer_hal(&soft_signer), VECTOR_HEADER.device_id);
    umi_flags_begin_session(&flags, VECTOR_HEADER.session_id);
    const uint16_t na = UMI_FORMAT_NOT_AVAILABLE_U16;
    umi_record_t rec;

    APPEND(time_sync, 0, SESSION_START_UNIX_MS);
    APPEND(state, 0, UMI_RECORDER_STATE_RECORDING);
    APPEND(sample, 1000, 0, 0, 0, 0, 640, 6230, UMI_FORMAT_HDOP_UNKNOWN, UMI_FIX_NONE, 3);
    APPEND(sample, 2000, 414038900, 21586100, 480, 6420, 910, 6380, 12, UMI_FIX_TWO_D, 6);
    APPEND(air, 2000, 52, 87, 131, -150, 712);
    APPEND(event, 2400, UMI_EVENT_KIND_HARD_BRAKE, 3850, 6120, 640, 414038900, 21586100);
    APPEND(sample, 3000, 414039100, 21586500, 230, 6380, 1130, na, 9, UMI_FIX_THREE_D, 9);
    TEST_ASSERT_EQUAL(UMI_FLAG_PRESSED,
                      umi_flags_create(&flags, 3200, UMI_FLAG_SOURCE_PRESS, NULL,
                                       &(umi_snapshot_t){414039100, 21586500, 230, 1130, na}, &rec));
    append(&rec);
    APPEND(event, 3600, UMI_EVENT_KIND_POTHOLE, 4630, 13900, 120, 414039100, 21586500);
    APPEND(sample, 4000, 414039400, 21587100, 510, 6410, 4630, 6710, 8, UMI_FIX_THREE_D, 11);
    TEST_ASSERT_EQUAL(UMI_FLAG_UNDERSTOOD,
                      umi_flags_create(&flags, 4100, UMI_FLAG_SOURCE_VOICE,
                                       &(umi_keyword_result_t){UMI_HAZARD_KIND_ROADWORKS, 92, UMI_LANG_CA},
                                       &(umi_snapshot_t){414039400, 21587100, 510, 4630, 6710}, &rec));
    append(&rec);
    APPEND(flag, .t_ms = 4800, .seq = 2, .source = UMI_FLAG_SOURCE_PRESS, .lat_e7 = 414039400,
           .lon_e7 = 21587100, .speed_cms = 510, .vib_mms2 = 4630, .noise_cdba = 6710,
           .sig_alg = UMI_SIG_ALG_NONE);
    APPEND(sample, 5000, 414039700, 21587700, 505, 6400, 1020, 6650, 8, UMI_FIX_THREE_D, 11);
    APPEND(flag_undo, 5100, 2);
    APPEND(status, 5100, 18, UMI_STATUS_FLAG_LOW_BATTERY, 3610, 3125, 5120);
    APPEND(state, 36000, UMI_RECORDER_STATE_AUTO_PAUSE);
    APPEND(state, 41000, UMI_RECORDER_STATE_RESUME);
    APPEND(sample, 42000, 414040800, 21589000, 150, 6390, 700, 6120, 9, UMI_FIX_THREE_D, 12);
    TEST_ASSERT_TRUE(umi_log_writer_finish(&writer, 42000));
    TEST_ASSERT_EQUAL_UINT32(0, flags.signing_failures);
    assert_encoded_equals("full");
}

/* ---------------------------------------------------------------- decoding */

#define PUT(obj, key, fmt, value) vj_set((obj), (key), (fmt), (value))

static void describe_header(const umi_header_t *h, vj_object_t *o)
{
    o->count = 0;
    PUT(o, "header_flags", "%u", (unsigned)h->flags);
    PUT(o, "device_id", "%016" PRIx64, h->device_id);
    PUT(o, "session_id", "%" PRIu32, h->session_id);
    PUT(o, "activity", "%u", (unsigned)h->activity);
    PUT(o, "hw_rev", "%u", (unsigned)h->hw_rev);
    vj_set(o, "fw_version", "[%u,%u,%u]", h->fw_version[0], h->fw_version[1], h->fw_version[2]);
}

/* The canonical form of one record (README, "Canonical JSON"): wire values,
 * spec field names, reserved bytes left out. */
static void describe_record(const umi_record_t *rec, vj_object_t *o)
{
    o->count = 0;
    switch (rec->type) {
    case UMI_RECORD_TYPE_SAMPLE: {
        umi_sample_t v;
        TEST_ASSERT_TRUE(umi_sample_decode(rec, &v));
        PUT(o, "type", "%s", "sample");
        PUT(o, "t_ms", "%" PRIu32, v.t_ms);
        PUT(o, "lat_e7", "%" PRId32, v.lat_e7);
        PUT(o, "lon_e7", "%" PRId32, v.lon_e7);
        PUT(o, "speed_cms", "%u", (unsigned)v.speed_cms);
        PUT(o, "heading_cdeg", "%u", (unsigned)v.heading_cdeg);
        PUT(o, "vib_mms2", "%u", (unsigned)v.vib_mms2);
        PUT(o, "noise_cdba", "%u", (unsigned)v.noise_cdba);
        PUT(o, "hdop_d", "%u", (unsigned)v.hdop_d);
        PUT(o, "fix", "%u", (unsigned)v.fix);
        PUT(o, "sats", "%u", (unsigned)v.sats);
        return;
    }
    case UMI_RECORD_TYPE_AIR: {
        umi_air_t v;
        TEST_ASSERT_TRUE(umi_air_decode(rec, &v));
        PUT(o, "type", "%s", "air");
        PUT(o, "t_ms", "%" PRIu32, v.t_ms);
        PUT(o, "pm1_dug", "%u", (unsigned)v.pm1_dug);
        PUT(o, "pm25_dug", "%u", (unsigned)v.pm25_dug);
        PUT(o, "pm10_dug", "%u", (unsigned)v.pm10_dug);
        PUT(o, "temp_cc", "%d", (int)v.temp_cc);
        PUT(o, "rh_dpct", "%u", (unsigned)v.rh_dpct);
        return;
    }
    case UMI_RECORD_TYPE_EVENT: {
        umi_event_t v;
        TEST_ASSERT_TRUE(umi_event_decode(rec, &v));
        PUT(o, "type", "%s", "event");
        PUT(o, "t_ms", "%" PRIu32, v.t_ms);
        PUT(o, "kind", "%u", (unsigned)v.kind);
        PUT(o, "value_mms2", "%u", (unsigned)v.value_mms2);
        PUT(o, "peak_mms2", "%u", (unsigned)v.peak_mms2);
        PUT(o, "duration_ms", "%u", (unsigned)v.duration_ms);
        PUT(o, "lat_e7", "%" PRId32, v.lat_e7);
        PUT(o, "lon_e7", "%" PRId32, v.lon_e7);
        return;
    }
    case UMI_RECORD_TYPE_FLAG: {
        umi_flag_t v;
        TEST_ASSERT_TRUE(umi_flag_decode(rec, &v));
        char signature[2 * UMI_SIGNING_SIGNATURE_LEN + 1];
        bytes_to_hex(v.signature, sizeof v.signature, signature);
        PUT(o, "type", "%s", "flag");
        PUT(o, "t_ms", "%" PRIu32, v.t_ms);
        PUT(o, "seq", "%u", (unsigned)v.seq);
        PUT(o, "source", "%u", (unsigned)v.source);
        PUT(o, "kind", "%u", (unsigned)v.kind);
        PUT(o, "confidence", "%u", (unsigned)v.confidence);
        PUT(o, "lang", "%u", (unsigned)v.lang);
        PUT(o, "lat_e7", "%" PRId32, v.lat_e7);
        PUT(o, "lon_e7", "%" PRId32, v.lon_e7);
        PUT(o, "speed_cms", "%u", (unsigned)v.speed_cms);
        PUT(o, "vib_mms2", "%u", (unsigned)v.vib_mms2);
        PUT(o, "noise_cdba", "%u", (unsigned)v.noise_cdba);
        PUT(o, "sig_alg", "%u", (unsigned)v.sig_alg);
        PUT(o, "sig_len", "%u", (unsigned)v.sig_len);
        PUT(o, "signature", "%s", signature);
        return;
    }
    case UMI_RECORD_TYPE_FLAG_UNDO: {
        umi_flag_undo_t v;
        TEST_ASSERT_TRUE(umi_flag_undo_decode(rec, &v));
        PUT(o, "type", "%s", "flag_undo");
        PUT(o, "t_ms", "%" PRIu32, v.t_ms);
        PUT(o, "seq", "%u", (unsigned)v.seq);
        return;
    }
    case UMI_RECORD_TYPE_STATUS: {
        umi_status_t v;
        TEST_ASSERT_TRUE(umi_status_decode(rec, &v));
        PUT(o, "type", "%s", "status");
        PUT(o, "t_ms", "%" PRIu32, v.t_ms);
        PUT(o, "battery_pct", "%u", (unsigned)v.battery_pct);
        PUT(o, "flags", "%u", (unsigned)v.flags);
        PUT(o, "battery_mv", "%u", (unsigned)v.battery_mv);
        PUT(o, "board_temp_cc", "%d", (int)v.board_temp_cc);
        PUT(o, "free_kib", "%u", (unsigned)v.free_kib);
        return;
    }
    case UMI_RECORD_TYPE_TIME_SYNC: {
        umi_time_sync_t v;
        TEST_ASSERT_TRUE(umi_time_sync_decode(rec, &v));
        PUT(o, "type", "%s", "time_sync");
        PUT(o, "t_ms", "%" PRIu32, v.t_ms);
        PUT(o, "unix_ms", "%" PRId64, v.unix_ms);
        return;
    }
    case UMI_RECORD_TYPE_STATE: {
        umi_state_t v;
        TEST_ASSERT_TRUE(umi_state_decode(rec, &v));
        PUT(o, "type", "%s", "state");
        PUT(o, "t_ms", "%" PRIu32, v.t_ms);
        PUT(o, "state", "%u", (unsigned)v.state);
        return;
    }
    case UMI_RECORD_TYPE_TRIM: {
        umi_trim_t v;
        TEST_ASSERT_TRUE(umi_trim_decode(rec, &v));
        PUT(o, "type", "%s", "trim");
        PUT(o, "t_ms", "%" PRIu32, v.t_ms);
        PUT(o, "start_m", "%u", (unsigned)v.start_m);
        PUT(o, "end_m", "%u", (unsigned)v.end_m);
        return;
    }
    case UMI_RECORD_TYPE_END: {
        umi_end_t v;
        TEST_ASSERT_TRUE(umi_end_decode(rec, &v));
        PUT(o, "type", "%s", "end");
        PUT(o, "t_ms", "%" PRIu32, v.t_ms);
        PUT(o, "record_count", "%" PRIu32, v.record_count);
        PUT(o, "file_crc32", "%" PRIu32, v.file_crc32);
        return;
    }
    default: {
        /* A type from a later revision: the reader hands it over raw. */
        char payload[2 * UMI_FORMAT_MAX_RECORD_PAYLOAD + 1];
        bytes_to_hex(rec->payload, rec->len, payload);
        PUT(o, "type", "%s", "unknown");
        PUT(o, "type_id", "%u", (unsigned)rec->type);
        PUT(o, "t_ms", "%" PRIu32, umi_record_t_ms(rec));
        PUT(o, "payload", "%s", payload);
        return;
    }
    }
}

static void assert_same_object(const vj_object_t *expected, const vj_object_t *actual, const char *where)
{
    char message[128];
    TEST_ASSERT_EQUAL_size_t_MESSAGE(expected->count, actual->count, where);
    for (size_t i = 0; i < expected->count; i++) {
        snprintf(message, sizeof message, "%s, %s", where, expected->fields[i].key);
        const char *value = vj_get(actual, expected->fields[i].key);
        TEST_ASSERT_NOT_NULL_MESSAGE(value, message);
        TEST_ASSERT_EQUAL_STRING_MESSAGE(expected->fields[i].value, value, message);
    }
}

/* Decodes <stem>.umis with the C reader and compares every value with <stem>.json. */
static void assert_decodes_to_its_json(const char *stem)
{
    load(stem);
    static vj_object_t expected, actual;
    char where[64];

    umi_log_reader_t reader;
    umi_header_t header;
    TEST_ASSERT_EQUAL(UMI_LOG_RECORD, umi_log_reader_open(&reader, file.data, file.len, &header));
    TEST_ASSERT_NOT_NULL(vj_object(vj_find(json, "header"), &expected));
    describe_header(&header, &actual);
    assert_same_object(&expected, &actual, "header");

    const char *records = vj_find(json, "records");
    TEST_ASSERT_NOT_NULL(records);
    umi_record_t rec;
    umi_log_result_t result;
    size_t index = 0;
    while ((result = umi_log_reader_next(&reader, &rec)) == UMI_LOG_RECORD) {
        snprintf(where, sizeof where, "%s record %zu", stem, index++);
        TEST_ASSERT_TRUE_MESSAGE(vj_next_object(&records, &expected), where);
        describe_record(&rec, &actual);
        assert_same_object(&expected, &actual, where);
    }
    snprintf(where, sizeof where, "%s: more records in the JSON", stem);
    TEST_ASSERT_FALSE_MESSAGE(vj_next_object(&records, &expected), where);

    const char *complete = vj_find(json, "complete");
    TEST_ASSERT_NOT_NULL(complete);
    if (strncmp(complete, "true", 4) == 0) {
        TEST_ASSERT_EQUAL(UMI_LOG_END, result);
        TEST_ASSERT_NOT_NULL(vj_object(vj_find(json, "end"), &expected));
        describe_record(&rec, &actual);
        assert_same_object(&expected, &actual, "end");
    } else {
        TEST_ASSERT_EQUAL(UMI_LOG_TRUNCATED, result);
        TEST_ASSERT_EQUAL_STRING_LEN("null", vj_find(json, "end"), 4);
    }
}

static void test_minimal_decodes_to_its_json(void) { assert_decodes_to_its_json("minimal"); }
static void test_full_decodes_to_its_json(void) { assert_decodes_to_its_json("full"); }
static void test_truncated_decodes_to_its_json(void) { assert_decodes_to_its_json("truncated"); }
static void test_unknown_record_decodes_to_its_json(void) { assert_decodes_to_its_json("unknown-record"); }
static void test_ride_decodes_to_its_json(void) { assert_decodes_to_its_json("ride"); }
static void test_ride_trimmed_decodes_to_its_json(void) { assert_decodes_to_its_json("ride.trimmed"); }

static void test_reader_passes_over_unknown_records_and_longer_payloads(void)
{
    load("unknown-record");
    umi_log_reader_t reader;
    umi_header_t header;
    umi_record_t rec;
    TEST_ASSERT_EQUAL(UMI_LOG_RECORD, umi_log_reader_open(&reader, file.data, file.len, &header));
    uint8_t types[8];
    uint8_t lens[8];
    size_t n = 0;
    while (umi_log_reader_next(&reader, &rec) == UMI_LOG_RECORD && n < sizeof types) {
        types[n] = rec.type;
        lens[n++] = rec.len;
    }
    TEST_ASSERT_EQUAL(UMI_LOG_END, reader.final);
    const uint8_t expected_types[] = {UMI_RECORD_TYPE_TIME_SYNC, UMI_RECORD_TYPE_SAMPLE, 0x42,
                                      UMI_RECORD_TYPE_SAMPLE};
    TEST_ASSERT_EQUAL_size_t(sizeof expected_types, n);
    TEST_ASSERT_EQUAL_HEX8_ARRAY(expected_types, types, n);
    TEST_ASSERT_EQUAL_UINT8(UMI_SAMPLE_LEN + 4, lens[3]); /* fields appended by a later revision */
}

/* ---------------------------------------------------------------- round trip */

#define REENCODE(kind)                                    \
    do {                                                  \
        umi_##kind##_t v_;                                \
        TEST_ASSERT_TRUE(umi_##kind##_decode(in, &v_));   \
        umi_##kind##_encode(&v_, out);                    \
    } while (0)

static void reencode(const umi_record_t *in, umi_record_t *out)
{
    switch (in->type) {
    case UMI_RECORD_TYPE_SAMPLE: REENCODE(sample); break;
    case UMI_RECORD_TYPE_AIR: REENCODE(air); break;
    case UMI_RECORD_TYPE_EVENT: REENCODE(event); break;
    case UMI_RECORD_TYPE_FLAG: REENCODE(flag); break;
    case UMI_RECORD_TYPE_FLAG_UNDO: REENCODE(flag_undo); break;
    case UMI_RECORD_TYPE_STATUS: REENCODE(status); break;
    case UMI_RECORD_TYPE_TIME_SYNC: REENCODE(time_sync); break;
    case UMI_RECORD_TYPE_STATE: REENCODE(state); break;
    case UMI_RECORD_TYPE_TRIM: REENCODE(trim); break;
    default: *out = *in; break;
    }
}

/* Decodes every record to its struct and writes it back with the C writer. */
static void assert_reencodes_byte_for_byte(const char *stem)
{
    load(stem);
    umi_log_reader_t reader;
    umi_header_t header;
    umi_record_t rec, again;
    TEST_ASSERT_EQUAL(UMI_LOG_RECORD, umi_log_reader_open(&reader, file.data, file.len, &header));
    encoded.len = 0;
    TEST_ASSERT_TRUE(umi_log_writer_begin(&writer, (umi_byte_sink_t){buffer_write, &encoded}, &header));
    while (umi_log_reader_next(&reader, &rec) == UMI_LOG_RECORD) {
        reencode(&rec, &again);
        append(&again);
    }
    TEST_ASSERT_EQUAL(UMI_LOG_END, reader.final);
    TEST_ASSERT_TRUE(umi_log_writer_finish(&writer, umi_record_t_ms(&rec)));
    TEST_ASSERT_EQUAL_size_t(file.len, encoded.len);
    TEST_ASSERT_EQUAL_HEX8_ARRAY(file.data, encoded.data, file.len);
}

static void test_ride_reencodes_byte_for_byte(void) { assert_reencodes_byte_for_byte("ride"); }
static void test_ride_trimmed_reencodes_byte_for_byte(void) { assert_reencodes_byte_for_byte("ride.trimmed"); }

/* ---------------------------------------------------------------- signatures */

/* Re-signs every signed flag of a vector; returns how many there were. */
static size_t assert_signatures_reproduced(const char *stem)
{
    load(stem);
    umi_hal_signer_t signer = umi_soft_signer_hal(&soft_signer);
    umi_log_reader_t reader;
    umi_header_t header;
    umi_record_t rec;
    size_t signed_flags = 0;
    TEST_ASSERT_EQUAL(UMI_LOG_RECORD, umi_log_reader_open(&reader, file.data, file.len, &header));
    while (umi_log_reader_next(&reader, &rec) == UMI_LOG_RECORD) {
        umi_flag_t flag;
        if (rec.type != UMI_RECORD_TYPE_FLAG || !umi_flag_decode(&rec, &flag) ||
            flag.sig_alg != UMI_SIG_ALG_ECDSA_P256) {
            continue;
        }
        uint8_t message[UMI_FLAG_MESSAGE_LEN];
        uint8_t signature[UMI_SIGNING_SIGNATURE_LEN];
        umi_flag_signing_message(header.device_id, header.session_id, &rec, message);
        TEST_ASSERT_TRUE(signer.sign(signer.ctx, message, sizeof message, signature));
        TEST_ASSERT_EQUAL_HEX8_ARRAY(flag.signature, signature, sizeof signature);
        signed_flags++;
    }
    return signed_flags;
}

static void test_every_vector_signature_is_reproduced(void)
{
    TEST_ASSERT_EQUAL_size_t(2, assert_signatures_reproduced("full"));
    TEST_ASSERT_EQUAL_size_t(6, assert_signatures_reproduced("ride"));
    TEST_ASSERT_EQUAL_size_t(4, assert_signatures_reproduced("ride.trimmed"));
}

int main(void)
{
    UNITY_BEGIN();
    RUN_TEST(test_minimal_is_encoded_byte_for_byte);
    RUN_TEST(test_full_is_encoded_byte_for_byte);
    RUN_TEST(test_minimal_decodes_to_its_json);
    RUN_TEST(test_full_decodes_to_its_json);
    RUN_TEST(test_truncated_decodes_to_its_json);
    RUN_TEST(test_unknown_record_decodes_to_its_json);
    RUN_TEST(test_ride_decodes_to_its_json);
    RUN_TEST(test_ride_trimmed_decodes_to_its_json);
    RUN_TEST(test_reader_passes_over_unknown_records_and_longer_payloads);
    RUN_TEST(test_ride_reencodes_byte_for_byte);
    RUN_TEST(test_ride_trimmed_reencodes_byte_for_byte);
    RUN_TEST(test_every_vector_signature_is_reproduced);
    return UNITY_END();
}
