#include "umi/drivers/esp32/clock.h"
#include "umi/drivers/esp32/sensors.h"
#include "umi/drivers/sht4x.h"
#include "umi/protocol_gen.h"

#define SHT40_ADDR 0x44
#define I2C_HZ 400000
#define I2C_TIMEOUT_MS 20
#define MEASURE_MS 10u /* high repeatability: 8.3 ms max */
/* Every AIR period: temperature and humidity move slowly. */
#define PERIOD_MS (UMI_RATES_AIR_PERIOD_S * 1000u)

esp_err_t umi_esp32_env_init(umi_esp32_env_t *e, i2c_master_bus_handle_t bus)
{
    *e = (umi_esp32_env_t){0};
    i2c_device_config_t dev = {
        .dev_addr_length = I2C_ADDR_BIT_LEN_7,
        .device_address = SHT40_ADDR,
        .scl_speed_hz = I2C_HZ,
    };
    return i2c_master_bus_add_device(bus, &dev, &e->dev);
}

/* Command, then read 10 ms later on a following poll: the core task never
 * waits on the bus. */
static bool poll(void *ctx, umi_env_reading_t *out)
{
    umi_esp32_env_t *e = ctx;
    uint32_t now = umi_esp32_now_ms();
    if (!e->measuring) {
        if (e->measured_once && now - e->command_ms < PERIOD_MS) {
            return false;
        }
        const uint8_t cmd = UMI_SHT4X_CMD_MEASURE_HIGH;
        e->measuring = i2c_master_transmit(e->dev, &cmd, 1, I2C_TIMEOUT_MS) == ESP_OK;
        e->command_ms = now;
        e->measured_once = true;
        return false;
    }
    if (now - e->command_ms < MEASURE_MS) {
        return false;
    }
    e->measuring = false;
    uint8_t raw[UMI_SHT4X_MEASURE_LEN];
    if (i2c_master_receive(e->dev, raw, sizeof raw, I2C_TIMEOUT_MS) != ESP_OK) {
        return false;
    }
    out->t_ms = now;
    return umi_sht4x_decode(raw, &out->temp_c, &out->rh_pct);
}

umi_hal_env_t umi_esp32_env_hal(umi_esp32_env_t *e)
{
    return (umi_hal_env_t){.poll = poll, .ctx = e};
}
