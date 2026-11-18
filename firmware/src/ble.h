/* BLE GATT service of protocol/README.md §4 on NimBLE.
 *
 * Callbacks run in the NimBLE host task and never touch the application:
 * writes are posted to the core task's inbox, and the core task hands back
 * Live Status snapshots and Control Point results, which this module sends
 * from the host task. */
#ifndef UMI_BLE_H
#define UMI_BLE_H

#include <stddef.h>
#include <stdint.h>

#include "esp_err.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "umi/core/ble_payloads.h"
#include "umi/core/settings.h"

/* ATT_MTU 247 leaves 244 bytes per write. */
#define UMI_BLE_MAX_WRITE 244

typedef enum {
    UMI_BLE_MSG_COMMAND,  /* Control Point, already validated */
    UMI_BLE_MSG_SETTINGS, /* Settings TLV */
    UMI_BLE_MSG_HAZARDS,  /* Hazards chunk */
} umi_ble_msg_kind_t;

typedef struct {
    umi_ble_msg_kind_t kind;
    uint16_t len;
    uint8_t data[UMI_BLE_MAX_WRITE];
} umi_ble_msg_t;

/* Fills out with the Session Index payload; returns its length. Called from
 * the host task. */
typedef size_t (*umi_ble_index_fn)(uint8_t *out, size_t cap);

esp_err_t umi_ble_start(const umi_device_info_t *info, QueueHandle_t inbox,
                        umi_ble_index_fn session_index);

/* From the core task: the latest values, notified to subscribers on change. */
void umi_ble_publish_status(const umi_live_status_t *status);
void umi_ble_publish_settings(const umi_settings_t *settings);

/* From the core task: the Control Point indication for a processed command. */
void umi_ble_indicate(uint8_t opcode, uint8_t status);

#endif /* UMI_BLE_H */
