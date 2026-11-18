/* What an IMU detector reports; the application adds the position. */
#ifndef UMI_CORE_DETECTION_H
#define UMI_CORE_DETECTION_H

#include <stdint.h>

typedef struct {
    uint8_t kind;      /* umi_event_kind_t */
    uint32_t t_ms;     /* device time the event started */
    float value_mps2;  /* mean deceleration (brake) or 1 s vertical RMS (pothole) */
    float peak_mps2;
    uint32_t duration_ms;
} umi_detection_t;

#endif /* UMI_CORE_DETECTION_H */
