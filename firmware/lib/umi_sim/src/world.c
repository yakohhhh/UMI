#include "umi/sim/world.h"

#include <math.h>
#include <string.h>

#include "umi/core/spl.h"

#define TONE_HZ 1000u
#define PI 3.14159265358979323846

static void queue_init(umi_sim_queue_t *q, void *items, size_t item_size, size_t cap)
{
    *q = (umi_sim_queue_t){.items = items, .item_size = (uint16_t)item_size, .cap = (uint8_t)cap};
}

static void *slot(const umi_sim_queue_t *q, size_t index)
{
    return (uint8_t *)q->items + (size_t)((q->head + index) % q->cap) * q->item_size;
}

static void queue_push(umi_sim_world_t *w, umi_sim_queue_t *q, const void *item)
{
    if (q->count == q->cap) {
        q->head = (uint8_t)((q->head + 1) % q->cap);
        q->count--;
        w->overruns++;
    }
    memcpy(slot(q, q->count), item, q->item_size);
    q->count++;
}

static const void *queue_peek(const umi_sim_queue_t *q)
{
    return q->count == 0 ? NULL : slot(q, 0);
}

static bool queue_pop(umi_sim_queue_t *q, void *out)
{
    if (q->count == 0) {
        return false;
    }
    memcpy(out, slot(q, 0), q->item_size);
    q->head = (uint8_t)((q->head + 1) % q->cap);
    q->count--;
    return true;
}

#define QUEUE_INIT(q, items) queue_init(&(q), (items), sizeof (items)[0], sizeof(items) / sizeof (items)[0])

bool umi_sim_world_init(umi_sim_world_t *w, const char *scenario_text, umi_scenario_warn_fn warn,
                        void *warn_ctx)
{
    memset(w, 0, sizeof *w);
    QUEUE_INIT(w->imu, w->imu_items);
    QUEUE_INIT(w->fixes, w->fix_items);
    QUEUE_INIT(w->pm, w->pm_items);
    QUEUE_INIT(w->edges, w->edge_items);
    QUEUE_INIT(w->levels, w->level_items);
    umi_nmea_init(&w->nmea);
    umi_pms_init(&w->pms);
    if (!umi_scenario_open(&w->scenario, scenario_text, warn, warn_ctx)) {
        return false;
    }
    w->has_next = umi_scenario_next(&w->scenario, &w->next);
    return true;
}

static void deliver(umi_sim_world_t *w, const umi_scenario_line_t *line)
{
    switch (line->kind) {
    case UMI_SCN_IMU: {
        umi_imu_sample_t s = {
            .t_ms = line->t_ms,
            .ax = line->as.imu.ax,
            .ay = line->as.imu.ay,
            .az = line->as.imu.az,
            .gx = line->as.imu.gx,
            .gy = line->as.imu.gy,
            .gz = line->as.imu.gz,
        };
        queue_push(w, &w->imu, &s);
        break;
    }
    case UMI_SCN_GNSS: {
        umi_gnss_fix_t fix;
        if (umi_nmea_feed_sentence(&w->nmea, line->as.gnss.sentence, line->as.gnss.len,
                                   line->t_ms, &fix)) {
            queue_push(w, &w->fixes, &fix);
        }
        break;
    }
    case UMI_SCN_PM: {
        umi_pms_frame_t frame;
        for (size_t i = 0; i < UMI_SCENARIO_PM_LEN; i++) {
            if (umi_pms_feed(&w->pms, line->as.pm[i], &frame)) {
                umi_pm_reading_t r = {
                    .t_ms = line->t_ms,
                    .pm1_ugm3 = frame.pm1_atm,
                    .pm25_ugm3 = frame.pm25_atm,
                    .pm10_ugm3 = frame.pm10_atm,
                };
                queue_push(w, &w->pm, &r);
            }
        }
        break;
    }
    case UMI_SCN_SPL: {
        umi_sim_level_t level = {.t_ms = line->t_ms, .dba = line->as.spl_dba};
        queue_push(w, &w->levels, &level);
        break;
    }
    case UMI_SCN_ENV:
        w->env = (umi_env_reading_t){line->t_ms, line->as.env.temp_c, line->as.env.rh_pct};
        w->env_new = true;
        w->has_env = true;
        break;
    case UMI_SCN_BUTTON: {
        umi_button_edge_t edge = {.t_ms = line->t_ms, .pressed = line->as.button_pressed};
        queue_push(w, &w->edges, &edge);
        break;
    }
    case UMI_SCN_BATTERY:
        w->battery = (umi_battery_reading_t){
            .mv = line->as.battery.mv, .pct = line->as.battery.pct, .charging = false};
        w->battery_new = true;
        break;
    case UMI_SCN_KEYWORD:
        if (w->listening) {
            w->keyword = line->as.keyword;
            w->keyword_ready = true;
        } else {
            w->stray_keywords++;
        }
        break;
    }
}

