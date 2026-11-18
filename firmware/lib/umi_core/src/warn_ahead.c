#include "umi/core/warn_ahead.h"

#include <math.h>

#include "umi/core/geo.h"
#include "umi/core/time.h"
#include "umi/protocol_gen.h"

#define AHEAD_HALF_ANGLE_DEG 60.0
/* Below walking pace the course over ground is noise. */
#define MIN_SPEED_CMS 150u
#define COOLDOWN_MS (UMI_FEEDBACK_WARN_AHEAD_COOLDOWN_S * 1000u)

void umi_warn_ahead_init(umi_warn_ahead_t *w)
{
    w->count = 0;
    w->staging_count = 0;
    w->staging_expected = 0;
    w->staging_open = false;
}

bool umi_warn_ahead_begin(umi_warn_ahead_t *w, uint16_t count)
{
    if (count > UMI_WARN_AHEAD_MAX_HAZARDS) {
        w->staging_open = false;
        return false;
    }
    w->staging_open = true;
    w->staging_count = 0;
    w->staging_expected = count;
    return true;
}

static const umi_warn_ahead_entry_t *find_active(const umi_warn_ahead_t *w, uint32_t id)
{
    for (size_t i = 0; i < w->count; i++) {
        if (w->active[i].hazard.id == id) {
            return &w->active[i];
        }
    }
    return NULL;
}

bool umi_warn_ahead_add(umi_warn_ahead_t *w, const umi_hazard_t *hazards, size_t n)
{
    if (!w->staging_open || w->staging_count + n > w->staging_expected) {
        return false;
    }
    for (size_t i = 0; i < n; i++) {
        /* A hazard already known keeps its cooldown, so a refresh of the list
         * does not chirp again for the one the rider just passed. */
        const umi_warn_ahead_entry_t *old = find_active(w, hazards[i].id);
        w->staging[w->staging_count++] = (umi_warn_ahead_entry_t){
            .hazard = hazards[i],
            .warned = old != NULL && old->warned,
            .warned_ms = old != NULL ? old->warned_ms : 0,
        };
    }
    return true;
}

bool umi_warn_ahead_commit(umi_warn_ahead_t *w)
{
    bool complete = w->staging_open && w->staging_count == w->staging_expected;
    w->staging_open = false;
    if (!complete) {
        return false;
    }
    for (size_t i = 0; i < w->staging_count; i++) {
        w->active[i] = w->staging[i];
    }
    w->count = w->staging_count;
    return true;
}

bool umi_warn_ahead_check(umi_warn_ahead_t *w, uint32_t now_ms, const umi_gnss_fix_t *fix,
                          umi_hazard_t *out)
{
    if (fix->fix == UMI_FIX_NONE || fix->speed_cms < MIN_SPEED_CMS) {
        return false;
    }
    const double radius_m = UMI_FEEDBACK_WARN_AHEAD_RADIUS_M;
    umi_geo_point_t here = {fix->lat_e7, fix->lon_e7};
    double course = fix->heading_cdeg / 100.0;
    umi_warn_ahead_entry_t *best = NULL;
    double best_m = INFINITY;
    for (size_t i = 0; i < w->count; i++) {
        umi_warn_ahead_entry_t *e = &w->active[i];
        if (e->warned && umi_elapsed_ms(now_ms, e->warned_ms) < COOLDOWN_MS) {
            continue;
        }
        umi_geo_point_t there = {e->hazard.lat_e7, e->hazard.lon_e7};
        if (!umi_geo_maybe_within(here, there, radius_m)) {
            continue;
        }
        double d = umi_geo_distance_m(here, there);
        if (d > radius_m || d >= best_m) {
            continue;
        }
        double off = fabs(umi_geo_heading_diff_deg(course, umi_geo_bearing_deg(here, there)));
        if (off <= AHEAD_HALF_ANGLE_DEG) {
            best = e;
            best_m = d;
        }
    }
    if (best == NULL) {
        return false;
    }
    best->warned = true;
    best->warned_ms = now_ms;
    *out = best->hazard;
    return true;
}
