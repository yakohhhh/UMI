#include "umi/core/clip.h"

#include <math.h>

#include "umi/core/time.h"
#include "umi/protocol_gen.h"

/* The SoC temperature moves slowly and STATUS is every 60 s. */
#define BOARD_TEMP_PERIOD_MS 10000u
/* Same freshness rule as the recorder's: older fixes are not a position. */
#define FIX_FRESH_MS 2500u
/* Detectors date an event at its onset, recognised only later (a pothole up
 * to half a second after its first shock), so records are held back this long
 * on top of what producers report as pending. */
#define RECORD_SETTLE_MS 1000u

void umi_clip_init(umi_clip_t *c, const umi_hal_t *hal, const umi_identity_t *identity,
                   const umi_settings_t *settings)
{
    *c = (umi_clip_t){.hal = *hal, .settings = *settings};
    umi_button_init(&c->button);
    umi_vibration_init(&c->vibration);
    umi_brake_init(&c->brake);
    umi_pothole_init(&c->pothole);
    umi_spl_init(&c->spl, hal->mic.sample_rate_hz, 0.0f);
    umi_flags_init(&c->flags, hal->signer, identity->device_id);
    umi_feedback_init(&c->feedback, hal->buzzer, hal->led);
    umi_recorder_init(&c->recorder, identity, hal->storage);
    umi_warn_ahead_init(&c->warn_ahead);
    c->sensors.vib_mms2 = UMI_FORMAT_NOT_AVAILABLE_U16;
    c->sensors.noise_cdba = UMI_FORMAT_NOT_AVAILABLE_U16;
}

void umi_clip_set_settings(umi_clip_t *c, const umi_settings_t *settings)
{
    c->settings = *settings;
}

umi_warn_ahead_t *umi_clip_hazards(umi_clip_t *c)
{
    return &c->warn_ahead;
}

static bool fix_fresh(const umi_clip_t *c, uint32_t now_ms)
{
    return c->sensors.has_fix && c->sensors.fix.fix != UMI_FIX_NONE &&
           umi_elapsed_ms(now_ms, c->sensors.fix.t_ms) <= FIX_FRESH_MS;
}

static umi_snapshot_t snapshot(const umi_clip_t *c, uint32_t now_ms)
{
    umi_snapshot_t s = {.vib_mms2 = c->sensors.vib_mms2, .noise_cdba = c->sensors.noise_cdba};
    if (fix_fresh(c, now_ms)) {
        s.lat_e7 = c->sensors.fix.lat_e7;
        s.lon_e7 = c->sensors.fix.lon_e7;
        s.speed_cms = c->sensors.fix.speed_cms;
    }
    return s;
}

static uint16_t to_mms2(float mps2)
{
    float v = mps2 * 1000.0f;
    return v >= (float)(UMI_FORMAT_NOT_AVAILABLE_U16 - 1) ? UMI_FORMAT_NOT_AVAILABLE_U16 - 1
                                                          : (uint16_t)lroundf(v > 0.0f ? v : 0.0f);
}

/* ---------------------------------------------------------------- sensors */

static void read_imu(umi_clip_t *c)
{
    size_t n;
    do {
        n = c->hal.imu.read(c->hal.imu.ctx, c->imu_buf, UMI_CLIP_IMU_CHUNK);
        for (size_t i = 0; i < n; i++) {
            const umi_imu_sample_t *s = &c->imu_buf[i];
            float vertical = umi_vibration_update(&c->vibration, s);
            umi_pothole_update(&c->pothole, s->t_ms, vertical, umi_vibration_rms(&c->vibration));
            umi_brake_on_imu(&c->brake, s);
        }
    } while (n == UMI_CLIP_IMU_CHUNK);
    c->sensors.vib_mms2 = umi_vibration_ready(&c->vibration)
                              ? to_mms2(umi_vibration_rms(&c->vibration))
                              : UMI_FORMAT_NOT_AVAILABLE_U16;
}

