#include "umi/core/brake.h"

#include "umi/core/time.h"
#include "umi/protocol_gen.h"

/* The x baseline follows slope and mounting tilt (2 s low-pass) and freezes
 * while the rider decelerates, so a long brake is not absorbed into it. */
#define BASELINE_TAU_S 2.0f
#define BASELINE_ALPHA (1.0f / (BASELINE_TAU_S * (float)UMI_RATES_IMU_HZ))
#define FREEZE_MPS2 (UMI_DETECTION_HARD_BRAKE_MPS2 / 2.0f)
/* No bike decelerates hard for this long: past it the event is closed, which
 * also bounds how long the recorder holds records back. */
#define MAX_DURATION_MS 5000u
/* Share of the IMU speed loss the GNSS must see; GNSS speed is smoothed by
 * the receiver and sampled at 1 Hz, so it under-reads short brakes. */
#define GNSS_DROP_RATIO 0.5f
/* Longer than one GNSS period: past it the receiver is considered lost. */
#define GNSS_WAIT_MS 2000u
#define SAMPLE_MS (1000u / UMI_RATES_IMU_HZ)
/* The moving average reports a change (N - 1) / 2 samples late; events are
 * dated back by that much. */
#define SMOOTHING_DELAY_MS ((UMI_BRAKE_SMOOTHING - 1u) * SAMPLE_MS / 2u)

void umi_brake_init(umi_brake_t *b)
{
    *b = (umi_brake_t){.phase = UMI_BRAKE_IDLE};
}

static float smooth(umi_brake_t *b, float value)
{
    if (b->smooth_count == UMI_BRAKE_SMOOTHING) {
        b->smooth_sum -= b->smooth_buf[b->smooth_index];
    } else {
        b->smooth_count++;
    }
    b->smooth_buf[b->smooth_index] = value;
    b->smooth_sum += value;
    b->smooth_index = (uint8_t)((b->smooth_index + 1) % UMI_BRAKE_SMOOTHING);
    return b->smooth_sum / (float)b->smooth_count;
}

static void close_event(umi_brake_t *b)
{
    if (umi_elapsed_ms(b->last_ms, b->start_ms) + SAMPLE_MS >= UMI_DETECTION_HARD_BRAKE_MIN_MS) {
        b->phase = UMI_BRAKE_CONFIRMING;
    } else {
        b->phase = UMI_BRAKE_IDLE;
    }
}

void umi_brake_on_imu(umi_brake_t *b, const umi_imu_sample_t *s)
{
    if (!b->primed) {
        b->baseline_x = s->ax;
        b->primed = true;
    }
    float decel = smooth(b, b->baseline_x - s->ax);
    float raw_decel = b->baseline_x - s->ax;
    if (decel < FREEZE_MPS2) {
        b->baseline_x += BASELINE_ALPHA * (s->ax - b->baseline_x);
    }

    switch (b->phase) {
    case UMI_BRAKE_IDLE: {
        bool refractory = b->has_refractory && umi_time_before(s->t_ms, b->refractory_until_ms);
        if (!refractory && decel > UMI_DETECTION_HARD_BRAKE_MPS2) {
            b->phase = UMI_BRAKE_ACTIVE;
            b->start_ms = s->t_ms - SMOOTHING_DELAY_MS;
            b->last_ms = b->start_ms;
            b->decel_sum = decel;
            b->decel_n = 1;
            b->peak = raw_decel;
        }
        break;
    }
    case UMI_BRAKE_ACTIVE:
        if (decel > UMI_DETECTION_HARD_BRAKE_MPS2) {
            b->last_ms = s->t_ms - SMOOTHING_DELAY_MS;
            b->decel_sum += decel;
            b->decel_n++;
            if (raw_decel > b->peak) {
                b->peak = raw_decel;
            }
            if (umi_elapsed_ms(s->t_ms, b->start_ms) >= MAX_DURATION_MS) {
                close_event(b);
            }
        } else {
            close_event(b);
        }
        break;
    case UMI_BRAKE_CONFIRMING:
        break;
    }
}

void umi_brake_on_fix(umi_brake_t *b, const umi_gnss_fix_t *fix)
{
    if (fix->fix == UMI_FIX_NONE) {
        return;
    }
    b->fixes[b->fix_next] = (umi_brake_fix_t){fix->t_ms, fix->speed_cms};
    b->fix_next = (uint8_t)((b->fix_next + 1) % UMI_BRAKE_FIX_HISTORY);
    if (b->fix_count < UMI_BRAKE_FIX_HISTORY) {
        b->fix_count++;
    }
}

/* Latest fix at or before t, or first fix at or after t. */
static const umi_brake_fix_t *find_fix(const umi_brake_t *b, uint32_t t_ms, bool before)
{
    const umi_brake_fix_t *best = NULL;
    for (uint8_t i = 0; i < b->fix_count; i++) {
        const umi_brake_fix_t *f = &b->fixes[i];
        if (before) {
            if (!umi_time_before(t_ms, f->t_ms) &&
                (best == NULL || umi_time_before(best->t_ms, f->t_ms))) {
                best = f;
            }
        } else if (!umi_time_before(f->t_ms, t_ms) &&
                   (best == NULL || umi_time_before(f->t_ms, best->t_ms))) {
            best = f;
        }
    }
    return best;
}

bool umi_brake_poll(umi_brake_t *b, uint32_t now_ms, umi_detection_t *out)
{
    if (b->phase != UMI_BRAKE_CONFIRMING) {
        return false;
    }
    const umi_brake_fix_t *after = find_fix(b, b->last_ms, false);
    if (after == NULL && umi_elapsed_ms(now_ms, b->last_ms) < GNSS_WAIT_MS) {
        return false;
    }

    float mean = b->decel_sum / (float)b->decel_n;
    uint32_t duration_ms = umi_elapsed_ms(b->last_ms, b->start_ms) + SAMPLE_MS;
    const umi_brake_fix_t *before = find_fix(b, b->start_ms, true);
    bool confirmed = true;
    if (before != NULL && after != NULL) {
        float imu_drop_cms = mean * (float)duration_ms / 10.0f; /* m/s² x ms -> cm/s */
        float gnss_drop_cms = (float)before->speed_cms - (float)after->speed_cms;
        confirmed = gnss_drop_cms >= GNSS_DROP_RATIO * imu_drop_cms;
    }

    b->phase = UMI_BRAKE_IDLE;
    b->has_refractory = true;
    b->refractory_until_ms = b->last_ms + UMI_DETECTION_HARD_BRAKE_REFRACTORY_MS;
    if (!confirmed) {
        b->rejected++;
        return false;
    }
    *out = (umi_detection_t){
        .kind = UMI_EVENT_KIND_HARD_BRAKE,
        .t_ms = b->start_ms,
        .value_mps2 = mean,
        .peak_mps2 = b->peak,
        .duration_ms = duration_ms,
    };
    return true;
}

bool umi_brake_pending_since(const umi_brake_t *b, uint32_t *t_ms)
{
    if (b->phase == UMI_BRAKE_IDLE) {
        return false;
    }
    *t_ms = b->start_ms;
    return true;
}
