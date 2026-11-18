/* Session storage on the host file system for the SIL: the first session goes
 * to the requested path, later ones next to it as <stem>.<session_id>.umis. */
#ifndef UMI_SIL_HOST_STORAGE_H
#define UMI_SIL_HOST_STORAGE_H

#include <stdint.h>
#include <stdio.h>

#include "umi/hal/storage.h"

#define UMI_HOST_STORAGE_MAX_SESSIONS 16

typedef struct {
    const char *first_path;
    uint32_t next_id;
    FILE *file;
    uint32_t written;           /* bytes in all sessions, against the capacity */
    uint32_t capacity_kib;
    char paths[UMI_HOST_STORAGE_MAX_SESSIONS][512];
    unsigned session_count;
} umi_host_storage_t;

void umi_host_storage_init(umi_host_storage_t *s, const char *first_path, uint32_t first_id);
umi_hal_storage_t umi_host_storage_hal(umi_host_storage_t *s);

#endif /* UMI_SIL_HOST_STORAGE_H */
