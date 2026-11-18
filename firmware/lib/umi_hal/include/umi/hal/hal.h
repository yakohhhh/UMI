/* Every part the Clip application needs, bundled for dependency injection.
 * Time is not a part: the application is handed now_ms on every step, which
 * keeps the core deterministic and lets the SIL run in simulated time. */
#ifndef UMI_HAL_H
#define UMI_HAL_H

#include "umi/hal/battery.h"
#include "umi/hal/board.h"
#include "umi/hal/button.h"
#include "umi/hal/buzzer.h"
#include "umi/hal/env.h"
#include "umi/hal/gnss.h"
#include "umi/hal/imu.h"
#include "umi/hal/keyword.h"
#include "umi/hal/led.h"
#include "umi/hal/mic.h"
#include "umi/hal/pm.h"
#include "umi/hal/signer.h"
#include "umi/hal/storage.h"

typedef struct {
    umi_hal_imu_t imu;
    umi_hal_gnss_t gnss;
    umi_hal_pm_t pm;
    umi_hal_env_t env;
    umi_hal_mic_t mic;
    umi_hal_keyword_t keyword;
    umi_hal_battery_t battery;
    umi_hal_board_t board;
    umi_hal_button_t button;
    umi_hal_buzzer_t buzzer;
    umi_hal_led_t led;
    umi_hal_storage_t storage;
    umi_hal_signer_t signer;
} umi_hal_t;

#endif /* UMI_HAL_H */