void umi_sim_world_advance(umi_sim_world_t *w, uint32_t now_ms)
{
    w->now_ms = now_ms;
    while (w->has_next && w->next.t_ms <= now_ms) {
        deliver(w, &w->next);
        w->has_next = umi_scenario_next(&w->scenario, &w->next);
    }
}

bool umi_sim_world_finished(const umi_sim_world_t *w)
{
    return !w->has_next;
}

uint32_t umi_sim_world_last_ms(const umi_sim_world_t *w)
{
    return w->scenario.last_t_ms;
}

/* ---------------------------------------------------------------- HAL */

static size_t imu_read(void *ctx, umi_imu_sample_t *out, size_t max)
{
    umi_sim_world_t *w = ctx;
    size_t n = 0;
    while (n < max && queue_pop(&w->imu, &out[n])) {
        n++;
    }
    return n;
}

static bool gnss_poll(void *ctx, umi_gnss_fix_t *out)
{
    umi_sim_world_t *w = ctx;
    return queue_pop(&w->fixes, out);
}

static bool pm_poll(void *ctx, umi_pm_reading_t *out)
{
    umi_sim_world_t *w = ctx;
    return queue_pop(&w->pm, out);
}

static bool env_poll(void *ctx, umi_env_reading_t *out)
{
    umi_sim_world_t *w = ctx;
    if (!w->env_new) {
        return false;
    }
    w->env_new = false;
    *out = w->env;
    return true;
}

static bool battery_poll(void *ctx, umi_battery_reading_t *out)
{
    umi_sim_world_t *w = ctx;
    if (!w->battery_new) {
        return false;
    }
    w->battery_new = false;
    *out = w->battery;
    return true;
}

static bool board_temp(void *ctx, int16_t *out)
{
    /* No scenario column for it: the enclosure follows the air around it. */
    umi_sim_world_t *w = ctx;
    if (!w->has_env) {
        return false;
    }
    *out = (int16_t)lroundf(w->env.temp_c * 100.0f);
    return true;
}

static bool button_poll(void *ctx, umi_button_edge_t *out)
{
    umi_sim_world_t *w = ctx;
    return queue_pop(&w->edges, out);
}

static size_t mic_read(void *ctx, int32_t *pcm, size_t max)
{
    umi_sim_world_t *w = ctx;
    uint64_t due = (uint64_t)w->now_ms * UMI_SIM_MIC_RATE_HZ / 1000u;
    size_t n = 0;
    while (n < max && w->mic_samples < due) {
        uint64_t k = w->mic_samples;
        uint32_t t_ms = (uint32_t)(k * 1000u / UMI_SIM_MIC_RATE_HZ);
        const umi_sim_level_t *level;
        while ((level = queue_peek(&w->levels)) != NULL && level->t_ms <= t_ms) {
            /* Clipped at full scale, like the real mic past its acoustic overload. */
            double peak = sqrt(2.0) * umi_spl_tone_rms(level->dba);
            w->level_amplitude = (peak < 1.0 ? peak : 1.0) * 2147483647.0;
            w->level_set = true;
            umi_sim_level_t done;
            queue_pop(&w->levels, &done);
        }
        w->mic_samples++;
        if (!w->level_set) {
            /* No level scripted yet: the mic is not delivering. */
            continue;
        }
        double phase = 2.0 * PI * (double)((k * TONE_HZ) % UMI_SIM_MIC_RATE_HZ) / UMI_SIM_MIC_RATE_HZ;
        pcm[n++] = (int32_t)lrint(w->level_amplitude * sin(phase));
    }
    return n;
}

static void keyword_start(void *ctx)
{
    umi_sim_world_t *w = ctx;
    w->listening = true;
    w->keyword_ready = false;
}

static bool keyword_poll(void *ctx, umi_keyword_result_t *out)
{
    umi_sim_world_t *w = ctx;
    if (!w->keyword_ready) {
        return false;
    }
    w->keyword_ready = false;
    *out = w->keyword;
    return true;
}

static void keyword_stop(void *ctx)
{
    umi_sim_world_t *w = ctx;
    w->listening = false;
    w->keyword_ready = false;
}

void umi_sim_world_bind(umi_sim_world_t *w, umi_hal_t *hal)
{
    hal->imu = (umi_hal_imu_t){.read = imu_read, .ctx = w};
    hal->gnss = (umi_hal_gnss_t){.poll = gnss_poll, .ctx = w};
    hal->pm = (umi_hal_pm_t){.poll = pm_poll, .ctx = w};
    hal->env = (umi_hal_env_t){.poll = env_poll, .ctx = w};
    hal->mic = (umi_hal_mic_t){.sample_rate_hz = UMI_SIM_MIC_RATE_HZ, .read = mic_read, .ctx = w};
    hal->keyword = (umi_hal_keyword_t){
        .start = keyword_start, .poll = keyword_poll, .stop = keyword_stop, .ctx = w};
    hal->battery = (umi_hal_battery_t){.poll = battery_poll, .ctx = w};
    hal->board = (umi_hal_board_t){.temp_cc = board_temp, .ctx = w};
    hal->button = (umi_hal_button_t){.poll = button_poll, .ctx = w};
}
