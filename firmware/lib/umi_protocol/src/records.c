#include "umi/records.h"

#include <string.h>

#include "umi/bytes.h"

static uint8_t *begin(umi_record_t *out, uint8_t type, uint8_t len)
{
    out->type = type;
    out->len = len;
    memset(out->payload, 0, len);
    return out->payload;
}

static const uint8_t *expect(const umi_record_t *in, uint8_t type, uint8_t min_len)
{
    return (in->type == type && in->len >= min_len) ? in->payload : NULL;
}

uint32_t umi_record_t_ms(const umi_record_t *rec)
{
    return umi_get_u32le(rec->payload);
}

void umi_sample_encode(const umi_sample_t *in, umi_record_t *out)
{
    uint8_t *p = begin(out, UMI_RECORD_TYPE_SAMPLE, UMI_SAMPLE_LEN);
    umi_put_u32le(p + 0, in->t_ms);
    umi_put_i32le(p + 4, in->lat_e7);
    umi_put_i32le(p + 8, in->lon_e7);
    umi_put_u16le(p + 12, in->speed_cms);
    umi_put_u16le(p + 14, in->heading_cdeg);
    umi_put_u16le(p + 16, in->vib_mms2);
    umi_put_u16le(p + 18, in->noise_cdba);
    p[20] = in->hdop_d;
    p[21] = in->fix;
    p[22] = in->sats;
}

bool umi_sample_decode(const umi_record_t *in, umi_sample_t *out)
{
    const uint8_t *p = expect(in, UMI_RECORD_TYPE_SAMPLE, UMI_SAMPLE_LEN);
    if (p == NULL) {
        return false;
    }
    *out = (umi_sample_t){
        .t_ms = umi_get_u32le(p + 0),
        .lat_e7 = umi_get_i32le(p + 4),
        .lon_e7 = umi_get_i32le(p + 8),
        .speed_cms = umi_get_u16le(p + 12),
        .heading_cdeg = umi_get_u16le(p + 14),
        .vib_mms2 = umi_get_u16le(p + 16),
        .noise_cdba = umi_get_u16le(p + 18),
        .hdop_d = p[20],
        .fix = p[21],
        .sats = p[22],
    };
    return true;
}

void umi_air_encode(const umi_air_t *in, umi_record_t *out)
{
    uint8_t *p = begin(out, UMI_RECORD_TYPE_AIR, UMI_AIR_LEN);
    umi_put_u32le(p + 0, in->t_ms);
    umi_put_u16le(p + 4, in->pm1_dug);
    umi_put_u16le(p + 6, in->pm25_dug);
    umi_put_u16le(p + 8, in->pm10_dug);
    umi_put_i16le(p + 10, in->temp_cc);
    umi_put_u16le(p + 12, in->rh_dpct);
}

bool umi_air_decode(const umi_record_t *in, umi_air_t *out)
{
    const uint8_t *p = expect(in, UMI_RECORD_TYPE_AIR, UMI_AIR_LEN);
    if (p == NULL) {
        return false;
    }
    *out = (umi_air_t){
        .t_ms = umi_get_u32le(p + 0),
        .pm1_dug = umi_get_u16le(p + 4),
        .pm25_dug = umi_get_u16le(p + 6),
        .pm10_dug = umi_get_u16le(p + 8),
        .temp_cc = umi_get_i16le(p + 10),
        .rh_dpct = umi_get_u16le(p + 12),
    };
    return true;
}

void umi_event_encode(const umi_event_t *in, umi_record_t *out)
{
    uint8_t *p = begin(out, UMI_RECORD_TYPE_EVENT, UMI_EVENT_LEN);
    umi_put_u32le(p + 0, in->t_ms);
    p[4] = in->kind;
    umi_put_u16le(p + 6, in->value_mms2);
    umi_put_u16le(p + 8, in->peak_mms2);
    umi_put_u16le(p + 10, in->duration_ms);
    umi_put_i32le(p + 12, in->lat_e7);
    umi_put_i32le(p + 16, in->lon_e7);
}

