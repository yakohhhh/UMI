/* Device time on the ESP32-S3: milliseconds since boot from esp_timer. */
#ifndef UMI_DRIVERS_ESP32_CLOCK_H
#define UMI_DRIVERS_ESP32_CLOCK_H

#include <stdint.h>

#include "esp_timer.h"

static inline uint32_t umi_esp32_now_ms(void)
{
    return (uint32_t)(esp_timer_get_time() / 1000);
}

#endif /* UMI_DRIVERS_ESP32_CLOCK_H */
