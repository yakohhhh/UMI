/* Flag button on a GPIO: an interrupt on every edge queues (time, level), so
 * bounces reach the core's debouncer exactly as they happened. */
#ifndef UMI_DRIVERS_ESP32_BUTTON_H
#define UMI_DRIVERS_ESP32_BUTTON_H

#include <stdbool.h>

#include "driver/gpio.h"
#include "esp_err.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "umi/hal/button.h"

typedef struct {
    gpio_num_t gpio;
    bool active_low;
    QueueHandle_t edges;
} umi_esp32_button_t;

/* active_low: pressed pulls the line to ground (internal pull-up enabled). */
esp_err_t umi_esp32_button_init(umi_esp32_button_t *b, gpio_num_t gpio, bool active_low);
umi_hal_button_t umi_esp32_button_hal(umi_esp32_button_t *b);

#endif /* UMI_DRIVERS_ESP32_BUTTON_H */
