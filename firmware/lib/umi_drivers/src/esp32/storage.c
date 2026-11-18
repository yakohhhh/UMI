#include "umi/drivers/esp32/storage.h"

#include <dirent.h>
#include <inttypes.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

#include "esp_vfs_fat.h"
#include "umi/session_log.h"

#define NEXT_ID_KEY "next_sid"
#define PATH_MAX_LEN 48
/* The first TIME_SYNC is written within the first seconds of a session. */
#define TIME_SYNC_SCAN_BYTES 1024

static void session_path(uint32_t session_id, char out[PATH_MAX_LEN])
{
    snprintf(out, PATH_MAX_LEN, UMI_ESP32_SESSIONS_PATH "/%08" PRIx32 ".umis", session_id);
}

esp_err_t umi_esp32_storage_init(umi_esp32_storage_t *s, nvs_handle_t nvs)
{
    *s = (umi_esp32_storage_t){.wl = WL_INVALID_HANDLE, .nvs = nvs};
    esp_vfs_fat_mount_config_t mount = {
        .format_if_mount_failed = true,
        .max_files = 2,
        .allocation_unit_size = CONFIG_WL_SECTOR_SIZE,
    };
    return esp_vfs_fat_spiflash_mount_rw_wl(UMI_ESP32_SESSIONS_PATH, UMI_ESP32_SESSIONS_PARTITION,
                                            &mount, &s->wl);
}

static bool next_session_id(void *ctx, uint32_t *out)
{
    umi_esp32_storage_t *s = ctx;
    uint32_t id = 1;
    esp_err_t err = nvs_get_u32(s->nvs, NEXT_ID_KEY, &id);
    if (err != ESP_OK && err != ESP_ERR_NVS_NOT_FOUND) {
        return false;
    }
    /* Committed before use: a crash right after must not hand it out twice. */
    if (nvs_set_u32(s->nvs, NEXT_ID_KEY, id + 1) != ESP_OK || nvs_commit(s->nvs) != ESP_OK) {
        return false;
    }
    *out = id;
    return true;
}

static bool open_session(void *ctx, uint32_t session_id)
{
    umi_esp32_storage_t *s = ctx;
    char path[PATH_MAX_LEN];
    session_path(session_id, path);
    s->file = fopen(path, "wb");
    s->open_id = s->file != NULL ? session_id : 0;
    return s->file != NULL;
}

static bool write_bytes(void *ctx, const uint8_t *data, size_t len)
{
    umi_esp32_storage_t *s = ctx;
    return s->file != NULL && fwrite(data, 1, len, s->file) == len;
}

static bool flush(void *ctx)
{
    umi_esp32_storage_t *s = ctx;
    return s->file != NULL && fflush(s->file) == 0 && fsync(fileno(s->file)) == 0;
}

static bool close_session(void *ctx)
{
    umi_esp32_storage_t *s = ctx;
    if (s->file == NULL) {
        return false;
    }
    bool ok = fclose(s->file) == 0;
    s->file = NULL;
    s->open_id = 0;
    return ok;
}

static uint32_t free_kib(void *ctx)
{
    (void)ctx;
    uint64_t total, free_bytes;
    if (esp_vfs_fat_info(UMI_ESP32_SESSIONS_PATH, &total, &free_bytes) != ESP_OK) {
        return 0;
    }
    return (uint32_t)(free_bytes / 1024u);
}

umi_hal_storage_t umi_esp32_storage_hal(umi_esp32_storage_t *s)
{
    return (umi_hal_storage_t){
        .next_session_id = next_session_id,
        .open = open_session,
        .write = write_bytes,
        .flush = flush,
        .close = close_session,
        .free_kib = free_kib,
        .ctx = s,
    };
}

/* UTC of t_ms = 0 from the first TIME_SYNC near the start of the file. */
static uint32_t first_unix_s(const char *path)
{
    FILE *f = fopen(path, "rb");
    if (f == NULL) {
        return 0;
    }
    uint8_t *head = malloc(TIME_SYNC_SCAN_BYTES);
    size_t n = head != NULL ? fread(head, 1, TIME_SYNC_SCAN_BYTES, f) : 0;
    fclose(f);
    uint32_t result = 0;
    umi_log_reader_t reader;
    umi_header_t header;
    umi_record_t rec;
    if (n > 0 && umi_log_reader_open(&reader, head, n, &header) == UMI_LOG_RECORD) {
        while (umi_log_reader_next(&reader, &rec) == UMI_LOG_RECORD) {
            umi_time_sync_t sync;
            if (umi_time_sync_decode(&rec, &sync)) {
                result = (uint32_t)((sync.unix_ms - sync.t_ms) / 1000);
                break;
            }
        }
    }
    free(head);
    return result;
}

static int by_id(const void *a, const void *b)
{
    uint32_t x = ((const umi_esp32_session_info_t *)a)->session_id;
    uint32_t y = ((const umi_esp32_session_info_t *)b)->session_id;
    return x < y ? -1 : x > y;
}

size_t umi_esp32_storage_list(umi_esp32_storage_t *s, umi_esp32_session_info_t *out, size_t max)
{
    (void)s;
    DIR *dir = opendir(UMI_ESP32_SESSIONS_PATH);
    if (dir == NULL) {
        return 0;
    }
    size_t n = 0;
    struct dirent *entry;
    while (n < max && (entry = readdir(dir)) != NULL) {
        char *end;
        unsigned long id = strtoul(entry->d_name, &end, 16);
        if (strcmp(end, ".umis") != 0) {
            continue;
        }
        char path[PATH_MAX_LEN];
        session_path((uint32_t)id, path);
        struct stat st;
        if (stat(path, &st) != 0) {
            continue;
        }
        out[n++] = (umi_esp32_session_info_t){
            .session_id = (uint32_t)id,
            .size = (uint32_t)st.st_size,
            .first_unix_s = first_unix_s(path),
        };
    }
    closedir(dir);
    qsort(out, n, sizeof out[0], by_id);
    return n;
}

size_t umi_esp32_storage_pending(umi_esp32_storage_t *s)
{
    DIR *dir = opendir(UMI_ESP32_SESSIONS_PATH);
    if (dir == NULL) {
        return 0;
    }
    size_t n = 0;
    struct dirent *entry;
    while ((entry = readdir(dir)) != NULL) {
        char *end;
        unsigned long id = strtoul(entry->d_name, &end, 16);
        n += strcmp(end, ".umis") == 0 && !(s->file != NULL && id == s->open_id);
    }
    closedir(dir);
    return n;
}

esp_err_t umi_esp32_storage_delete(umi_esp32_storage_t *s, uint32_t session_id)
{
    if (s->file != NULL && s->open_id == session_id) {
        return ESP_ERR_INVALID_STATE;
    }
    char path[PATH_MAX_LEN];
    session_path(session_id, path);
    return unlink(path) == 0 ? ESP_OK : ESP_ERR_NOT_FOUND;
}
