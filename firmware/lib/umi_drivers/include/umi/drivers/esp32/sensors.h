/* Real sensor drivers of the Clip board. Written against the datasheets of the
 * assumed parts (docs/hardware/assumptions.md) and compile-tested only: each
 * is to be validated on the board when the order arrives. */
#ifndef UMI_DRIVERS_ESP32_SENSORS_H
#define UMI_DRIVERS_ESP32_SENSORS_H

#include <stdbool.h>
#include <stdint.h>

#include "driver/gpio.h"
#include "driver/i2c_master.h"
#include "driver/i2s_std.h"
#include "driver/uart.h"
#include "esp_err.h"
#include "umi/drivers/nmea.h"
#include "umi/drivers/pms.h"
#include "umi/hal/hal.h"

/* GNSS receiver on a UART (u-blox, NMEA output). */
typedef struct {
    uart_port_t port;
    umi_nmea_t nmea;
    uint8_t buf[128];
    size_t len;
    size_t pos;
} umi_esp32_gnss_t;

esp_err_t umi_esp32_gnss_init(umi_esp32_gnss_t *g, uart_port_t port, gpio_num_t tx, gpio_num_t rx,
                              int baud);
umi_hal_gnss_t umi_esp32_gnss_hal(umi_esp32_gnss_t *g);

/* Plantower PMSA003 on a UART, active mode. */
typedef struct {
    uart_port_t port;
    umi_pms_t pms;
} umi_esp32_pm_t;

esp_err_t umi_esp32_pm_init(umi_esp32_pm_t *p, uart_port_t port, gpio_num_t tx, gpio_num_t rx);
umi_hal_pm_t umi_esp32_pm_hal(umi_esp32_pm_t *p);

/* ICS-43434 on I2S, left slot, 24 bits in 32-bit words. */
typedef struct {
    i2s_chan_handle_t rx;
} umi_esp32_mic_t;

esp_err_t umi_esp32_mic_init(umi_esp32_mic_t *m, gpio_num_t bclk, gpio_num_t ws, gpio_num_t sd,
                             uint32_t sample_rate_hz);
umi_hal_mic_t umi_esp32_mic_hal(umi_esp32_mic_t *m, uint32_t sample_rate_hz);

/* SHT40 on I2C: one non-blocking measurement every period. */
typedef struct {
    i2c_master_dev_handle_t dev;
    bool measuring;
    bool measured_once;
    uint32_t command_ms;
} umi_esp32_env_t;

esp_err_t umi_esp32_env_init(umi_esp32_env_t *e, i2c_master_bus_handle_t bus);
umi_hal_env_t umi_esp32_env_hal(umi_esp32_env_t *e);

/* MAX17048 fuel gauge on I2C. */
typedef struct {
    i2c_master_dev_handle_t dev;
    bool read_once;
    uint32_t read_ms;
} umi_esp32_fuel_t;

esp_err_t umi_esp32_fuel_init(umi_esp32_fuel_t *f, i2c_master_bus_handle_t bus);
umi_hal_battery_t umi_esp32_fuel_hal(umi_esp32_fuel_t *f);

/* LSM6DSO32 on I2C, read from its FIFO. */
typedef struct {
    i2c_master_dev_handle_t dev;
    float pending_gyro[3];
} umi_esp32_imu_t;

esp_err_t umi_esp32_imu_init(umi_esp32_imu_t *i, i2c_master_bus_handle_t bus);
umi_hal_imu_t umi_esp32_imu_hal(umi_esp32_imu_t *i);

/* Keyword recogniser: blocked on hardware (see keyword.c). */
umi_hal_keyword_t umi_esp32_keyword_hal(void);

#endif /* UMI_DRIVERS_ESP32_SENSORS_H */