bool umi_event_decode(const umi_record_t *in, umi_event_t *out)
{
    const uint8_t *p = expect(in, UMI_RECORD_TYPE_EVENT, UMI_EVENT_LEN);
    if (p == NULL) {
        return false;
    }
    *out = (umi_event_t){
        .t_ms = umi_get_u32le(p + 0),
        .kind = p[4],
        .value_mms2 = umi_get_u16le(p + 6),
        .peak_mms2 = umi_get_u16le(p + 8),
        .duration_ms = umi_get_u16le(p + 10),
        .lat_e7 = umi_get_i32le(p + 12),
        .lon_e7 = umi_get_i32le(p + 16),
    };
    return true;
}

void umi_flag_encode(const umi_flag_t *in, umi_record_t *out)
{
    uint8_t *p = begin(out, UMI_RECORD_TYPE_FLAG, UMI_FLAG_LEN);
    umi_put_u32le(p + 0, in->t_ms);
    umi_put_u16le(p + 4, in->seq);
    p[6] = in->source;
    p[7] = in->kind;
    p[8] = in->confidence;
    p[9] = in->lang;
    umi_put_i32le(p + 12, in->lat_e7);
    umi_put_i32le(p + 16, in->lon_e7);
    umi_put_u16le(p + 20, in->speed_cms);
    umi_put_u16le(p + 22, in->vib_mms2);
    umi_put_u16le(p + 24, in->noise_cdba);
    p[28] = in->sig_alg;
    p[29] = in->sig_len;
    memcpy(p + 30, in->signature, UMI_SIGNING_SIGNATURE_LEN);
}

bool umi_flag_decode(const umi_record_t *in, umi_flag_t *out)
{
    const uint8_t *p = expect(in, UMI_RECORD_TYPE_FLAG, UMI_FLAG_LEN);
    if (p == NULL) {
        return false;
    }
    *out = (umi_flag_t){
        .t_ms = umi_get_u32le(p + 0),
        .seq = umi_get_u16le(p + 4),
        .source = p[6],
        .kind = p[7],
        .confidence = p[8],
        .lang = p[9],
        .lat_e7 = umi_get_i32le(p + 12),
        .lon_e7 = umi_get_i32le(p + 16),
        .speed_cms = umi_get_u16le(p + 20),
        .vib_mms2 = umi_get_u16le(p + 22),
        .noise_cdba = umi_get_u16le(p + 24),
        .sig_alg = p[28],
        .sig_len = p[29],
    };
    memcpy(out->signature, p + 30, UMI_SIGNING_SIGNATURE_LEN);
    return true;
}

void umi_flag_undo_encode(const umi_flag_undo_t *in, umi_record_t *out)
{
    uint8_t *p = begin(out, UMI_RECORD_TYPE_FLAG_UNDO, UMI_FLAG_UNDO_LEN);
    umi_put_u32le(p + 0, in->t_ms);
    umi_put_u16le(p + 4, in->seq);
}

bool umi_flag_undo_decode(const umi_record_t *in, umi_flag_undo_t *out)
{
    const uint8_t *p = expect(in, UMI_RECORD_TYPE_FLAG_UNDO, UMI_FLAG_UNDO_LEN);
    if (p == NULL) {
        return false;
    }
    *out = (umi_flag_undo_t){.t_ms = umi_get_u32le(p), .seq = umi_get_u16le(p + 4)};
    return true;
}

void umi_status_encode(const umi_status_t *in, umi_record_t *out)
{
    uint8_t *p = begin(out, UMI_RECORD_TYPE_STATUS, UMI_STATUS_LEN);
    umi_put_u32le(p + 0, in->t_ms);
    p[4] = in->battery_pct;
    p[5] = in->flags;
    umi_put_u16le(p + 6, in->battery_mv);
    umi_put_i16le(p + 8, in->board_temp_cc);
    umi_put_u16le(p + 10, in->free_kib);
}

