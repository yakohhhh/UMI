#include "umi/session_log.h"

#include <string.h>

#include "umi/bytes.h"
#include "umi/crc.h"

/* Header layout (protocol/README.md §1.1). */
enum {
    HDR_MAGIC = 0,
    HDR_VERSION = 4,
    HDR_LEN = 5,
    HDR_FLAGS = 6,
    HDR_DEVICE_ID = 8,
    HDR_SESSION_ID = 16,
    HDR_ACTIVITY = 20,
    HDR_HW_REV = 21,
    HDR_FW_VERSION = 22,
    HDR_CRC = 28,
};

void umi_header_encode(const umi_header_t *in, uint8_t out[UMI_FORMAT_HEADER_LEN])
{
    memset(out, 0, UMI_FORMAT_HEADER_LEN);
    memcpy(out + HDR_MAGIC, UMI_FORMAT_MAGIC, 4);
    out[HDR_VERSION] = UMI_FORMAT_VERSION;
    out[HDR_LEN] = UMI_FORMAT_HEADER_LEN;
    umi_put_u16le(out + HDR_FLAGS, in->flags);
    umi_put_u64le(out + HDR_DEVICE_ID, in->device_id);
    umi_put_u32le(out + HDR_SESSION_ID, in->session_id);
    out[HDR_ACTIVITY] = in->activity;
    out[HDR_HW_REV] = in->hw_rev;
    memcpy(out + HDR_FW_VERSION, in->fw_version, 3);
    umi_put_u32le(out + HDR_CRC, umi_crc32_update(UMI_CRC32_INIT, out, HDR_CRC));
}

static bool emit(umi_log_writer_t *w, const uint8_t *data, size_t len)
{
    if (w->failed || !w->sink.write(w->sink.ctx, data, len)) {
        w->failed = true;
        return false;
    }
    w->file_crc32 = umi_crc32_update(w->file_crc32, data, len);
    return true;
}

/* One sink write per record, so a power loss leaves whole records or a short
 * tail that the reader's CRC check discards. */
static bool emit_record(umi_log_writer_t *w, const umi_record_t *rec)
{
    uint8_t frame[UMI_RECORD_FRAMING_LEN + UMI_FORMAT_MAX_RECORD_PAYLOAD];
    frame[0] = rec->type;
    frame[1] = rec->len;
    memcpy(frame + 2, rec->payload, rec->len);
    uint16_t crc = umi_crc16_update(UMI_CRC16_INIT, frame, (size_t)rec->len + 2);
    umi_put_u16le(frame + 2 + rec->len, crc);
    return emit(w, frame, (size_t)rec->len + UMI_RECORD_FRAMING_LEN);
}

bool umi_log_writer_begin(umi_log_writer_t *w, umi_byte_sink_t sink, const umi_header_t *header)
{
    *w = (umi_log_writer_t){.sink = sink, .file_crc32 = UMI_CRC32_INIT};
    uint8_t bytes[UMI_FORMAT_HEADER_LEN];
    umi_header_encode(header, bytes);
    return emit(w, bytes, sizeof bytes);
}

bool umi_log_writer_append(umi_log_writer_t *w, const umi_record_t *rec)
{
    if (rec->type == UMI_RECORD_TYPE_END || rec->len < 4) {
        return false;
    }
    uint32_t t_ms = umi_record_t_ms(rec);
    if (w->record_count > 0 && t_ms < w->last_t_ms) {
        return false;
    }
    if (!emit_record(w, rec)) {
        return false;
    }
    w->last_t_ms = t_ms;
    w->record_count++;
    return true;
}

bool umi_log_writer_finish(umi_log_writer_t *w, uint32_t duration_ms)
{
    umi_record_t rec;
    umi_end_encode(
        &(umi_end_t){
            /* END closes the log, so it may not precede the last record. */
            .t_ms = duration_ms < w->last_t_ms ? w->last_t_ms : duration_ms,
            .record_count = w->record_count,
            .file_crc32 = w->file_crc32,
        },
        &rec);
    return emit_record(w, &rec);
}

umi_log_result_t umi_log_reader_open(umi_log_reader_t *r, const uint8_t *data, size_t len,
                                     umi_header_t *header)
{
    *r = (umi_log_reader_t){.data = data, .len = len};
    if (len < UMI_FORMAT_HEADER_LEN || memcmp(data, UMI_FORMAT_MAGIC, 4) != 0) {
        return UMI_LOG_BAD_MAGIC;
    }
    if (data[HDR_VERSION] != UMI_FORMAT_VERSION) {
        return UMI_LOG_BAD_VERSION;
    }
    if (umi_crc32_update(UMI_CRC32_INIT, data, HDR_CRC) != umi_get_u32le(data + HDR_CRC)) {
        return UMI_LOG_BAD_HEADER_CRC;
    }
    size_t header_len = data[HDR_LEN];
    if (header_len < UMI_FORMAT_HEADER_LEN || header_len > len) {
        return UMI_LOG_BAD_HEADER_LEN;
    }
    *header = (umi_header_t){
        .flags = umi_get_u16le(data + HDR_FLAGS),
        .device_id = umi_get_u64le(data + HDR_DEVICE_ID),
        .session_id = umi_get_u32le(data + HDR_SESSION_ID),
        .activity = data[HDR_ACTIVITY],
        .hw_rev = data[HDR_HW_REV],
    };
    memcpy(header->fw_version, data + HDR_FW_VERSION, 3);
    r->pos = header_len;
    return UMI_LOG_RECORD;
}

static umi_log_result_t stop(umi_log_reader_t *r, umi_log_result_t result)
{
    r->done = true;
    r->final = result;
    return result;
}

umi_log_result_t umi_log_reader_next(umi_log_reader_t *r, umi_record_t *rec)
{
    if (r->done) {
        return r->final;
    }
    size_t remaining = r->len - r->pos;
    if (remaining < UMI_RECORD_FRAMING_LEN) {
        return stop(r, UMI_LOG_TRUNCATED);
    }
    const uint8_t *frame = r->data + r->pos;
    size_t len = frame[1];
    if (remaining < len + UMI_RECORD_FRAMING_LEN) {
        return stop(r, UMI_LOG_TRUNCATED);
    }
    if (umi_crc16_update(UMI_CRC16_INIT, frame, len + 2) != umi_get_u16le(frame + 2 + len)) {
        return stop(r, UMI_LOG_TRUNCATED);
    }
    rec->type = frame[0];
    rec->len = (uint8_t)len;
    memcpy(rec->payload, frame + 2, len);

    if (rec->type != UMI_RECORD_TYPE_END) {
        r->pos += len + UMI_RECORD_FRAMING_LEN;
        r->record_count++;
        return UMI_LOG_RECORD;
    }
    umi_end_t end;
    bool valid = umi_end_decode(rec, &end) && end.record_count == r->record_count &&
                 end.file_crc32 == umi_crc32_update(UMI_CRC32_INIT, r->data, r->pos);
    return stop(r, valid ? UMI_LOG_END : UMI_LOG_TRUNCATED);
}
