/* Hard-brake detector ([detection] hard_brake_*): longitudinal deceleration
 * above the threshold for at least hard_brake_min_ms, then a refractory period.
 *
 * The IMU decides, the GNSS confirms: once the deceleration ends, the event is
 * held until the next fix and dropped if the ground speed did not fall by at
 * least half of what the IMU integrated (a pothole or a knock on the Clip also
 * shakes the x axis, but does not slow the bike down). Without GNSS around the
 * event, the IMU alone decides. */
#ifndef UMI_CORE_BRAKE_H
#define UMI_CORE_BRAKE_H

#include <stdbool.h>
#include <stdint.h>

#include "umi/core/detection.h"
#include "umi/hal/gnss.h"
#include "umi/hal/imu.h"

#define UMI_BRAKE_SMOOTHING 10 /* samples (100 ms) of moving average against road shocks */
#define UMI_BRAKE_FIX_HISTORY 4

typedef enum {
    UMI_BRAKE_IDLE,
    UMI_BRAKE_ACTIVE,     /* decelerating above the threshold */
    UMI_BRAKE_CONFIRMING, /* ended, waiting for the GNSS cross-check */
} umi_brake_phase_t;

typedef struct {
    uint32_t t_ms;
    uint16_t speed_cms;
} umi_brake_fix_t;

typedef struct {
    float baseline_x; /* gravity and mounting tilt on the x axis */
    bool primed;
    float smooth_buf[UMI_BRAKE_SMOOTHING];
    float smooth_sum;
    uint8_t smooth_index;
    uint8_t smooth_count;

    umi_brake_phase_t phase;
    uint32_t start_ms;
    uint32_t last_ms;
    float decel_sum;
    uint32_t decel_n;
    float peak;
    bool has_refractory;
    uint32_t refractory_until_ms;

    umi_brake_fix_t fixes[UMI_BRAKE_FIX_HISTORY];
    uint8_t fix_count;
    uint8_t fix_next;

    uint32_t rejected; /* events the GNSS did not confirm, for diagnostics */
} umi_brake_t;

void umi_brake_init(umi_brake_t *b);
void umi_brake_on_imu(umi_brake_t *b, const umi_imu_sample_t *s);
void umi_brake_on_fix(umi_brake_t *b, const umi_gnss_fix_t *fix);

/* Returns a confirmed hard brake once the cross-check is settled. */
bool umi_brake_poll(umi_brake_t *b, uint32_t now_ms, umi_detection_t *out);

bool umi_brake_pending_since(const umi_brake_t *b, uint32_t *t_ms);

#endif /* UMI_CORE_BRAKE_H */
