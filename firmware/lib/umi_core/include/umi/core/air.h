/* AIR record contents: PM readings averaged over the AIR period, PM2.5
 * corrected for humidity, and the latest temperature and humidity. */
#ifndef UMI_CORE_AIR_H
#define UMI_CORE_AIR_H

#include <stdbool.h>
#include <stdint.h>

#include "umi/hal/env.h"
#include "umi/hal/pm.h"
#include "umi/records.h"

typedef struct {
    uint32_t pm1_sum;
    uint32_t pm25_sum;
    uint32_t pm10_sum;
    uint16_t n;
} umi_air_acc_t;

void umi_air_reset(umi_air_acc_t *acc);
void umi_air_add(umi_air_acc_t *acc, const umi_pm_reading_t *r);

/* Laser counters see droplets swollen by humidity as larger particles. The
 * kappa-Koehler growth factor (Crilley et al. 2018, AMT 11, 709) shrinks the
 * reading back to dry mass. Kappa is site-dependent: to calibrate against the
 * Barcelona reference stations. */
float umi_pm25_dry(float pm25_ugm3, float rh_pct);

/* Builds an AIR record from the period's average (pm fields not available when
 * no reading arrived) and the latest environment reading (env may be NULL). */
void umi_air_make(const umi_air_acc_t *acc, const umi_env_reading_t *env, uint32_t t_ms,
                  umi_air_t *out);

#endif /* UMI_CORE_AIR_H */
