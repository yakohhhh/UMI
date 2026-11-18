/* The .umis session log (protocol/README.md §1): a 32-byte header, CRC-framed
 * records in non-decreasing t_ms order, and an END record carrying the file CRC. */
#ifndef UMI_SESSION_LOG_H
#define UMI_SESSION_LOG_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "umi/records.h"

/* type + len before the payload, crc16 after it. */
#define UMI_RECORD_FRAMING_LEN 4

typedef struct {
    uint16_t flags; /* umi_header_flag_t bits */
    uint64_t device_id;
    uint32_t session_id;
    uint8_t activity; /* umi_activity_t */
    uint8_t hw_rev;
    uint8_t fw_version[3]; /* major, minor, patch */
} umi_header_t;

void umi_header_encode(const umi_header_t *in, uint8_t out[UMI_FORMAT_HEADER_LEN]);

/* Where the writer puts bytes: a RAM buffer on the host, a flash file on the
 * Clip. Returns false when the bytes could not be stored. */
typedef struct {
    bool (*write)(void *ctx, const uint8_t *data, size_t len);
    void *ctx;
} umi_byte_sink_t;

typedef struct {
    umi_byte_sink_t sink;
    uint32_t file_crc32; /* over every byte written so far */
    uint32_t record_count;
    uint32_t last_t_ms;
    bool failed; /* a sink write failed; the log is truncated from here */
} umi_log_writer_t;

bool umi_log_writer_begin(umi_log_writer_t *w, umi_byte_sink_t sink, const umi_header_t *header);

/* Appends one record. Refuses an END (use umi_log_writer_finish) and a record
 * older than the previous one, which would break the ordering readers rely on. */
bool umi_log_writer_append(umi_log_writer_t *w, const umi_record_t *rec);

/* Writes the END record; the log must not be appended to afterwards. */
bool umi_log_writer_finish(umi_log_writer_t *w, uint32_t duration_ms);

typedef enum {
    UMI_LOG_RECORD,         /* *rec holds the next record */
    UMI_LOG_END,            /* *rec holds a valid END: the log is complete */
    UMI_LOG_TRUNCATED,      /* no END, or a record failed its CRC: stop reading */
    UMI_LOG_BAD_MAGIC,
    UMI_LOG_BAD_VERSION,
    UMI_LOG_BAD_HEADER_CRC,
    UMI_LOG_BAD_HEADER_LEN,
} umi_log_result_t;

typedef struct {
    const uint8_t *data;
    size_t len;
    size_t pos;
    uint32_t record_count;
    bool done;
    umi_log_result_t final; /* END or TRUNCATED once done */
} umi_log_reader_t;

umi_log_result_t umi_log_reader_open(umi_log_reader_t *r, const uint8_t *data, size_t len,
                                     umi_header_t *header);

/* Returns the next record. Unknown record types are returned like any other, so
 * callers skip what they do not decode. After END or TRUNCATED, keeps returning
 * the same result. */
umi_log_result_t umi_log_reader_next(umi_log_reader_t *r, umi_record_t *rec);

#endif /* UMI_SESSION_LOG_H */
