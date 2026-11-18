/* Session recorder: decides when a ride starts, pauses and stops ([detection]
 * motion_start_*, auto_pause_s, auto_stop_s) and writes the periodic records
 * ([rates]) to one .umis per session.
 *
 *   idle --moving for motion_start_s--> recording --still for auto_pause_s--> paused
 *   paused --moving--> recording         paused --still for auto_stop_s--> END, idle
 *
 * Records from other modules (events, flags) go through umi_recorder_push with
 * session-relative t_ms; everything is reordered (record_queue.h) and written
 * on umi_recorder_flush. */
#ifndef UMI_CORE_RECORDER_H
#define UMI_CORE_RECORDER_H

#include <stdbool.h>
#include <stdint.h>

#include "umi/core/air.h"
#include "umi/core/record_queue.h"
#include "umi/hal/battery.h"
#include "umi/hal/env.h"
#include "umi/hal/gnss.h"
#include "umi/hal/pm.h"
#include "umi/hal/storage.h"
#include "umi/session_log.h"

/* What goes into every session header. */
typedef struct {
    uint64_t device_id;
    uint8_t hw_rev;
    uint8_t fw_version[3];
    uint16_t header_flags; /* UMI_HEADER_FLAG_SIMULATED on simulated hardware */
    uint8_t activity;
} umi_identity_t;

/* Latest readings, kept current by the application and sampled by the recorder. */
typedef struct {
    bool has_fix;
    umi_gnss_fix_t fix;
    uint16_t vib_mms2;   /* 1 s RMS, or UMI_FORMAT_NOT_AVAILABLE_U16 */
    uint16_t noise_cdba; /* LAeq 1 s, or UMI_FORMAT_NOT_AVAILABLE_U16 */
    bool has_env;
    umi_env_reading_t env;
    bool has_battery;
    umi_battery_reading_t battery;
    bool has_board_temp;
    int16_t board_temp_cc;
} umi_sensor_state_t;

typedef enum {
    UMI_RECORDER_IDLE,
    UMI_RECORDER_RECORDING,
    UMI_RECORDER_PAUSED,
} umi_recorder_phase_t;

typedef enum {
    UMI_RECORDER_NO_CHANGE,
    UMI_RECORDER_STARTED,
    UMI_RECORDER_PAUSED_NOW,
    UMI_RECORDER_RESUMED,
    UMI_RECORDER_STOPPED,
} umi_recorder_change_t;

typedef struct {
    umi_identity_t identity;
    umi_hal_storage_t storage;
    umi_recorder_phase_t phase;

    bool moving;
    uint32_t moving_since_ms;
    bool still;
    uint32_t still_since_ms;

    uint32_t session_id;
    uint32_t start_ms; /* device time of t_ms = 0 */
    bool time_synced;
    uint32_t next_sample_t;
    uint32_t next_air_t;
    uint32_t next_status_t;
    uint32_t last_sync_ms;
    umi_air_acc_t air;
    umi_log_writer_t writer;
    umi_record_queue_t queue;

    uint32_t dropped; /* records lost to a full queue, bad ordering or storage */
} umi_recorder_t;

void umi_recorder_init(umi_recorder_t *r, const umi_identity_t *identity,
                       umi_hal_storage_t storage);

/* Runs the session state machine and the periodic records. */
umi_recorder_change_t umi_recorder_tick(umi_recorder_t *r, uint32_t now_ms,
                                        const umi_sensor_state_t *sensors);

/* A new GNSS epoch: the first one with UTC in a session writes TIME_SYNC. */
void umi_recorder_on_fix(umi_recorder_t *r, const umi_gnss_fix_t *fix);

/* The phone set the time (BLE SET_TIME): written as a TIME_SYNC too. */
void umi_recorder_on_time_set(umi_recorder_t *r, uint32_t now_ms, int64_t unix_ms);

void umi_recorder_add_pm(umi_recorder_t *r, const umi_pm_reading_t *reading);

/* Queues a record from another module; its t_ms is session-relative. */
void umi_recorder_push(umi_recorder_t *r, const umi_record_t *rec);

/* Writes every queued record dated at or before horizon_ms (device time). */
void umi_recorder_flush(umi_recorder_t *r, uint32_t horizon_ms);

/* Closes the session now: writes what is queued and the END record. */
void umi_recorder_stop(umi_recorder_t *r, uint32_t now_ms);

bool umi_recorder_in_session(const umi_recorder_t *r);

/* umi_status_flag_t bits for the current state (STATUS record, Live Status). */
uint8_t umi_recorder_status_flags(const umi_recorder_t *r, const umi_sensor_state_t *sensors);

/* Session-relative time of a device time; times before the start map to 0. */
uint32_t umi_recorder_session_ms(const umi_recorder_t *r, uint32_t device_ms);

#endif /* UMI_CORE_RECORDER_H */
