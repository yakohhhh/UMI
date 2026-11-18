#include "umi/core/recorder.h"


#include "umi/core/time.h"
#include "umi/protocol_gen.h"

#define SAMPLE_PERIOD_MS (1000u / UMI_RATES_SAMPLE_HZ)
#define AIR_PERIOD_MS (UMI_RATES_AIR_PERIOD_S * 1000u)
#define STATUS_PERIOD_MS (UMI_RATES_STATUS_PERIOD_S * 1000u)
#define MOTION_START_MS (UMI_DETECTION_MOTION_START_S * 1000u)
#define AUTO_PAUSE_MS (UMI_DETECTION_AUTO_PAUSE_S * 1000u)
#define AUTO_STOP_MS (UMI_DETECTION_AUTO_STOP_S * 1000u)
#define MOTION_SPEED_CMS ((uint16_t)(UMI_DETECTION_MOTION_START_SPEED_KMH * 100000.0f / 3600.0f + 0.5f))

/* A fix older than two GNSS periods is gone (tunnel, indoors). */
#define FIX_STALE_MS (2500u / UMI_RATES_GNSS_HZ)
/* Without GNSS, a Clip this calm is lying still (a parked bike), not riding
 * through a tunnel. */
#define STILL_VIB_MMS2 300u
/* How often written data is made power-loss safe. */
#define STORAGE_SYNC_MS 10000u
#define LOW_BATTERY_PCT 15u
/* About nine hours of riding at ~110 KB per hour. */
#define STORAGE_LOW_KIB 1024u

typedef enum { MOTION_UNKNOWN, MOTION_MOVING, MOTION_STILL } motion_t;

void umi_recorder_init(umi_recorder_t *r, const umi_identity_t *identity,
                       umi_hal_storage_t storage)
{
    *r = (umi_recorder_t){.identity = *identity, .storage = storage, .phase = UMI_RECORDER_IDLE};
    umi_record_queue_init(&r->queue);
}

static bool fix_usable(const umi_sensor_state_t *s, uint32_t now_ms)
{
    return s->has_fix && s->fix.fix != UMI_FIX_NONE &&
           umi_elapsed_ms(now_ms, s->fix.t_ms) <= FIX_STALE_MS;
}

static motion_t classify(const umi_sensor_state_t *s, uint32_t now_ms)
{
    if (fix_usable(s, now_ms)) {
        return s->fix.speed_cms >= MOTION_SPEED_CMS ? MOTION_MOVING : MOTION_STILL;
    }
    if (s->vib_mms2 != UMI_FORMAT_NOT_AVAILABLE_U16 && s->vib_mms2 < STILL_VIB_MMS2) {
        return MOTION_STILL;
    }
    return MOTION_UNKNOWN;
}

static void track_motion(umi_recorder_t *r, motion_t motion, uint32_t now_ms)
{
    if (motion == MOTION_MOVING && !r->moving) {
        r->moving = true;
        r->moving_since_ms = now_ms;
    } else if (motion != MOTION_MOVING) {
        r->moving = false;
    }
    if (motion == MOTION_STILL && !r->still) {
        r->still = true;
        r->still_since_ms = now_ms;
    } else if (motion != MOTION_STILL) {
        r->still = false;
    }
}

uint32_t umi_recorder_session_ms(const umi_recorder_t *r, uint32_t device_ms)
{
    return umi_time_before(device_ms, r->start_ms) ? 0 : umi_elapsed_ms(device_ms, r->start_ms);
}

bool umi_recorder_in_session(const umi_recorder_t *r)
{
    return r->phase != UMI_RECORDER_IDLE;
}

static bool sink_write(void *ctx, const uint8_t *data, size_t len)
{
    umi_hal_storage_t *storage = ctx;
    return storage->write(storage->ctx, data, len);
}

static void write_record(umi_recorder_t *r, const umi_record_t *rec)
{
    if (!umi_log_writer_append(&r->writer, rec)) {
        r->dropped++;
    }
}

void umi_recorder_push(umi_recorder_t *r, const umi_record_t *rec)
{
    if (!umi_recorder_in_session(r)) {
        return;
    }
    umi_record_t oldest;
    if (!umi_record_queue_push(&r->queue, rec) && umi_record_queue_pop(&r->queue, &oldest)) {
        /* Only reachable if a producer holds records far longer than designed.
         * Writing the oldest keeps the log valid; a later record dated before
         * it is then refused by the writer and counted as dropped. */
        write_record(r, &oldest);
        umi_record_queue_push(&r->queue, rec);
    }
}

static void push_state(umi_recorder_t *r, uint32_t t_ms, uint8_t state)
{
    umi_record_t rec;
    umi_state_encode(&(umi_state_t){.t_ms = t_ms, .state = state}, &rec);
    umi_recorder_push(r, &rec);
}

