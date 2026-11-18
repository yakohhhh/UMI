/* Session storage on the "sessions" flash partition (partitions.csv): FAT on
 * ESP-IDF's wear levelling, one /sessions/<id>.umis per session, and the
 * session counter in NVS so ids are never reused, even after a format. */
#ifndef UMI_DRIVERS_ESP32_STORAGE_H
#define UMI_DRIVERS_ESP32_STORAGE_H

#include <stddef.h>
#include <stdint.h>
#include <stdio.h>

#include "esp_err.h"
#include "nvs.h"
#include "umi/hal/storage.h"
#include "wear_levelling.h"

#define UMI_ESP32_SESSIONS_PARTITION "sessions"
#define UMI_ESP32_SESSIONS_PATH "/sessions"

typedef struct {
    wl_handle_t wl;
    nvs_handle_t nvs;
    FILE *file;
    uint32_t open_id;
} umi_esp32_storage_t;

/* One stored session, as listed in the BLE Session Index. */
typedef struct {
    uint32_t session_id;
    uint32_t size;
    uint32_t first_unix_s; /* 0 when the session has no TIME_SYNC yet */
} umi_esp32_session_info_t;

esp_err_t umi_esp32_storage_init(umi_esp32_storage_t *s, nvs_handle_t nvs);
umi_hal_storage_t umi_esp32_storage_hal(umi_esp32_storage_t *s);

/* Sessions on flash, oldest first; returns how many were written to out. */
size_t umi_esp32_storage_list(umi_esp32_storage_t *s, umi_esp32_session_info_t *out, size_t max);

/* Sessions waiting for the phone (Live Status sessions_pending): every stored
 * session except the one being recorded. */
size_t umi_esp32_storage_pending(umi_esp32_storage_t *s);

/* Deletes a stored session once the phone confirmed its upload; refuses the
 * session being recorded. */
esp_err_t umi_esp32_storage_delete(umi_esp32_storage_t *s, uint32_t session_id);

#endif /* UMI_DRIVERS_ESP32_STORAGE_H */
