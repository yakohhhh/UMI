#include "umi/drivers/esp32/sensors.h"

esp_err_t umi_esp32_mic_init(umi_esp32_mic_t *m, gpio_num_t bclk, gpio_num_t ws, gpio_num_t sd,
                             uint32_t sample_rate_hz)
{
    i2s_chan_config_t chan = I2S_CHANNEL_DEFAULT_CONFIG(I2S_NUM_0, I2S_ROLE_MASTER);
    esp_err_t err = i2s_new_channel(&chan, NULL, &m->rx);
    if (err != ESP_OK) {
        return err;
    }
    i2s_std_config_t std = {
        .clk_cfg = I2S_STD_CLK_DEFAULT_CONFIG(sample_rate_hz),
        /* The ICS-43434 sends 24 bits left-justified in a 32-bit slot: read as
         * a 32-bit word it is already Q31, as the HAL wants. */
        .slot_cfg = I2S_STD_PHILIPS_SLOT_DEFAULT_CONFIG(I2S_DATA_BIT_WIDTH_32BIT, I2S_SLOT_MODE_MONO),
        .gpio_cfg = {
            .mclk = I2S_GPIO_UNUSED,
            .bclk = bclk,
            .ws = ws,
            .dout = I2S_GPIO_UNUSED,
            .din = sd,
        },
    };
    std.slot_cfg.slot_mask = I2S_STD_SLOT_LEFT; /* L/R pin tied low */
    err = i2s_channel_init_std_mode(m->rx, &std);
    return err == ESP_OK ? i2s_channel_enable(m->rx) : err;
}

static size_t read(void *ctx, int32_t *pcm, size_t max)
{
    umi_esp32_mic_t *m = ctx;
    size_t bytes = 0;
    /* Never blocks: whatever the DMA buffers hold right now. */
    i2s_channel_read(m->rx, pcm, max * sizeof pcm[0], &bytes, 0);
    return bytes / sizeof pcm[0];
}

umi_hal_mic_t umi_esp32_mic_hal(umi_esp32_mic_t *m, uint32_t sample_rate_hz)
{
    return (umi_hal_mic_t){.sample_rate_hz = sample_rate_hz, .read = read, .ctx = m};
}
