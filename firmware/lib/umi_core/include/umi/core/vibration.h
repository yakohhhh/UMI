/* Vertical vibration: the acceleration along gravity with gravity removed, and
 * its RMS over the last second (SAMPLE.vib_mms2, the comfort score's input).
 *
 * Projecting on the tracked gravity vector instead of the z axis makes the
 * measure independent of how the Clip is tilted on the bike. */
#ifndef UMI_CORE_VIBRATION_H
#define UMI_CORE_VIBRATION_H

#include <stdbool.h>
#include <stdint.h>

#include "umi/hal/imu.h"
#include "umi/protocol_gen.h"

#define UMI_VIBRATION_WINDOW UMI_RATES_IMU_HZ /* one second of samples */

typedef struct {
    float gravity[3];
    bool primed;
    int32_t window_mms2[UMI_VIBRATION_WINDOW];
    uint64_t sum_sq; /* exact integer sum, so hours of updates never drift */
    uint16_t index;
    uint16_t count;
} umi_vibration_t;

void umi_vibration_init(umi_vibration_t *v);

/* Returns this sample's vertical acceleration with gravity removed, m/s². */
float umi_vibration_update(umi_vibration_t *v, const umi_imu_sample_t *s);

/* RMS of the last second, m/s²; covers fewer samples during the first second. */
float umi_vibration_rms(const umi_vibration_t *v);

/* True once a full second has been seen. */
bool umi_vibration_ready(const umi_vibration_t *v);

#endif /* UMI_CORE_VIBRATION_H */
