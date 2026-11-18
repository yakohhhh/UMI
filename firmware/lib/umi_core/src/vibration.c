#include "umi/core/vibration.h"

#include <math.h>

/* Gravity is what is left after a 1 s low-pass: slow enough to ignore road
 * shocks, fast enough to follow the Clip tilting through a turn. */
#define GRAVITY_TAU_S 1.0f
#define GRAVITY_ALPHA (1.0f / (GRAVITY_TAU_S * (float)UMI_RATES_IMU_HZ))

void umi_vibration_init(umi_vibration_t *v)
{
    *v = (umi_vibration_t){0};
}

float umi_vibration_update(umi_vibration_t *v, const umi_imu_sample_t *s)
{
    const float a[3] = {s->ax, s->ay, s->az};
    if (!v->primed) {
        for (int i = 0; i < 3; i++) {
            v->gravity[i] = a[i];
        }
        v->primed = true;
    }
    for (int i = 0; i < 3; i++) {
        v->gravity[i] += GRAVITY_ALPHA * (a[i] - v->gravity[i]);
    }
    const float *g = v->gravity;
    float g_norm = sqrtf(g[0] * g[0] + g[1] * g[1] + g[2] * g[2]);
    float vertical = 0.0f;
    if (g_norm > 0.0f) {
        vertical = ((a[0] - g[0]) * g[0] + (a[1] - g[1]) * g[1] + (a[2] - g[2]) * g[2]) / g_norm;
    }

    int32_t mms2 = (int32_t)lroundf(vertical * 1000.0f);
    if (v->count == UMI_VIBRATION_WINDOW) {
        int64_t old = v->window_mms2[v->index];
        v->sum_sq -= (uint64_t)(old * old);
    } else {
        v->count++;
    }
    v->window_mms2[v->index] = mms2;
    v->sum_sq += (uint64_t)((int64_t)mms2 * mms2);
    v->index = (uint16_t)((v->index + 1) % UMI_VIBRATION_WINDOW);
    return vertical;
}

float umi_vibration_rms(const umi_vibration_t *v)
{
    if (v->count == 0) {
        return 0.0f;
    }
    return (float)sqrt((double)v->sum_sq / v->count) / 1000.0f;
}

bool umi_vibration_ready(const umi_vibration_t *v)
{
    return v->count == UMI_VIBRATION_WINDOW;
}