static bool start_session(umi_recorder_t *r, uint32_t now_ms)
{
    uint32_t session_id;
    if (!r->storage.next_session_id(r->storage.ctx, &session_id) ||
        !r->storage.open(r->storage.ctx, session_id)) {
        return false;
    }
    umi_header_t header = {
        .flags = r->identity.header_flags,
        .device_id = r->identity.device_id,
        .session_id = session_id,
        .activity = r->identity.activity,
        .hw_rev = r->identity.hw_rev,
        .fw_version = {r->identity.fw_version[0], r->identity.fw_version[1],
                       r->identity.fw_version[2]},
    };
    umi_byte_sink_t sink = {.write = sink_write, .ctx = &r->storage};
    if (!umi_log_writer_begin(&r->writer, sink, &header)) {
        r->storage.close(r->storage.ctx);
        return false;
    }
    r->phase = UMI_RECORDER_RECORDING;
    r->session_id = session_id;
    r->start_ms = now_ms;
    r->time_synced = false;
    r->next_sample_t = SAMPLE_PERIOD_MS;
    r->next_air_t = AIR_PERIOD_MS;
    r->next_status_t = 0;
    r->last_sync_ms = now_ms;
    umi_air_reset(&r->air);
    umi_record_queue_init(&r->queue);
    push_state(r, 0, UMI_RECORDER_STATE_RECORDING);
    return true;
}

static uint16_t clamp_u16(uint32_t value)
{
    return value >= UMI_FORMAT_NOT_AVAILABLE_U16 ? UMI_FORMAT_NOT_AVAILABLE_U16 - 1
                                                 : (uint16_t)value;
}

static void push_sample(umi_recorder_t *r, uint32_t t_ms, uint32_t now_ms,
                        const umi_sensor_state_t *s)
{
    umi_sample_t sample = {
        .t_ms = t_ms,
        .vib_mms2 = s->vib_mms2,
        .noise_cdba = s->noise_cdba,
        .hdop_d = s->has_fix ? s->fix.hdop_d : UMI_FORMAT_HDOP_UNKNOWN,
        .fix = UMI_FIX_NONE,
        .sats = s->has_fix ? s->fix.sats : 0,
    };
    if (fix_usable(s, now_ms)) {
        sample.lat_e7 = s->fix.lat_e7;
        sample.lon_e7 = s->fix.lon_e7;
        sample.speed_cms = s->fix.speed_cms;
        sample.heading_cdeg = s->fix.heading_cdeg;
        sample.fix = s->fix.fix;
    }
    umi_record_t rec;
    umi_sample_encode(&sample, &rec);
    umi_recorder_push(r, &rec);
}

static void push_air(umi_recorder_t *r, uint32_t t_ms, const umi_sensor_state_t *s)
{
    umi_air_t air;
    umi_air_make(&r->air, s->has_env ? &s->env : NULL, t_ms, &air);
    umi_air_reset(&r->air);
    umi_record_t rec;
    umi_air_encode(&air, &rec);
    umi_recorder_push(r, &rec);
}

uint8_t umi_recorder_status_flags(const umi_recorder_t *r, const umi_sensor_state_t *sensors)
{
    uint8_t flags = 0;
    if (sensors->has_battery && sensors->battery.charging) {
        flags |= UMI_STATUS_FLAG_CHARGING;
    }
    if (sensors->has_battery && sensors->battery.pct < LOW_BATTERY_PCT) {
        flags |= UMI_STATUS_FLAG_LOW_BATTERY;
    }
    if (r->storage.free_kib(r->storage.ctx) < STORAGE_LOW_KIB) {
        flags |= UMI_STATUS_FLAG_STORAGE_LOW;
    }
    return flags;
}

static void push_status(umi_recorder_t *r, uint32_t t_ms, const umi_sensor_state_t *s)
{
    umi_status_t status = {
        .t_ms = t_ms,
        .flags = umi_recorder_status_flags(r, s),
        .board_temp_cc = s->has_board_temp ? s->board_temp_cc : INT16_MIN,
        .free_kib = clamp_u16(r->storage.free_kib(r->storage.ctx)),
    };
    if (s->has_battery) {
        status.battery_pct = s->battery.pct;
        status.battery_mv = s->battery.mv;
    }
    umi_record_t rec;
    umi_status_encode(&status, &rec);
    umi_recorder_push(r, &rec);
}

/* Next multiple of period strictly after t. */
static uint32_t next_slot(uint32_t t, uint32_t period)
{
    return (t / period + 1u) * period;
}

static void run_schedule(umi_recorder_t *r, uint32_t now_ms, const umi_sensor_state_t *s)
{
    uint32_t t = umi_recorder_session_ms(r, now_ms);
    /* One record per due slot; after a stall the schedule realigns instead of
     * bursting stale copies of the same readings. */
    if (r->phase == UMI_RECORDER_RECORDING && t >= r->next_sample_t) {
        push_sample(r, r->next_sample_t, now_ms, s);
        r->next_sample_t = next_slot(t, SAMPLE_PERIOD_MS);
    }
    if (t >= r->next_air_t) {
        push_air(r, r->next_air_t, s);
        r->next_air_t = next_slot(t, AIR_PERIOD_MS);
    }
    if (t >= r->next_status_t) {
        push_status(r, r->next_status_t, s);
        r->next_status_t = next_slot(t, STATUS_PERIOD_MS);
    }
}

