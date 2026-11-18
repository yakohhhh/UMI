/* What the rider hears and sees: a piezo on LEDC PWM and a WS2812 RGB LED on
 * RMT (the DevKitC-1's on-board LED; the Clip's LED part is to confirm). */
#ifndef UMI_DRIVERS_ESP32_INDICATORS_H
#define UMI_DRIVERS_ESP32_INDICATORS_H

#include <stdint.h>

#include "driver/gpio.h"
#include "driver/ledc.h"
#include "driver/rmt_tx.h"
#include "esp_err.h"
#include "umi/hal/buzzer.h"
#include "umi/hal/led.h"

typedef struct {
    ledc_channel_t channel;
    ledc_timer_t timer;
    uint16_t tone_hz;
} umi_esp32_buzzer_t;

esp_err_t umi_esp32_buzzer_init(umi_esp32_buzzer_t *b, gpio_num_t gpio);
umi_hal_buzzer_t umi_esp32_buzzer_hal(umi_esp32_buzzer_t *b);

typedef struct {
    rmt_channel_handle_t channel;
    rmt_encoder_handle_t encoder;
    uint8_t grb[3]; /* must outlive the asynchronous transmission */
} umi_esp32_led_t;

esp_err_t umi_esp32_led_init(umi_esp32_led_t *l, gpio_num_t gpio);
umi_hal_led_t umi_esp32_led_hal(umi_esp32_led_t *l);

#endif /* UMI_DRIVERS_ESP32_INDICATORS_H */
