#include "host_storage.h"

#include <string.h>

/* Same capacity as the Clip's "sessions" partition (partitions.csv), so the
 * STATUS records of a SIL run look like the device's. */
#define SESSIONS_PARTITION_KIB 10112u

void umi_host_storage_init(umi_host_storage_t *s, const char *first_path, uint32_t first_id)
{
    *s = (umi_host_storage_t){
        .first_path = first_path,
        .next_id = first_id,
        .capacity_kib = SESSIONS_PARTITION_KIB,
    };
}

static bool next_session_id(void *ctx, uint32_t *out)
{
    umi_host_storage_t *s = ctx;
    *out = s->next_id++;
    return true;
}

static void session_path(const umi_host_storage_t *s, uint32_t session_id, char *out, size_t cap)
{
    if (s->session_count == 0) {
        snprintf(out, cap, "%s", s->first_path);
        return;
    }
    const char *dot = strrchr(s->first_path, '.');
    const char *slash = strrchr(s->first_path, '/');
    size_t stem = dot != NULL && (slash == NULL || dot > slash) ? (size_t)(dot - s->first_path)
                                                                : strlen(s->first_path);
    snprintf(out, cap, "%.*s.%u.umis", (int)stem, s->first_path, (unsigned)session_id);
}

static bool open_session(void *ctx, uint32_t session_id)
{
    umi_host_storage_t *s = ctx;
    if (s->file != NULL || s->session_count == UMI_HOST_STORAGE_MAX_SESSIONS) {
        return false;
    }
    char *path = s->paths[s->session_count];
    session_path(s, session_id, path, sizeof s->paths[0]);
    s->file = fopen(path, "wb");
    if (s->file == NULL) {
        return false;
    }
    s->session_count++;
    return true;
}

static bool write_bytes(void *ctx, const uint8_t *data, size_t len)
{
    umi_host_storage_t *s = ctx;
    if (s->file == NULL || fwrite(data, 1, len, s->file) != len) {
        return false;
    }
    s->written += (uint32_t)len;
    return true;
}

static bool flush(void *ctx)
{
    umi_host_storage_t *s = ctx;
    return s->file != NULL && fflush(s->file) == 0;
}

static bool close_session(void *ctx)
{
    umi_host_storage_t *s = ctx;
    if (s->file == NULL) {
        return false;
    }
    bool ok = fclose(s->file) == 0;
    s->file = NULL;
    return ok;
}

static uint32_t free_kib(void *ctx)
{
    umi_host_storage_t *s = ctx;
    uint32_t used_kib = s->written / 1024u;
    return used_kib >= s->capacity_kib ? 0 : s->capacity_kib - used_kib;
}

umi_hal_storage_t umi_host_storage_hal(umi_host_storage_t *s)
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
