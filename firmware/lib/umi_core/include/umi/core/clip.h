/* The Clip application: polls every part through the HAL, runs the detectors,
 * the button gestures and the recorder, and drives the chirps and LED.
 *
 * Single-threaded by design: the target calls umi_clip_step from one task
 * every few milliseconds, the SIL calls it in simulated time, and both run
 * exactly the same logic. Other tasks (BLE) hand their requests to that task
 * instead of calling in concurrently. */
#ifndef UMI_CORE_CLIP_H
#define UMI_CORE_CLIP_H

#include <stdbool.h>
#include <stdint.h>

#include "umi/core/brake.h"
#include "umi/core/button.h"
#include "umi/core/ble_payloads.h"
#include "umi/core/feedback.h"
#include "umi/core/flags.h"
#include "umi/core/pothole.h"
#include "umi/core/recorder.h"
#include "umi/core/settings.h"
#include "umi/core/spl.h"
#include "umi/core/vibration.h"
#include "umi/core/warn_ahead.h"
#include "umi/hal/hal.h"

#define UMI_CLIP_IMU_CHUNK 32
#define UMI_CLIP_PCM_CHUNK 256

/* Counters for logs and bench checks; never written to the session. */
typedef struct {
    uint32_t flags;
    uint32_t undos;
    uint32_t events;
    uint32_t warnings;
    uint32_t sessions;
} umi_clip_stats_t;

typedef struct {
    umi_hal_t hal;
    umi_settings_t settings;

    umi_button_t button;
    umi_vibration_t vibration;
    umi_brake_t brake;
    umi_pothole_t pothole;
    umi_spl_t spl;
    umi_flags_t flags;
    umi_feedback_t feedback;
    umi_recorder_t recorder;
    umi_warn_ahead_t warn_ahead;

    umi_sensor_state_t sensors;
    umi_snapshot_t press_snapshot;
    uint32_t board_temp_read_ms;
    bool board_temp_read;

    bool voice_open;
    uint32_t voice_opened_ms;
    uint32_t voice_press_ms;
    umi_snapshot_t voice_snapshot;

    umi_clip_stats_t stats;
    umi_imu_sample_t imu_buf[UMI_CLIP_IMU_CHUNK];
    int32_t pcm_buf[UMI_CLIP_PCM_CHUNK];
} umi_clip_t;

void umi_clip_init(umi_clip_t *c, const umi_hal_t *hal, const umi_identity_t *identity,
                   const umi_settings_t *settings);

void umi_clip_step(umi_clip_t *c, uint32_t now_ms);

/* Power-off or end of a simulation: settles a pending voice flag and closes
 * the session with END. */
void umi_clip_shutdown(umi_clip_t *c, uint32_t now_ms);

void umi_clip_set_settings(umi_clip_t *c, const umi_settings_t *settings);

/* The phone's clock (BLE SET_TIME). */
void umi_clip_set_time(umi_clip_t *c, uint32_t now_ms, int64_t unix_ms);

/* Hazard list for warn-ahead, filled from BLE between HAZARDS_BEGIN and END. */
umi_warn_ahead_t *umi_clip_hazards(umi_clip_t *c);

/* Everything in Live Status except sessions_pending, which only storage knows. */
void umi_clip_live_status(const umi_clip_t *c, umi_live_status_t *out);

#endif /* UMI_CORE_CLIP_H */
