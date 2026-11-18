/* Ambient temperature and relative humidity. */
#ifndef UMI_HAL_ENV_H
#define UMI_HAL_ENV_H

#include <stdbool.h>
#include <stdint.h>

typedef struct {
    uint32_t t_ms;
    float temp_c;
    float rh_pct;
} umi_env_reading_t;

typedef struct {
    bool (*poll)(void *ctx, umi_env_reading_t *out);
    void *ctx;
} umi_hal_env_t;

#endif /* UMI_HAL_ENV_H */
