/* Warn-ahead: two low chirps when the rider approaches a verified hazard the
 * phone sent over BLE ([feedback] warn_ahead_radius_m, warn_ahead_cooldown_s).
 *
 * "Approaching" means moving and the hazard lies ahead (within 60° of the
 * course), so a hazard just passed or a parked bike next to one stays quiet.
 * The cooldown is per hazard. */
#ifndef UMI_CORE_WARN_AHEAD_H
#define UMI_CORE_WARN_AHEAD_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "umi/hal/gnss.h"

/* The phone sends the hazards around the rider's usual area; 128 x 13 bytes
 * is one BLE upload of a couple of seconds. */
#define UMI_WARN_AHEAD_MAX_HAZARDS 128

typedef struct {
    uint32_t id;
    int32_t lat_e7;
    int32_t lon_e7;
    uint8_t kind; /* umi_hazard_kind_t */
} umi_hazard_t;

typedef struct {
    umi_hazard_t hazard;
    bool warned;
    uint32_t warned_ms;
} umi_warn_ahead_entry_t;

typedef struct {
    umi_warn_ahead_entry_t active[UMI_WARN_AHEAD_MAX_HAZARDS];
    size_t count;
    /* Upload in progress (HAZARDS_BEGIN .. HAZARDS_END); the active list keeps
     * warning until it is committed. */
    umi_warn_ahead_entry_t staging[UMI_WARN_AHEAD_MAX_HAZARDS];
    size_t staging_count;
    size_t staging_expected;
    bool staging_open;
} umi_warn_ahead_t;

void umi_warn_ahead_init(umi_warn_ahead_t *w);

bool umi_warn_ahead_begin(umi_warn_ahead_t *w, uint16_t count);
bool umi_warn_ahead_add(umi_warn_ahead_t *w, const umi_hazard_t *hazards, size_t n);
/* Replaces the active list; hazards that stay keep their cooldown. Fails if
 * fewer hazards arrived than announced. */
bool umi_warn_ahead_commit(umi_warn_ahead_t *w);

/* Checks a fix; returns the nearest hazard to warn about, at most one. */
bool umi_warn_ahead_check(umi_warn_ahead_t *w, uint32_t now_ms, const umi_gnss_fix_t *fix,
                          umi_hazard_t *out);

#endif /* UMI_CORE_WARN_AHEAD_H */
