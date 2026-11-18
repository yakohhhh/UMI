/* Pothole detector ([detection] pothole_*): an impact peak at least
 * pothole_peak_mps2 inside a second whose vertical RMS reaches pothole_rms_mps2.
 *
 * The decision waits half a second after the peak so the RMS window is centred
 * on the impact; a lone spike (a knock on the Clip) has a high peak but a low
 * RMS and is ignored. */
#ifndef UMI_CORE_POTHOLE_H
#define UMI_CORE_POTHOLE_H

#include <stdbool.h>
#include <stdint.h>

#include "umi/core/detection.h"

typedef struct {
    bool candidate;
    uint32_t onset_ms;    /* first sample of the shock */
    uint32_t peak_ms;
    float peak;
    uint32_t loud_last_ms; /* last sample above the RMS threshold */
    uint32_t quiet_last_ms; /* last sample below it, to date the onset */
    bool has_refractory;
    uint32_t refractory_until_ms;
    bool ready;
    umi_detection_t out;
} umi_pothole_t;

void umi_pothole_init(umi_pothole_t *p);

/* vertical: this sample's vertical acceleration without gravity; rms_1s: the
 * vibration RMS of the second ending with this sample. */
void umi_pothole_update(umi_pothole_t *p, uint32_t t_ms, float vertical, float rms_1s);

bool umi_pothole_poll(umi_pothole_t *p, umi_detection_t *out);

bool umi_pothole_pending_since(const umi_pothole_t *p, uint32_t *t_ms);

#endif /* UMI_CORE_POTHOLE_H */
