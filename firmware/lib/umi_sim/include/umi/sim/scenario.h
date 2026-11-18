/* SIL scenario reader (protocol/sil-scenario.md, format v1): one sensor
 * reading per line, in time order. Works in place on a NUL-terminated text
 * (a file read on the host, or the copy embedded in a devkit's flash). */
#ifndef UMI_SIM_SCENARIO_H
#define UMI_SIM_SCENARIO_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "umi/hal/keyword.h"

#define UMI_SCENARIO_HEADER "# umi-sil-scenario v1"
#define UMI_SCENARIO_PM_LEN 32

typedef enum {
    UMI_SCN_IMU,
    UMI_SCN_GNSS,
    UMI_SCN_PM,
    UMI_SCN_SPL,
    UMI_SCN_ENV,
    UMI_SCN_BUTTON,
    UMI_SCN_BATTERY,
    UMI_SCN_KEYWORD,
} umi_scenario_kind_t;

typedef struct {
    uint32_t t_ms;
    umi_scenario_kind_t kind;
    union {
        struct {
            float ax, ay, az, gx, gy, gz;
        } imu;
        struct {
            const char *sentence; /* points into the scenario text */
            size_t len;
        } gnss;
        uint8_t pm[UMI_SCENARIO_PM_LEN];
        float spl_dba;
        struct {
            float temp_c, rh_pct;
        } env;
        bool button_pressed;
        struct {
            uint16_t mv;
            uint8_t pct;
        } battery;
        umi_keyword_result_t keyword;
    } as;
} umi_scenario_line_t;

/* Called for every line that is skipped: comments excepted. */
typedef void (*umi_scenario_warn_fn)(void *ctx, uint32_t line_no, const char *reason);

typedef struct {
    const char *text;
    const char *pos;
    uint32_t line_no;
    uint32_t last_t_ms;
    umi_scenario_warn_fn warn;
    void *warn_ctx;
    uint32_t skipped;
} umi_scenario_t;

/* Fails when the first line is not the v1 header. warn may be NULL. */
bool umi_scenario_open(umi_scenario_t *s, const char *text, umi_scenario_warn_fn warn,
                       void *warn_ctx);

/* Next valid reading; false at the end. Unknown kinds, malformed lines and
 * lines going back in time are skipped with a warning. */
bool umi_scenario_next(umi_scenario_t *s, umi_scenario_line_t *out);

#endif /* UMI_SIM_SCENARIO_H */
