/* 6-axis IMU at UMI_RATES_IMU_HZ. Body frame: x forward, y left, z up. */
#ifndef UMI_HAL_IMU_H
#define UMI_HAL_IMU_H

#include <stddef.h>
#include <stdint.h>

typedef struct {
    uint32_t t_ms; /* device time of the measurement */
    float ax, ay, az; /* m/s², gravity included (az ≈ +9.81 at rest) */
    float gx, gy, gz; /* rad/s */
} umi_imu_sample_t;

typedef struct {
    /* Copies up to max samples measured since the previous call, oldest first. */
    size_t (*read)(void *ctx, umi_imu_sample_t *out, size_t max);
    void *ctx;
} umi_hal_imu_t;

#endif /* UMI_HAL_IMU_H */
