#include "umi/drivers/esp32/indicators.h"

#define BUZZER_MODE LEDC_LOW_SPEED_MODE
#define BUZZER_RESOLUTION LEDC_TIMER_10_BIT
#define BUZZER_HALF_DUTY (1u << (BUZZER_RESOLUTION - 1)) /* square wave: loudest on a piezo */

/* WS2812 timing at a 10 MHz RMT tick: 0 = 0.3/0.9 µs, 1 = 0.9/0.3 µs. */
#define LED_RESOLUTION_HZ 10000000u
/* An LED at full power is glaring at night and costs ~20 mA. */
#define LED_BRIGHTNESS_SHIFT 2

esp_err_t umi_esp32_buzzer_init(umi_esp32_buzzer_t *b, gpio_num_t gpio)
{
    *b = (umi_esp32_buzzer_t){.channel = LEDC_CHANNEL_0, .timer = LEDC_TIMER_0};
    ledc_timer_config_t timer = {
        .speed_mode = BUZZER_MODE,
        .duty_resolution = BUZZER_RESOLUTION,
        .timer_num = b->timer,
        .freq_hz = 2000,
        .clk_cfg = LEDC_AUTO_CLK,
    };
    esp_err_t err = ledc_timer_config(&timer);
    if (err != ESP_OK) {
        return err;
    }
    ledc_channel_config_t channel = {
        .gpio_num = gpio,
        .speed_mode = BUZZER_MODE,
        .channel = b->channel,
        .timer_sel = b->timer,
        .duty = 0,
        .hpoint = 0,
    };
    return ledc_channel_config(&channel);
}

static void tone(void *ctx, uint16_t hz)
{
    umi_esp32_buzzer_t *b = ctx;
    if (hz == b->tone_hz) {
        return;
    }
    b->tone_hz = hz;
    if (hz != 0) {
        ledc_set_freq(BUZZER_MODE, b->timer, hz);
    }
    ledc_set_duty(BUZZER_MODE, b->channel, hz != 0 ? BUZZER_HALF_DUTY : 0);
    ledc_update_duty(BUZZER_MODE, b->channel);
}

umi_hal_buzzer_t umi_esp32_buzzer_hal(umi_esp32_buzzer_t *b)
{
    return (umi_hal_buzzer_t){.tone = tone, .ctx = b};
}

esp_err_t umi_esp32_led_init(umi_esp32_led_t *l, gpio_num_t gpio)
{
    rmt_tx_channel_config_t channel = {
        .gpio_num = gpio,
        .clk_src = RMT_CLK_SRC_DEFAULT,
        .resolution_hz = LED_RESOLUTION_HZ,
        .mem_block_symbols = 48,
        .trans_queue_depth = 4,
    };
    esp_err_t err = rmt_new_tx_channel(&channel, &l->channel);
    if (err != ESP_OK) {
        return err;
    }
    rmt_bytes_encoder_config_t encoder = {
        .bit0 = {.level0 = 1, .duration0 = 3, .level1 = 0, .duration1 = 9},
        .bit1 = {.level0 = 1, .duration0 = 9, .level1 = 0, .duration1 = 3},
        .flags.msb_first = 1,
    };
    err = rmt_new_bytes_encoder(&encoder, &l->encoder);
    if (err != ESP_OK) {
        return err;
    }
    return rmt_enable(l->channel);
}

static void set(void *ctx, umi_led_color_t color)
{
    umi_esp32_led_t *l = ctx;
    /* The product's signal orange, #FF5B1F, in the LED's GRB order. */
    const uint8_t orange_grb[3] = {0x5B, 0xFF, 0x1F};
    for (int i = 0; i < 3; i++) {
        l->grb[i] = color == UMI_LED_ORANGE ? (uint8_t)(orange_grb[i] >> LED_BRIGHTNESS_SHIFT) : 0;
    }
    rmt_transmit_config_t tx = {.loop_count = 0};
    rmt_transmit(l->channel, l->encoder, l->grb, sizeof l->grb, &tx);
}

umi_hal_led_t umi_esp32_led_hal(umi_esp32_led_t *l)
{
    return (umi_hal_led_t){.set = set, .ctx = l};
}