umi_recorder_change_t umi_recorder_tick(umi_recorder_t *r, uint32_t now_ms,
                                        const umi_sensor_state_t *sensors)
{
    track_motion(r, classify(sensors, now_ms), now_ms);
    umi_recorder_change_t change = UMI_RECORDER_NO_CHANGE;

    switch (r->phase) {
    case UMI_RECORDER_IDLE:
        if (r->moving && umi_elapsed_ms(now_ms, r->moving_since_ms) >= MOTION_START_MS) {
            if (!start_session(r, now_ms)) {
                /* Storage refused: wait for another full motion window. */
                r->moving = false;
                return UMI_RECORDER_NO_CHANGE;
            }
            change = UMI_RECORDER_STARTED;
        }
        break;
    case UMI_RECORDER_RECORDING:
        if (r->still && umi_elapsed_ms(now_ms, r->still_since_ms) >= AUTO_PAUSE_MS) {
            r->phase = UMI_RECORDER_PAUSED;
            push_state(r, umi_recorder_session_ms(r, now_ms), UMI_RECORDER_STATE_AUTO_PAUSE);
            change = UMI_RECORDER_PAUSED_NOW;
        }
        break;
    case UMI_RECORDER_PAUSED:
        if (r->moving) {
            uint32_t t = umi_recorder_session_ms(r, now_ms);
            r->phase = UMI_RECORDER_RECORDING;
            r->next_sample_t = next_slot(t, SAMPLE_PERIOD_MS);
            push_state(r, t, UMI_RECORDER_STATE_RESUME);
            change = UMI_RECORDER_RESUMED;
        } else if (r->still && umi_elapsed_ms(now_ms, r->still_since_ms) >= AUTO_STOP_MS) {
            umi_recorder_stop(r, now_ms);
            return UMI_RECORDER_STOPPED;
        }
        break;
    }
    if (umi_recorder_in_session(r)) {
        run_schedule(r, now_ms, sensors);
    }
    return change;
}

static void push_time_sync(umi_recorder_t *r, uint32_t t_ms, int64_t unix_ms)
{
    umi_record_t rec;
    umi_time_sync_encode(&(umi_time_sync_t){.t_ms = t_ms, .unix_ms = unix_ms}, &rec);
    umi_recorder_push(r, &rec);
    r->time_synced = true;
}

void umi_recorder_on_fix(umi_recorder_t *r, const umi_gnss_fix_t *fix)
{
    if (umi_recorder_in_session(r) && !r->time_synced && fix->fix != UMI_FIX_NONE &&
        fix->has_utc) {
        push_time_sync(r, umi_recorder_session_ms(r, fix->t_ms), fix->unix_ms);
    }
}

void umi_recorder_on_time_set(umi_recorder_t *r, uint32_t now_ms, int64_t unix_ms)
{
    if (umi_recorder_in_session(r)) {
        push_time_sync(r, umi_recorder_session_ms(r, now_ms), unix_ms);
    }
}

void umi_recorder_add_pm(umi_recorder_t *r, const umi_pm_reading_t *reading)
{
    umi_air_add(&r->air, reading);
}

static void sync_storage(umi_recorder_t *r, uint32_t now_ms)
{
    if (umi_elapsed_ms(now_ms, r->last_sync_ms) >= STORAGE_SYNC_MS) {
        r->storage.flush(r->storage.ctx);
        r->last_sync_ms = now_ms;
    }
}

void umi_recorder_flush(umi_recorder_t *r, uint32_t horizon_ms)
{
    if (!umi_recorder_in_session(r) || umi_time_before(horizon_ms, r->start_ms)) {
        return;
    }
    uint32_t horizon_t = umi_recorder_session_ms(r, horizon_ms);
    umi_record_t rec;
    while (umi_record_queue_pop_until(&r->queue, horizon_t, &rec)) {
        write_record(r, &rec);
    }
    sync_storage(r, horizon_ms);
}

void umi_recorder_stop(umi_recorder_t *r, uint32_t now_ms)
{
    if (!umi_recorder_in_session(r)) {
        return;
    }
    umi_record_t rec;
    while (umi_record_queue_pop(&r->queue, &rec)) {
        write_record(r, &rec);
    }
    umi_log_writer_finish(&r->writer, umi_recorder_session_ms(r, now_ms));
    r->storage.flush(r->storage.ctx);
    r->storage.close(r->storage.ctx);
    r->phase = UMI_RECORDER_IDLE;
    r->moving = false;
    r->still = false;
}