static void warn_ahead(umi_clip_t *c, uint32_t now_ms, const umi_gnss_fix_t *fix)
{
    /* A confirmation in progress wins; the hazard is checked again next fix. */
    if (!c->settings.warn_ahead || !umi_recorder_in_session(&c->recorder) ||
        umi_feedback_playing(&c->feedback)) {
        return;
    }
    umi_hazard_t hazard;
    if (umi_warn_ahead_check(&c->warn_ahead, now_ms, fix, &hazard)) {
        c->stats.warnings++;
        umi_feedback_play(&c->feedback, UMI_FEEDBACK_WARN_AHEAD, false, now_ms);
    }
}

static void read_gnss(umi_clip_t *c, uint32_t now_ms)
{
    umi_gnss_fix_t fix;
    while (c->hal.gnss.poll(c->hal.gnss.ctx, &fix)) {
        c->sensors.fix = fix;
        c->sensors.has_fix = true;
        umi_brake_on_fix(&c->brake, &fix);
        umi_recorder_on_fix(&c->recorder, &fix);
        warn_ahead(c, now_ms, &fix);
    }
}

static void read_air(umi_clip_t *c)
{
    bool enabled = (c->settings.sensors & UMI_SENSOR_AIR) != 0;
    umi_pm_reading_t pm;
    while (c->hal.pm.poll(c->hal.pm.ctx, &pm)) {
        if (enabled) {
            umi_recorder_add_pm(&c->recorder, &pm);
        }
    }
    umi_env_reading_t env;
    while (c->hal.env.poll(c->hal.env.ctx, &env)) {
        c->sensors.env = env;
        c->sensors.has_env = true;
    }
    if (!enabled) {
        c->sensors.has_env = false;
    }
}

static void read_noise(umi_clip_t *c)
{
    size_t n;
    do {
        n = c->hal.mic.read(c->hal.mic.ctx, c->pcm_buf, UMI_CLIP_PCM_CHUNK);
        umi_spl_process(&c->spl, c->pcm_buf, n);
    } while (n == UMI_CLIP_PCM_CHUNK);

    float dba;
    bool enabled = (c->settings.sensors & UMI_SENSOR_NOISE) != 0;
    /* The rider's own voice during the keyword window is not street noise. */
    if (enabled && !c->voice_open && umi_spl_laeq_1s(&c->spl, &dba)) {
        float cdba = dba * 100.0f;
        c->sensors.noise_cdba = cdba >= (float)(UMI_FORMAT_NOT_AVAILABLE_U16 - 1)
                                    ? UMI_FORMAT_NOT_AVAILABLE_U16 - 1
                                    : (uint16_t)lroundf(cdba > 0.0f ? cdba : 0.0f);
    } else {
        c->sensors.noise_cdba = UMI_FORMAT_NOT_AVAILABLE_U16;
    }
}

static void read_power(umi_clip_t *c, uint32_t now_ms)
{
    umi_battery_reading_t battery;
    while (c->hal.battery.poll(c->hal.battery.ctx, &battery)) {
        c->sensors.battery = battery;
        c->sensors.has_battery = true;
    }
    if (!c->board_temp_read || umi_elapsed_ms(now_ms, c->board_temp_read_ms) >= BOARD_TEMP_PERIOD_MS) {
        c->board_temp_read = true;
        c->board_temp_read_ms = now_ms;
        c->sensors.has_board_temp =
            c->hal.board.temp_cc(c->hal.board.ctx, &c->sensors.board_temp_cc);
    }
}

/* ---------------------------------------------------------------- flags */

static bool chirps_muted(const umi_clip_t *c)
{
    return !c->settings.chirp;
}

static void make_flag(umi_clip_t *c, uint32_t press_ms, uint8_t source,
                      const umi_keyword_result_t *kw, const umi_snapshot_t *snap, uint32_t now_ms)
{
    umi_record_t rec;
    umi_flag_outcome_t outcome = umi_flags_create(
        &c->flags, umi_recorder_session_ms(&c->recorder, press_ms), source, kw, snap, &rec);
    umi_recorder_push(&c->recorder, &rec);
    c->stats.flags++;
    umi_feedback_pattern_t pattern = UMI_FEEDBACK_FLAG;
    if (outcome == UMI_FLAG_UNDERSTOOD) {
        pattern = UMI_FEEDBACK_KEYWORD_UNDERSTOOD;
    } else if (outcome == UMI_FLAG_NOT_UNDERSTOOD) {
        pattern = UMI_FEEDBACK_KEYWORD_NOT_UNDERSTOOD;
    }
    umi_feedback_play(&c->feedback, pattern, chirps_muted(c), now_ms);
}

