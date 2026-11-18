#include "umi/drivers/esp32/board.h"

#include <math.h>

esp_err_t umi_esp32_board_init(umi_esp32_board_t *b)
{
    /* The range a Clip on a handlebar sees, Barcelona winter night to summer sun. */
    temperature_sensor_config_t cfg = TEMPERATURE_SENSOR_CONFIG_DEFAULT(-10, 80);
    esp_err_t err = temperature_sensor_install(&cfg, &b->sensor);
    return err == ESP_OK ? temperature_sensor_enable(b->sensor) : err;
}

static bool temp_cc(void *ctx, int16_t *out)
{
    umi_esp32_board_t *b = ctx;
    float celsius;
    if (temperature_sensor_get_celsius(b->sensor, &celsius) != ESP_OK) {
        return false;
    }
    *out = (int16_t)lroundf(celsius * 100.0f);
    return true;
}

umi_hal_board_t umi_esp32_board_hal(umi_esp32_board_t *b)
{
    return (umi_hal_board_t){.temp_cc = temp_cc, .ctx = b};
}
