#include "umi/drivers/esp32/clock.h"
#include "umi/drivers/esp32/sensors.h"
#include "umi/drivers/max17048.h"

#define I2C_HZ 400000
#define I2C_TIMEOUT_MS 20
/* The gauge updates every second; the battery moves over minutes. */
#define PERIOD_MS 10000u

esp_err_t umi_esp32_fuel_init(umi_esp32_fuel_t *f, i2c_master_bus_handle_t bus)
{
    *f = (umi_esp32_fuel_t){0};
    i2c_device_config_t dev = {
        .dev_addr_length = I2C_ADDR_BIT_LEN_7,
        .device_address = UMI_MAX17048_I2C_ADDR,
        .scl_speed_hz = I2C_HZ,
    };
    return i2c_master_bus_add_device(bus, &dev, &f->dev);
}

static bool read_register(umi_esp32_fuel_t *f, uint8_t reg, uint16_t *out)
{
    uint8_t raw[2];
    if (i2c_master_transmit_receive(f->dev, &reg, 1, raw, sizeof raw, I2C_TIMEOUT_MS) != ESP_OK) {
        return false;
    }
    *out = (uint16_t)(raw[0] << 8 | raw[1]);
    return true;
}

static bool poll(void *ctx, umi_battery_reading_t *out)
{
    umi_esp32_fuel_t *f = ctx;
    uint32_t now = umi_esp32_now_ms();
    if (f->read_once && now - f->read_ms < PERIOD_MS) {
        return false;
    }
    f->read_once = true;
    f->read_ms = now;
    uint16_t vcell, soc, crate;
    if (!read_register(f, UMI_MAX17048_REG_VCELL, &vcell) ||
        !read_register(f, UMI_MAX17048_REG_SOC, &soc) ||
        !read_register(f, UMI_MAX17048_REG_CRATE, &crate)) {
        return false;
    }
    *out = (umi_battery_reading_t){
        .mv = umi_max17048_mv(vcell),
        .pct = umi_max17048_pct(soc),
        /* Charging shows as a rising charge rate; the charger's STAT pin
         * would be more direct once the board routes it. */
        .charging = umi_max17048_crate_milli_pct_h(crate) > 0,
    };
    return true;
}

umi_hal_battery_t umi_esp32_fuel_hal(umi_esp32_fuel_t *f)
{
    return (umi_hal_battery_t){.poll = poll, .ctx = f};
}