bool umi_status_decode(const umi_record_t *in, umi_status_t *out)
{
    const uint8_t *p = expect(in, UMI_RECORD_TYPE_STATUS, UMI_STATUS_LEN);
    if (p == NULL) {
        return false;
    }
    *out = (umi_status_t){
        .t_ms = umi_get_u32le(p + 0),
        .battery_pct = p[4],
        .flags = p[5],
        .battery_mv = umi_get_u16le(p + 6),
        .board_temp_cc = umi_get_i16le(p + 8),
        .free_kib = umi_get_u16le(p + 10),
    };
    return true;
}

void umi_time_sync_encode(const umi_time_sync_t *in, umi_record_t *out)
{
    uint8_t *p = begin(out, UMI_RECORD_TYPE_TIME_SYNC, UMI_TIME_SYNC_LEN);
    umi_put_u32le(p + 0, in->t_ms);
    umi_put_i64le(p + 4, in->unix_ms);
}

bool umi_time_sync_decode(const umi_record_t *in, umi_time_sync_t *out)
{
    const uint8_t *p = expect(in, UMI_RECORD_TYPE_TIME_SYNC, UMI_TIME_SYNC_LEN);
    if (p == NULL) {
        return false;
    }
    *out = (umi_time_sync_t){.t_ms = umi_get_u32le(p), .unix_ms = umi_get_i64le(p + 4)};
    return true;
}

void umi_state_encode(const umi_state_t *in, umi_record_t *out)
{
    uint8_t *p = begin(out, UMI_RECORD_TYPE_STATE, UMI_STATE_LEN);
    umi_put_u32le(p + 0, in->t_ms);
    p[4] = in->state;
}

bool umi_state_decode(const umi_record_t *in, umi_state_t *out)
{
    const uint8_t *p = expect(in, UMI_RECORD_TYPE_STATE, UMI_STATE_LEN);
    if (p == NULL) {
        return false;
    }
    *out = (umi_state_t){.t_ms = umi_get_u32le(p), .state = p[4]};
    return true;
}

void umi_trim_encode(const umi_trim_t *in, umi_record_t *out)
{
    uint8_t *p = begin(out, UMI_RECORD_TYPE_TRIM, UMI_TRIM_LEN);
    umi_put_u32le(p + 0, in->t_ms);
    umi_put_u16le(p + 4, in->start_m);
    umi_put_u16le(p + 6, in->end_m);
}

bool umi_trim_decode(const umi_record_t *in, umi_trim_t *out)
{
    const uint8_t *p = expect(in, UMI_RECORD_TYPE_TRIM, UMI_TRIM_LEN);
    if (p == NULL) {
        return false;
    }
    *out = (umi_trim_t){
        .t_ms = umi_get_u32le(p),
        .start_m = umi_get_u16le(p + 4),
        .end_m = umi_get_u16le(p + 6),
    };
    return true;
}

void umi_end_encode(const umi_end_t *in, umi_record_t *out)
{
    uint8_t *p = begin(out, UMI_RECORD_TYPE_END, UMI_END_LEN);
    umi_put_u32le(p + 0, in->t_ms);
    umi_put_u32le(p + 4, in->record_count);
    umi_put_u32le(p + 12, in->file_crc32);
}

bool umi_end_decode(const umi_record_t *in, umi_end_t *out)
{
    const uint8_t *p = expect(in, UMI_RECORD_TYPE_END, UMI_END_LEN);
    if (p == NULL) {
        return false;
    }
    *out = (umi_end_t){
        .t_ms = umi_get_u32le(p),
        .record_count = umi_get_u32le(p + 4),
        .file_crc32 = umi_get_u32le(p + 12),
    };
    return true;
}
