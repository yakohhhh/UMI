#include "umi/core/ble_payloads.h"

#include <string.h>

#include "umi/bytes.h"

void umi_ble_uuid128(uint16_t id, uint8_t out[16])
{
    /* Canonical b6d2xxxx-6a1e-4c3f-9a9e-2f1c0b5e4d01, written back to front. */
    static const uint8_t base_le[16] = {0x01, 0x4d, 0x5e, 0x0b, 0x1c, 0x2f, 0x9e, 0x9a,
                                        0x3f, 0x4c, 0x1e, 0x6a, 0x00, 0x00, 0xd2, 0xb6};
    memcpy(out, base_le, 16);
    umi_put_u16le(out + 12, id);
}

void umi_live_status_encode(const umi_live_status_t *s, uint8_t out[UMI_BLE_LIVE_STATUS_LEN])
{
    out[0] = s->battery_pct;
    out[1] = s->status_flags;
    out[2] = s->recorder_state;
    out[3] = s->fix;
    umi_put_u16le(out + 4, s->sessions_pending);
}

size_t umi_device_info_encode(const umi_device_info_t *info, uint8_t *out, size_t cap)
{
    size_t serial_len = info->serial != NULL ? strlen(info->serial) : 0;
    size_t len = 8 + 1 + 3 + UMI_PUBLIC_KEY_LEN + serial_len;
    if (cap < len) {
        return 0;
    }
    umi_put_u64le(out, info->device_id);
    out[8] = info->hw_rev;
    memcpy(out + 9, info->fw_version, 3);
    memcpy(out + 12, info->public_key, UMI_PUBLIC_KEY_LEN);
    if (serial_len > 0) {
        memcpy(out + 12 + UMI_PUBLIC_KEY_LEN, info->serial, serial_len);
    }
    return len;
}

bool umi_ble_command_parse(const uint8_t *data, size_t len, umi_ble_command_t *out)
{
    if (len < 1) {
        return false;
    }
    *out = (umi_ble_command_t){.opcode = data[0]};
    const uint8_t *arg = data + 1;
    size_t arg_len = len - 1;
    switch (data[0]) {
    case UMI_BLE_OP_START_TRANSFER:
        if (arg_len != 8) {
            return false;
        }
        out->arg.start_transfer.session_id = umi_get_u32le(arg);
        out->arg.start_transfer.offset = umi_get_u32le(arg + 4);
        return true;
    case UMI_BLE_OP_ACK:
        if (arg_len != 2) {
            return false;
        }
        out->arg.ack_chunk_seq = umi_get_u16le(arg);
        return true;
    case UMI_BLE_OP_DELETE:
        if (arg_len != 4) {
            return false;
        }
        out->arg.delete_session_id = umi_get_u32le(arg);
        return true;
    case UMI_BLE_OP_SET_TIME:
        if (arg_len != 8) {
            return false;
        }
        out->arg.set_time_unix_ms = umi_get_i64le(arg);
        return true;
    case UMI_BLE_OP_HAZARDS_BEGIN:
        if (arg_len != 2) {
            return false;
        }
        out->arg.hazards_count = umi_get_u16le(arg);
        return true;
    case UMI_BLE_OP_HAZARDS_END:
        return arg_len == 0;
    default:
        return false;
    }
}

int umi_ble_hazards_parse(const uint8_t *data, size_t len, umi_hazard_t *out, size_t max)
{
    if (len % UMI_BLE_HAZARD_LEN != 0 || len / UMI_BLE_HAZARD_LEN > max) {
        return -1;
    }
    size_t n = len / UMI_BLE_HAZARD_LEN;
    for (size_t i = 0; i < n; i++) {
        const uint8_t *p = data + i * UMI_BLE_HAZARD_LEN;
        out[i] = (umi_hazard_t){
            .id = umi_get_u32le(p),
            .lat_e7 = umi_get_i32le(p + 4),
            .lon_e7 = umi_get_i32le(p + 8),
            .kind = p[12],
        };
    }
    return (int)n;
}
