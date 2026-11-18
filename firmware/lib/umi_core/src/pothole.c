#include "umi/core/pothole.h"

#include <math.h>

#include "umi/core/time.h"
#include "umi/protocol_gen.h"

#define SAMPLE_MS (1000u / UMI_RATES_IMU_HZ)
#define HALF_WINDOW_MS 500u

void umi_pothole_init(umi_pothole_t *p)
{
    *p = (umi_pothole_t){0};
}

void umi_pothole_update(umi_pothole_t *p, uint32_t t_ms, float vertical, float rms_1s)
{
    float magnitude = fabsf(vertical);
    bool loud = magnitude >= UMI_DETECTION_POTHOLE_RMS_MPS2;
    if (!loud) {
        p->quiet_last_ms = t_ms;
    }

    if (!p->candidate) {
        bool refractory = p->has_refractory && umi_time_before(t_ms, p->refractory_until_ms);
        if (!refractory && magnitude >= UMI_DETECTION_POTHOLE_PEAK_MPS2) {
            p->candidate = true;
            /* On a rough road the signal may never have been quiet: the shock
             * starts at most half a window before its peak. */
            uint32_t onset = p->quiet_last_ms + SAMPLE_MS;
            bool long_ago = umi_elapsed_ms(t_ms, onset) > HALF_WINDOW_MS;
            p->onset_ms = long_ago ? t_ms - HALF_WINDOW_MS : onset;
            p->peak_ms = t_ms;
            p->peak = magnitude;
            p->loud_last_ms = t_ms;
        }
        return;
    }

    if (loud) {
        p->loud_last_ms = t_ms;
    }
    if (magnitude > p->peak) {
        p->peak = magnitude;
    }
    if (umi_elapsed_ms(t_ms, p->peak_ms) < HALF_WINDOW_MS) {
        return;
    }
    p->candidate = false;
    if (rms_1s < UMI_DETECTION_POTHOLE_RMS_MPS2) {
        return;
    }
    p->has_refractory = true;
    p->refractory_until_ms = p->peak_ms + UMI_DETECTION_POTHOLE_REFRACTORY_MS;
    p->out = (umi_detection_t){
        .kind = UMI_EVENT_KIND_POTHOLE,
        .t_ms = p->onset_ms,
        .value_mps2 = rms_1s,
        .peak_mps2 = p->peak,
        .duration_ms = umi_elapsed_ms(p->loud_last_ms, p->onset_ms) + SAMPLE_MS,
    };
    p->ready = true;
}

bool umi_pothole_poll(umi_pothole_t *p, umi_detection_t *out)
{
    if (!p->ready) {
        return false;
    }
    p->ready = false;
    *out = p->out;
    return true;
}

bool umi_pothole_pending_since(const umi_pothole_t *p, uint32_t *t_ms)
{
    if (!p->candidate && !p->ready) {
        return false;
    }
    *t_ms = p->candidate ? p->onset_ms : p->out.t_ms;
    return true;
}
