#include "trace.h"

#include <stdio.h>

void umi_trace_init(umi_trace_t *t, const uint32_t *now_ms, bool verbose)
{
    *t = (umi_trace_t){.now_ms = now_ms, .verbose = verbose, .led = UMI_LED_OFF};
}

static void tone(void *ctx, uint16_t hz)
{
    umi_trace_t *t = ctx;
    if (hz == t->tone_hz) {
        return;
    }
    t->tone_hz = hz;
    if (hz != 0) {
        t->chirps++;
        if (t->verbose) {
            fprintf(stderr, "  %9.3f s  chirp %u Hz\n", *t->now_ms / 1000.0, (unsigned)hz);
        }
    }
}

static void led(void *ctx, umi_led_color_t color)
{
    umi_trace_t *t = ctx;
    if (color == t->led) {
        return;
    }
    t->led = color;
    if (t->verbose) {
        fprintf(stderr, "  %9.3f s  led %s\n", *t->now_ms / 1000.0,
                color == UMI_LED_ORANGE ? "orange" : "off");
    }
}

umi_hal_buzzer_t umi_trace_buzzer(umi_trace_t *t)
{
    return (umi_hal_buzzer_t){.tone = tone, .ctx = t};
}

umi_hal_led_t umi_trace_led(umi_trace_t *t)
{
    return (umi_hal_led_t){.set = led, .ctx = t};
}