static void close_voice_window(umi_clip_t *c, const umi_keyword_result_t *kw, uint32_t now_ms)
{
    if (!c->voice_open) {
        return;
    }
    c->voice_open = false;
    c->hal.keyword.stop(c->hal.keyword.ctx);
    umi_feedback_stop(&c->feedback);
    /* Restart the noise average so the voice does not leak into the next second. */
    umi_spl_reset(&c->spl);
    make_flag(c, c->voice_press_ms, UMI_FLAG_SOURCE_VOICE, kw, &c->voice_snapshot, now_ms);
}

static void open_voice_window(umi_clip_t *c, uint32_t press_ms, uint32_t now_ms)
{
    c->voice_open = true;
    c->voice_opened_ms = now_ms;
    c->voice_press_ms = press_ms;
    c->voice_snapshot = c->press_snapshot;
    c->hal.keyword.start(c->hal.keyword.ctx);
    umi_feedback_play(&c->feedback, UMI_FEEDBACK_LISTENING, true, now_ms);
}

static void on_gesture(umi_clip_t *c, const umi_gesture_t *g, uint32_t now_ms)
{
    /* Outside a session there is no log to flag in; such a press is also
     * always inside the 200 m the privacy trim removes. */
    if (!umi_recorder_in_session(&c->recorder)) {
        return;
    }
    if (g->kind == UMI_GESTURE_DOWN) {
        c->press_snapshot = snapshot(c, now_ms);
        return;
    }
    /* A new gesture settles a voice window still open, so a double press right
     * after a hold undoes that voice flag. */
    close_voice_window(c, NULL, now_ms);

    switch (g->kind) {
    case UMI_GESTURE_SHORT:
        make_flag(c, g->t_ms, UMI_FLAG_SOURCE_PRESS, NULL, &c->press_snapshot, now_ms);
        break;
    case UMI_GESTURE_HOLD:
        if (c->settings.voice) {
            open_voice_window(c, g->t_ms, now_ms);
        } else {
            make_flag(c, g->t_ms, UMI_FLAG_SOURCE_PRESS, NULL, &c->press_snapshot, now_ms);
        }
        break;
    case UMI_GESTURE_DOUBLE: {
        umi_record_t rec;
        if (umi_flags_undo(&c->flags, umi_recorder_session_ms(&c->recorder, g->t_ms), &rec)) {
            umi_recorder_push(&c->recorder, &rec);
            c->stats.undos++;
            umi_feedback_play(&c->feedback, UMI_FEEDBACK_UNDO, chirps_muted(c), now_ms);
        }
        break;
    }
    case UMI_GESTURE_DOWN:
        break;
    }
}

static void run_button(umi_clip_t *c, uint32_t now_ms)
{
    umi_button_edge_t edge;
    while (c->hal.button.poll(c->hal.button.ctx, &edge)) {
        umi_button_edge(&c->button, edge.t_ms, edge.pressed);
    }
    umi_button_tick(&c->button, now_ms);
    umi_gesture_t g;
    while (umi_button_next(&c->button, &g)) {
        on_gesture(c, &g, now_ms);
    }
}

static void run_voice_window(umi_clip_t *c, uint32_t now_ms)
{
    if (!c->voice_open) {
        return;
    }
    umi_keyword_result_t kw;
    if (c->hal.keyword.poll(c->hal.keyword.ctx, &kw)) {
        close_voice_window(c, &kw, now_ms);
    } else if (umi_elapsed_ms(now_ms, c->voice_opened_ms) >= UMI_BUTTON_VOICE_WINDOW_MS) {
        close_voice_window(c, NULL, now_ms);
    }
}

/* ---------------------------------------------------------------- events */

