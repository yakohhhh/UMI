/* Session log records (protocol/README.md §1.3): decoded structs and their
 * fixed-point wire encoding. Field names keep the unit suffixes of the spec. */
#ifndef UMI_RECORDS_H
#define UMI_RECORDS_H

#include <stdbool.h>
#include <stdint.h>

#include "umi/protocol_gen.h"

/* Payload lengths this codec writes. Readers accept longer payloads: fields are
 * only ever appended (protocol/README.md §1.2). */
enum {
    UMI_SAMPLE_LEN = 24,
    UMI_AIR_LEN = 16,
    UMI_EVENT_LEN = 20,
    UMI_FLAG_LEN = 94,
    UMI_FLAG_UNDO_LEN = 6,
    UMI_STATUS_LEN = 12,
    UMI_TIME_SYNC_LEN = 12,
    UMI_STATE_LEN = 6,
    UMI_TRIM_LEN = 8,
    UMI_END_LEN = 16,
};

/* Bytes 0-27 of a FLAG payload: what the Clip's signature covers (§1.4). */
#define UMI_FLAG_SIGNED_PREFIX_LEN 28

/* A framed record before CRC: what the writer appends and the reader returns. */
typedef struct {
    uint8_t type;
    uint8_t len;
    uint8_t payload[UMI_FORMAT_MAX_RECORD_PAYLOAD];
} umi_record_t;

/* Every payload starts with t_ms, so ordering never needs the record type. */
uint32_t umi_record_t_ms(const umi_record_t *rec);

typedef struct {
    uint32_t t_ms;
    int32_t lat_e7;
    int32_t lon_e7;
    uint16_t speed_cms;
    uint16_t heading_cdeg;
    uint16_t vib_mms2;
    uint16_t noise_cdba;
    uint8_t hdop_d;
    uint8_t fix;
    uint8_t sats;
} umi_sample_t;

typedef struct {
    uint32_t t_ms;
    uint16_t pm1_dug;
    uint16_t pm25_dug;
    uint16_t pm10_dug;
    int16_t temp_cc;
    uint16_t rh_dpct;
} umi_air_t;

typedef struct {
    uint32_t t_ms;
    uint8_t kind;
    uint16_t value_mms2;
    uint16_t peak_mms2;
    uint16_t duration_ms;
    int32_t lat_e7;
    int32_t lon_e7;
} umi_event_t;

typedef struct {
    uint32_t t_ms;
    uint16_t seq;
    uint8_t source;
    uint8_t kind;
    uint8_t confidence;
    uint8_t lang;
    int32_t lat_e7;
    int32_t lon_e7;
    uint16_t speed_cms;
    uint16_t vib_mms2;
    uint16_t noise_cdba;
    uint8_t sig_alg;
    uint8_t sig_len;
    uint8_t signature[UMI_SIGNING_SIGNATURE_LEN];
} umi_flag_t;

typedef struct {
    uint32_t t_ms;
    uint16_t seq;
} umi_flag_undo_t;

typedef struct {
    uint32_t t_ms;
    uint8_t battery_pct;
    uint8_t flags;
    uint16_t battery_mv;
    int16_t board_temp_cc;
    uint16_t free_kib;
} umi_status_t;

typedef struct {
    uint32_t t_ms;
    int64_t unix_ms;
} umi_time_sync_t;

typedef struct {
    uint32_t t_ms;
    uint8_t state;
} umi_state_t;

typedef struct {
    uint32_t t_ms;
    uint16_t start_m;
    uint16_t end_m;
} umi_trim_t;

typedef struct {
    uint32_t t_ms;
    uint32_t record_count;
    uint32_t file_crc32;
} umi_end_t;

/* Encoders fill type, len and payload; reserved bytes are zero. */
void umi_sample_encode(const umi_sample_t *in, umi_record_t *out);
void umi_air_encode(const umi_air_t *in, umi_record_t *out);
void umi_event_encode(const umi_event_t *in, umi_record_t *out);
void umi_flag_encode(const umi_flag_t *in, umi_record_t *out);
void umi_flag_undo_encode(const umi_flag_undo_t *in, umi_record_t *out);
void umi_status_encode(const umi_status_t *in, umi_record_t *out);
void umi_time_sync_encode(const umi_time_sync_t *in, umi_record_t *out);
void umi_state_encode(const umi_state_t *in, umi_record_t *out);
void umi_trim_encode(const umi_trim_t *in, umi_record_t *out);
void umi_end_encode(const umi_end_t *in, umi_record_t *out);

/* Decoders fail on a wrong type or a payload shorter than the known layout,
 * and ignore any extra trailing bytes. */
bool umi_sample_decode(const umi_record_t *in, umi_sample_t *out);
bool umi_air_decode(const umi_record_t *in, umi_air_t *out);
bool umi_event_decode(const umi_record_t *in, umi_event_t *out);
bool umi_flag_decode(const umi_record_t *in, umi_flag_t *out);
bool umi_flag_undo_decode(const umi_record_t *in, umi_flag_undo_t *out);
bool umi_status_decode(const umi_record_t *in, umi_status_t *out);
bool umi_time_sync_decode(const umi_record_t *in, umi_time_sync_t *out);
bool umi_state_decode(const umi_record_t *in, umi_state_t *out);
bool umi_trim_decode(const umi_record_t *in, umi_trim_t *out);
bool umi_end_decode(const umi_record_t *in, umi_end_t *out);

#endif /* UMI_RECORDS_H */
