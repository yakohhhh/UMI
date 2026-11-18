/* Particulate matter sensor (laser scattering), about one reading per second. */
#ifndef UMI_HAL_PM_H
#define UMI_HAL_PM_H

#include <stdbool.h>
#include <stdint.h>

typedef struct {
    uint32_t t_ms;
    uint16_t pm1_ugm3; /* mass concentrations, atmospheric environment, µg/m³ */
    uint16_t pm25_ugm3;
    uint16_t pm10_ugm3;
} umi_pm_reading_t;

typedef struct {
    bool (*poll)(void *ctx, umi_pm_reading_t *out);
    void *ctx;
} umi_hal_pm_t;

#endif /* UMI_HAL_PM_H */
