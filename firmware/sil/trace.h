/* Buzzer and LED for the SIL: print what the rider would hear and see. */
#ifndef UMI_SIL_TRACE_H
#define UMI_SIL_TRACE_H

#include <stdbool.h>
#include <stdint.h>

#include "umi/hal/buzzer.h"
#include "umi/hal/led.h"

typedef struct {
    const uint32_t *now_ms;
    bool verbose;
    uint16_t tone_hz;
    umi_led_color_t led;
    uint32_t chirps;
} umi_trace_t;

void umi_trace_init(umi_trace_t *t, const uint32_t *now_ms, bool verbose);
umi_hal_buzzer_t umi_trace_buzzer(umi_trace_t *t);
umi_hal_led_t umi_trace_led(umi_trace_t *t);

#endif /* UMI_SIL_TRACE_H */
