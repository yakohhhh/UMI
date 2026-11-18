/* Simulated sensors driven by a SIL scenario. The world is advanced to "now"
 * before each application step; the HAL implementations then hand out what
 * the scenario produced up to that time, through the same parsers the real
 * drivers use (NMEA, Plantower) and a synthetic PCM stream for the SPL meter. */
#ifndef UMI_SIM_WORLD_H
#define UMI_SIM_WORLD_H

#include <stdbool.h>
#include <stdint.h>

#include "umi/drivers/nmea.h"
#include "umi/drivers/pms.h"
#include "umi/hal/hal.h"
#include "umi/sim/scenario.h"

#define UMI_SIM_IMU_QUEUE 64
#define UMI_SIM_FIX_QUEUE 4
#define UMI_SIM_PM_QUEUE 4
#define UMI_SIM_EDGE_QUEUE 16
#define UMI_SIM_LEVEL_QUEUE 8
#define UMI_SIM_MIC_RATE_HZ 16000u

/* Fixed-capacity FIFO over caller-owned storage; overflow drops the oldest,
 * as a sensor FIFO does. */
typedef struct {
    void *items;
    uint16_t item_size;
    uint8_t cap;
    uint8_t head;
    uint8_t count;
} umi_sim_queue_t;

typedef struct {
    uint32_t t_ms;
    float dba;
} umi_sim_level_t;

typedef struct {
    umi_scenario_t scenario;
    bool has_next;
    umi_scenario_line_t next;
    uint32_t now_ms;

    umi_imu_sample_t imu_items[UMI_SIM_IMU_QUEUE];
    umi_sim_queue_t imu;
    umi_gnss_fix_t fix_items[UMI_SIM_FIX_QUEUE];
    umi_sim_queue_t fixes;
    umi_pm_reading_t pm_items[UMI_SIM_PM_QUEUE];
    umi_sim_queue_t pm;
    umi_button_edge_t edge_items[UMI_SIM_EDGE_QUEUE];
    umi_sim_queue_t edges;
    umi_nmea_t nmea;
    umi_pms_t pms;

    bool env_new;
    umi_env_reading_t env;
    bool has_env;
    bool battery_new;
    umi_battery_reading_t battery;

    /* Mic: a 1 kHz tone at the scripted level, generated sample by sample so a
     * level change lands on the exact sample whatever the step size. */
    umi_sim_level_t level_items[UMI_SIM_LEVEL_QUEUE];
    umi_sim_queue_t levels;
    bool level_set;
    double level_amplitude; /* Q31 peak of the current tone */
    uint64_t mic_samples;

    bool listening;
    bool keyword_ready;
    umi_keyword_result_t keyword;

    uint32_t overruns; /* readings dropped because a queue was full */
    uint32_t stray_keywords; /* keyword lines outside a voice window */
} umi_sim_world_t;

/* Fails when the text is not a v1 scenario. warn reports skipped lines. */
bool umi_sim_world_init(umi_sim_world_t *w, const char *scenario_text, umi_scenario_warn_fn warn,
                        void *warn_ctx);

/* Delivers every scenario line dated at or before now_ms. */
void umi_sim_world_advance(umi_sim_world_t *w, uint32_t now_ms);

/* True once every line has been delivered. */
bool umi_sim_world_finished(const umi_sim_world_t *w);

/* Time of the last line delivered. */
uint32_t umi_sim_world_last_ms(const umi_sim_world_t *w);

/* Fills the sensor and button HALs of *hal; buzzer, LED, storage and signer
 * are left to the caller. */
void umi_sim_world_bind(umi_sim_world_t *w, umi_hal_t *hal);

#endif /* UMI_SIM_WORLD_H */
