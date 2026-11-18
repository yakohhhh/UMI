#include "umi/drivers/esp32/button.h"

#include "esp_attr.h"
#include "umi/drivers/esp32/clock.h"

/* Bounces arrive a few per press; the core drains this every 10 ms. */
#define EDGE_QUEUE_LEN 32

static void IRAM_ATTR on_edge(void *arg)
{
    umi_esp32_button_t *b = arg;
    bool level = gpio_get_level(b->gpio) != 0;
    umi_button_edge_t edge = {.t_ms = umi_esp32_now_ms(), .pressed = level != b->active_low};
    BaseType_t woken = pdFALSE;
    xQueueSendFromISR(b->edges, &edge, &woken);
    portYIELD_FROM_ISR(woken);
}

esp_err_t umi_esp32_button_init(umi_esp32_button_t *b, gpio_num_t gpio, bool active_low)
{
    b->gpio = gpio;
    b->active_low = active_low;
    b->edges = xQueueCreate(EDGE_QUEUE_LEN, sizeof(umi_button_edge_t));
    if (b->edges == NULL) {
        return ESP_ERR_NO_MEM;
    }
    gpio_config_t cfg = {
        .pin_bit_mask = 1ULL << gpio,
        .mode = GPIO_MODE_INPUT,
        .pull_up_en = active_low ? GPIO_PULLUP_ENABLE : GPIO_PULLUP_DISABLE,
        .pull_down_en = active_low ? GPIO_PULLDOWN_DISABLE : GPIO_PULLDOWN_ENABLE,
        .intr_type = GPIO_INTR_ANYEDGE,
    };
    esp_err_t err = gpio_config(&cfg);
    if (err != ESP_OK) {
        return err;
    }
    err = gpio_install_isr_service(0);
    if (err != ESP_OK && err != ESP_ERR_INVALID_STATE) { /* already installed is fine */
        return err;
    }
    return gpio_isr_handler_add(gpio, on_edge, b);
}

static bool poll(void *ctx, umi_button_edge_t *out)
{
    umi_esp32_button_t *b = ctx;
    return xQueueReceive(b->edges, out, 0) == pdTRUE;
}

umi_hal_button_t umi_esp32_button_hal(umi_esp32_button_t *b)
{
    return (umi_hal_button_t){.poll = poll, .ctx = b};
}
