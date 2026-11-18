/* Payloads of the BLE GATT service (protocol/README.md §4), independent of the
 * BLE stack so they are tested on the host. Multi-byte fields little-endian. */
#ifndef UMI_CORE_BLE_PAYLOADS_H
#define UMI_CORE_BLE_PAYLOADS_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "umi/core/warn_ahead.h"
#include "umi/hal/signer.h"

typedef enum {
    UMI_BLE_SERVICE = 0x0000,
    UMI_BLE_DEVICE_INFO = 0x0001,
    UMI_BLE_LIVE_STATUS = 0x0002,
    UMI_BLE_SESSION_INDEX = 0x0003,
    UMI_BLE_CONTROL_POINT = 0x0004,
    UMI_BLE_TRANSFER_DATA = 0x0005,
    UMI_BLE_SETTINGS = 0x0006,
    UMI_BLE_HAZARDS = 0x0007,
} umi_ble_id_t;

/* b6d2xxxx-6a1e-4c3f-9a9e-2f1c0b5e4d01 in over-the-air (little-endian) byte
 * order, which is how BLE stacks store 128-bit UUIDs. */
void umi_ble_uuid128(uint16_t id, uint8_t out[16]);

#define UMI_BLE_LIVE_STATUS_LEN 6

typedef struct {
    uint8_t battery_pct;
    uint8_t status_flags;   /* umi_status_flag_t */
    uint8_t recorder_state; /* 0 idle, else umi_recorder_state_t */
    uint8_t fix;            /* umi_fix_t */
    uint16_t sessions_pending;
} umi_live_status_t;

void umi_live_status_encode(const umi_live_status_t *s, uint8_t out[UMI_BLE_LIVE_STATUS_LEN]);

typedef struct {
    uint64_t device_id;
    uint8_t hw_rev;
    uint8_t fw_version[3];
    uint8_t public_key[UMI_PUBLIC_KEY_LEN];
    const char *serial;
} umi_device_info_t;

/* Returns the length written, 0 if cap is too small. */
size_t umi_device_info_encode(const umi_device_info_t *info, uint8_t *out, size_t cap);

typedef enum {
    UMI_BLE_OP_START_TRANSFER = 0x01,
    UMI_BLE_OP_ACK = 0x02,
    UMI_BLE_OP_DELETE = 0x03,
    UMI_BLE_OP_SET_TIME = 0x04,
    UMI_BLE_OP_HAZARDS_BEGIN = 0x05,
    UMI_BLE_OP_HAZARDS_END = 0x06,
} umi_ble_opcode_t;

/* Status byte of the Control Point indication. The spec leaves the values
 * open; these are the firmware's. */
typedef enum {
    UMI_BLE_STATUS_OK = 0x00,
    UMI_BLE_STATUS_UNSUPPORTED = 0x01,
    UMI_BLE_STATUS_INVALID = 0x02,
    UMI_BLE_STATUS_NOT_FOUND = 0x03,
    UMI_BLE_STATUS_FAILED = 0x04,
} umi_ble_status_t;

typedef struct {
    uint8_t opcode;
    union {
        struct {
            uint32_t session_id;
            uint32_t offset;
        } start_transfer;
        uint16_t ack_chunk_seq;
        uint32_t delete_session_id;
        int64_t set_time_unix_ms;
        uint16_t hazards_count;
    } arg;
} umi_ble_command_t;

/* Fails on an unknown opcode or arguments of the wrong length. */
bool umi_ble_command_parse(const uint8_t *data, size_t len, umi_ble_command_t *out);

#define UMI_BLE_HAZARD_LEN 13

/* A Hazards write: n x (hazard_id u32, lat_e7 i32, lon_e7 i32, kind u8).
 * Returns the number parsed, or -1 if len is not a whole number of hazards or
 * more than max. */
int umi_ble_hazards_parse(const uint8_t *data, size_t len, umi_hazard_t *out, size_t max);

#endif /* UMI_CORE_BLE_PAYLOADS_H */
