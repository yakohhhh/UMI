#include "umi/drivers/esp32/clock.h"
#include "umi/drivers/esp32/sensors.h"
#include "umi/drivers/lsm6dso32.h"

#define I2C_HZ 400000
#define I2C_TIMEOUT_MS 20
#define WORD_LEN 7 /* tag + X, Y, Z little-endian */
#define SAMPLE_PERIOD_US (1000000 / UMI_LSM6DSO32_ODR_HZ)

static esp_err_t write_register(umi_esp32_imu_t *i, uint8_t reg, uint8_t value)
{
    const uint8_t buf[2] = {reg, value};
    return i2c_master_transmit(i->dev, buf, sizeof buf, I2C_TIMEOUT_MS);
}

static esp_err_t read_registers(umi_esp32_imu_t *i, uint8_t reg, uint8_t *out, size_t len)
{
    return i2c_master_transmit_receive(i->dev, &reg, 1, out, len, I2C_TIMEOUT_MS);
}

esp_err_t umi_esp32_imu_init(umi_esp32_imu_t *i, i2c_master_bus_handle_t bus)
{
    *i = (umi_esp32_imu_t){0};
    i2c_device_config_t dev = {
        .dev_addr_length = I2C_ADDR_BIT_LEN_7,
        .device_address = UMI_LSM6DSO32_I2C_ADDR,
        .scl_speed_hz = I2C_HZ,
    };
    esp_err_t err = i2c_master_bus_add_device(bus, &dev, &i->dev);
    uint8_t who = 0;
    if (err == ESP_OK) {
        err = read_registers(i, UMI_LSM6DSO32_WHO_AM_I, &who, 1);
    }
    if (err == ESP_OK && who != UMI_LSM6DSO32_WHO_AM_I_VALUE) {
        return ESP_ERR_NOT_FOUND;
    }
    const uint8_t setup[][2] = {
        {UMI_LSM6DSO32_CTRL3_C, UMI_LSM6DSO32_CTRL3_C_BDU_INC},
        {UMI_LSM6DSO32_CTRL1_XL, UMI_LSM6DSO32_CTRL1_XL_104HZ_8G},
        {UMI_LSM6DSO32_CTRL2_G, UMI_LSM6DSO32_CTRL2_G_104HZ_2000DPS},
        {UMI_LSM6DSO32_FIFO_CTRL3, UMI_LSM6DSO32_FIFO_CTRL3_104HZ},
        {UMI_LSM6DSO32_FIFO_CTRL4, UMI_LSM6DSO32_FIFO_CTRL4_CONTINUOUS},
    };
    for (size_t k = 0; err == ESP_OK && k < sizeof setup / sizeof setup[0]; k++) {
        err = write_register(i, setup[k][0], setup[k][1]);
    }
    return err;
}

static int16_t le16(const uint8_t *p)
{
    return (int16_t)(p[0] | p[1] << 8);
}

/* The FIFO interleaves gyro and accel words; a sample is emitted on each
 * accel word with the latest gyro. Samples are dated back from now at the
 * output data rate, the newest being now. The chip axes are taken as the body
 * frame until the mount orientation is known (assumptions checklist). */
static size_t read(void *ctx, umi_imu_sample_t *out, size_t max)
{
    umi_esp32_imu_t *i = ctx;
    uint8_t status[2];
    if (read_registers(i, UMI_LSM6DSO32_FIFO_STATUS1, status, sizeof status) != ESP_OK) {
        return 0;
    }
    size_t words = (size_t)(status[0] | (status[1] & 0x03) << 8);
    size_t n = 0;
    uint8_t word[WORD_LEN];
    int64_t now_us = esp_timer_get_time();
    for (size_t w = 0; w < words && n < max; w++) {
        if (read_registers(i, UMI_LSM6DSO32_FIFO_DATA_OUT_TAG, word, sizeof word) != ESP_OK) {
            break;
        }
        uint8_t tag = umi_lsm6dso32_tag(word[0]);
        if (tag == UMI_LSM6DSO32_TAG_GYRO) {
            for (int a = 0; a < 3; a++) {
                i->pending_gyro[a] = umi_lsm6dso32_gyro_rads(le16(word + 1 + 2 * a));
            }
        } else if (tag == UMI_LSM6DSO32_TAG_ACCEL) {
            out[n++] = (umi_imu_sample_t){
                .ax = umi_lsm6dso32_accel_mps2(le16(word + 1)),
                .ay = umi_lsm6dso32_accel_mps2(le16(word + 3)),
                .az = umi_lsm6dso32_accel_mps2(le16(word + 5)),
                .gx = i->pending_gyro[0],
                .gy = i->pending_gyro[1],
                .gz = i->pending_gyro[2],
            };
        }
    }
    for (size_t k = 0; k < n; k++) {
        out[k].t_ms = (uint32_t)((now_us - (int64_t)(n - 1 - k) * SAMPLE_PERIOD_US) / 1000);
    }
    return n;
}

umi_hal_imu_t umi_esp32_imu_hal(umi_esp32_imu_t *i)
{
    return (umi_hal_imu_t){.read = read, .ctx = i};
}