static void record_detection(umi_clip_t *c, const umi_detection_t *d, uint32_t now_ms)
{
    if (!umi_recorder_in_session(&c->recorder)) {
        return;
    }
    umi_event_t event = {
        .t_ms = umi_recorder_session_ms(&c->recorder, d->t_ms),
        .kind = d->kind,
        .value_mms2 = to_mms2(d->value_mps2),
        .peak_mms2 = to_mms2(d->peak_mps2),
        .duration_ms = d->duration_ms > UINT16_MAX ? UINT16_MAX : (uint16_t)d->duration_ms,
    };
    if (fix_fresh(c, now_ms)) {
        event.lat_e7 = c->sensors.fix.lat_e7;
        event.lon_e7 = c->sensors.fix.lon_e7;
    }
    umi_record_t rec;
    umi_event_encode(&event, &rec);
    umi_recorder_push(&c->recorder, &rec);
    c->stats.events++;
}

static void run_detectors(umi_clip_t *c, uint32_t now_ms)
{
    umi_detection_t d;
    if (umi_brake_poll(&c->brake, now_ms, &d)) {
        record_detection(c, &d, now_ms);
    }
    if (umi_pothole_poll(&c->pothole, &d)) {
        record_detection(c, &d, now_ms);
    }
}

/* ---------------------------------------------------------------- step */

/* The oldest time a record may still be produced for: every producer that
 * dates a record in the past reports how far back it may go. */
static uint32_t record_horizon(const umi_clip_t *c, uint32_t now_ms)
{
    uint32_t horizon = now_ms - RECORD_SETTLE_MS;
    uint32_t t;
    if (umi_button_pending_since(&c->button, &t)) {
        horizon = umi_time_min(horizon, t);
    }
    if (c->voice_open) {
        horizon = umi_time_min(horizon, c->voice_press_ms);
    }
    if (umi_brake_pending_since(&c->brake, &t)) {
        horizon = umi_time_min(horizon, t);
    }
    if (umi_pothole_pending_since(&c->pothole, &t)) {
        horizon = umi_time_min(horizon, t);
    }
    /* Records at the horizon itself are still safe: order is non-decreasing. */
    return horizon;
}

void umi_clip_step(umi_clip_t *c, uint32_t now_ms)
{
    read_imu(c);
    read_gnss(c, now_ms);
    read_air(c);
    read_noise(c);
    read_power(c, now_ms);

    umi_recorder_change_t change = umi_recorder_tick(&c->recorder, now_ms, &c->sensors);
    if (change == UMI_RECORDER_STARTED) {
        umi_flags_begin_session(&c->flags, c->recorder.session_id);
        c->stats.sessions++;
    } else if (change == UMI_RECORDER_STOPPED && c->voice_open) {
        c->voice_open = false;
        c->hal.keyword.stop(c->hal.keyword.ctx);
        umi_feedback_stop(&c->feedback);
    }

    run_button(c, now_ms);
    run_voice_window(c, now_ms);
    run_detectors(c, now_ms);

    umi_recorder_flush(&c->recorder, record_horizon(c, now_ms));
    umi_feedback_tick(&c->feedback, now_ms);
}

void umi_clip_shutdown(umi_clip_t *c, uint32_t now_ms)
{
    if (umi_recorder_in_session(&c->recorder)) {
        close_voice_window(c, NULL, now_ms);
    }
    umi_recorder_stop(&c->recorder, now_ms);
    umi_feedback_stop(&c->feedback);
}

void umi_clip_set_time(umi_clip_t *c, uint32_t now_ms, int64_t unix_ms)
{
    umi_recorder_on_time_set(&c->recorder, now_ms, unix_ms);
}

void umi_clip_live_status(const umi_clip_t *c, umi_live_status_t *out)
{
    const umi_sensor_state_t *s = &c->sensors;
    *out = (umi_live_status_t){
        .battery_pct = s->has_battery ? s->battery.pct : 0,
        .status_flags = umi_recorder_status_flags(&c->recorder, s),
        .fix = s->has_fix ? s->fix.fix : UMI_FIX_NONE,
    };
    switch (c->recorder.phase) {
    case UMI_RECORDER_IDLE:
        out->recorder_state = 0;
        break;
    case UMI_RECORDER_RECORDING:
        out->recorder_state = UMI_RECORDER_STATE_RECORDING;
        break;
    case UMI_RECORDER_PAUSED:
        out->recorder_state = UMI_RECORDER_STATE_AUTO_PAUSE;
        break;
    }
}
