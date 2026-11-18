/* GNSS receiver: one fix per epoch (UMI_RATES_GNSS_HZ), already parsed. */
#ifndef UMI_HAL_GNSS_H
#define UMI_HAL_GNSS_H

#include <stdbool.h>
#include <stdint.h>

typedef struct {
    uint32_t t_ms; /* device time the epoch was received */
    uint8_t fix;   /* umi_fix_t; without a fix the position and motion fields are 0 */
    int32_t lat_e7;
    int32_t lon_e7;
    uint16_t speed_cms;
    uint16_t heading_cdeg; /* course over ground, 0-35999 */
    uint8_t hdop_d;        /* HDOP x 10, UMI_FORMAT_HDOP_UNKNOWN if not reported */
    uint8_t sats;
    bool has_utc;
    int64_t unix_ms; /* UTC of the epoch when has_utc */
} umi_gnss_fix_t;

typedef struct {
    /* Returns true and fills *out when a new epoch is available. */
    bool (*poll)(void *ctx, umi_gnss_fix_t *out);
    void *ctx;
} umi_hal_gnss_t;

#endif /* UMI_HAL_GNSS_H */
