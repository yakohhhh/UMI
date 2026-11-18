#include "umi/core/air.h"

#include <math.h>
#include <stddef.h>

#include "umi/protocol_gen.h"

#define KAPPA 0.38f
/* Past this the growth model diverges (it is singular at 100 %). */
#define RH_CAP_PCT 95.0f

/* The spec defines no "not available" value for signed fields; INT16_MIN
 * (-327.68 °C) cannot be a real temperature. */
#define TEMP_NOT_AVAILABLE INT16_MIN

void umi_air_reset(umi_air_acc_t *acc)
{
    *acc = (umi_air_acc_t){0};
}

void umi_air_add(umi_air_acc_t *acc, const umi_pm_reading_t *r)
{
    acc->pm1_sum += r->pm1_ugm3;
    acc->pm25_sum += r->pm25_ugm3;
    acc->pm10_sum += r->pm10_ugm3;
    acc->n++;
}

float umi_pm25_dry(float pm25_ugm3, float rh_pct)
{
    if (!(rh_pct > 0.0f)) {
        return pm25_ugm3;
    }
    float rh = (rh_pct < RH_CAP_PCT ? rh_pct : RH_CAP_PCT) / 100.0f;
    return pm25_ugm3 / (1.0f + KAPPA * rh / (1.0f - rh));
}

static uint16_t to_u16(float value)
{
    if (!(value >= 0.0f)) {
        return 0;
    }
    /* UMI_FORMAT_NOT_AVAILABLE_U16 is reserved, so saturate just below it. */
    return value >= (float)(UMI_FORMAT_NOT_AVAILABLE_U16 - 1) ? UMI_FORMAT_NOT_AVAILABLE_U16 - 1
                                                              : (uint16_t)lroundf(value);
}

void umi_air_make(const umi_air_acc_t *acc, const umi_env_reading_t *env, uint32_t t_ms,
                  umi_air_t *out)
{
    *out = (umi_air_t){
        .t_ms = t_ms,
        .pm1_dug = UMI_FORMAT_NOT_AVAILABLE_U16,
        .pm25_dug = UMI_FORMAT_NOT_AVAILABLE_U16,
        .pm10_dug = UMI_FORMAT_NOT_AVAILABLE_U16,
        .temp_cc = TEMP_NOT_AVAILABLE,
        .rh_dpct = UMI_FORMAT_NOT_AVAILABLE_U16,
    };
    if (env != NULL) {
        float cc = env->temp_c * 100.0f;
        /* A sensor fault could exceed the i16 range; INT16_MIN stays reserved. */
        out->temp_cc = cc >= 32767.0f ? 32767 : cc <= -32767.0f ? -32767 : (int16_t)lroundf(cc);
        out->rh_dpct = to_u16(env->rh_pct * 10.0f);
    }
    if (acc->n == 0) {
        return;
    }
    float n = (float)acc->n;
    float pm25 = (float)acc->pm25_sum / n;
    if (env != NULL) {
        pm25 = umi_pm25_dry(pm25, env->rh_pct);
    }
    out->pm1_dug = to_u16((float)acc->pm1_sum / n * 10.0f);
    out->pm25_dug = to_u16(pm25 * 10.0f);
    out->pm10_dug = to_u16((float)acc->pm10_sum / n * 10.0f);
}
