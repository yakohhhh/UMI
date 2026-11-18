/* ST LSM6DSO32 register map and sample decoding (pure C). Configuration used
 * by the Clip: accelerometer ±8 g and gyroscope ±2000 dps at 104 Hz (the part
 * has no 100 Hz rate), both batched into the FIFO in continuous mode. */
#ifndef UMI_DRIVERS_LSM6DSO32_H
#define UMI_DRIVERS_LSM6DSO32_H

#include <stdint.h>

#define UMI_LSM6DSO32_I2C_ADDR 0x6A /* SDO/SA0 low; 0x6B when high */
#define UMI_LSM6DSO32_WHO_AM_I_VALUE 0x6C

enum {
    UMI_LSM6DSO32_FIFO_CTRL3 = 0x09,
    UMI_LSM6DSO32_FIFO_CTRL4 = 0x0A,
    UMI_LSM6DSO32_WHO_AM_I = 0x0F,
    UMI_LSM6DSO32_CTRL1_XL = 0x10,
    UMI_LSM6DSO32_CTRL2_G = 0x11,
    UMI_LSM6DSO32_CTRL3_C = 0x12,
    UMI_LSM6DSO32_FIFO_STATUS1 = 0x3A,
    UMI_LSM6DSO32_FIFO_DATA_OUT_TAG = 0x78,
};

#define UMI_LSM6DSO32_CTRL1_XL_104HZ_8G 0x48  /* ODR 0100, FS_XL 10 (±8 g on the -32 part) */
#define UMI_LSM6DSO32_CTRL2_G_104HZ_2000DPS 0x4C
#define UMI_LSM6DSO32_CTRL3_C_BDU_INC 0x44     /* block data update, register auto-increment */
#define UMI_LSM6DSO32_FIFO_CTRL3_104HZ 0x44    /* batch both sensors at 104 Hz */
#define UMI_LSM6DSO32_FIFO_CTRL4_CONTINUOUS 0x06
#define UMI_LSM6DSO32_ODR_HZ 104

/* FIFO word tags (bits 7..3 of FIFO_DATA_OUT_TAG). */
#define UMI_LSM6DSO32_TAG_GYRO 0x01
#define UMI_LSM6DSO32_TAG_ACCEL 0x02

static inline uint8_t umi_lsm6dso32_tag(uint8_t tag_register)
{
    return (uint8_t)(tag_register >> 3);
}

/* ±8 g: 0.244 mg per LSB. */
static inline float umi_lsm6dso32_accel_mps2(int16_t raw)
{
    return (float)raw * 0.244e-3f * 9.80665f;
}

/* ±2000 dps: 70 mdps per LSB. */
static inline float umi_lsm6dso32_gyro_rads(int16_t raw)
{
    return (float)raw * 70e-3f * 0.0174532925f;
}

#endif /* UMI_DRIVERS_LSM6DSO32_H */
