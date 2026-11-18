/* Session storage: one .umis file per session, appended to while recording. */
#ifndef UMI_HAL_STORAGE_H
#define UMI_HAL_STORAGE_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

typedef struct {
    /* Hands out a session id never used before on this device (persisted). */
    bool (*next_session_id)(void *ctx, uint32_t *out);
    bool (*open)(void *ctx, uint32_t session_id);
    bool (*write)(void *ctx, const uint8_t *data, size_t len);
    /* Makes everything written so far survive a power loss. */
    bool (*flush)(void *ctx);
    bool (*close)(void *ctx);
    uint32_t (*free_kib)(void *ctx);
    void *ctx;
} umi_hal_storage_t;

#endif /* UMI_HAL_STORAGE_H */
