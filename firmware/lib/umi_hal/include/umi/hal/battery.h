/* Battery fuel gauge. */
#ifndef UMI_HAL_BATTERY_H
#define UMI_HAL_BATTERY_H

#include <stdbool.h>
#include <stdint.h>

typedef struct {
    uint16_t mv;
    uint8_t pct;
    bool charging;
} umi_battery_reading_t;

typedef struct {
    bool (*poll)(void *ctx, umi_battery_reading_t *out);
    void *ctx;
} umi_hal_battery_t;

#endif /* UMI_HAL_BATTERY_H */
