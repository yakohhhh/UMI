#include "umi/core/feedback.h"

#include "umi/core/time.h"
#include "umi/protocol_gen.h"

#define CHIRP UMI_FEEDBACK_CHIRP_MS
#define GAP UMI_FEEDBACK_CHIRP_GAP_MS
#define HIGH UMI_FEEDBACK_CHIRP_HIGH_HZ
#define LOW UMI_FEEDBACK_CHIRP_LOW_HZ
#define FLASH_MS 200  /* long enough to catch from the corner of an eye */
#define PULSE_MS 250

static const umi_feedback_step_t FLAG[] = {
    {CHIRP, HIGH, UMI_LED_ORANGE},
    {FLASH_MS - CHIRP, 0, UMI_LED_ORANGE},
};
static const umi_feedback_step_t LISTENING[] = {
    {PULSE_MS, 0, UMI_LED_ORANGE},
    {PULSE_MS, 0, UMI_LED_OFF},
};
static const umi_feedback_step_t UNDERSTOOD[] = {
    {CHIRP, LOW, UMI_LED_ORANGE},
    {GAP, 0, UMI_LED_OFF},
    {CHIRP, HIGH, UMI_LED_ORANGE},
};
static const umi_feedback_step_t NOT_UNDERSTOOD[] = {
    {CHIRP, LOW, UMI_LED_ORANGE},
};
static const umi_feedback_step_t UNDO[] = {
    {CHIRP, HIGH, UMI_LED_ORANGE},
    {GAP, 0, UMI_LED_OFF},
    {CHIRP, HIGH, UMI_LED_ORANGE},
};
static const umi_feedback_step_t WARN_AHEAD[] = {
    {CHIRP, LOW, UMI_LED_ORANGE},
    {GAP, 0, UMI_LED_OFF},
    {CHIRP, LOW, UMI_LED_ORANGE},
};

#define SEQ(steps, looping) ((umi_feedback_sequence_t){steps, sizeof steps / sizeof steps[0], looping})

static umi_feedback_sequence_t sequence_of(umi_feedback_pattern_t pattern)
{
    switch (pattern) {
    case UMI_FEEDBACK_FLAG:
        return SEQ(FLAG, false);
    case UMI_FEEDBACK_LISTENING:
        return SEQ(LISTENING, true);
    case UMI_FEEDBACK_KEYWORD_UNDERSTOOD:
        return SEQ(UNDERSTOOD, false);
    case UMI_FEEDBACK_KEYWORD_NOT_UNDERSTOOD:
        return SEQ(NOT_UNDERSTOOD, false);
    case UMI_FEEDBACK_UNDO:
        return SEQ(UNDO, false);
    case UMI_FEEDBACK_WARN_AHEAD:
        return SEQ(WARN_AHEAD, false);
    }
    return (umi_feedback_sequence_t){0};
}

void umi_feedback_init(umi_feedback_t *f, umi_hal_buzzer_t buzzer, umi_hal_led_t led)
{
    *f = (umi_feedback_t){.buzzer = buzzer, .led = led};
}

static void output(umi_feedback_t *f, uint16_t tone_hz, umi_led_color_t led)
{
    f->buzzer.tone(f->buzzer.ctx, f->muted ? 0 : tone_hz);
    f->led.set(f->led.ctx, led);
}

static void enter_step(umi_feedback_t *f, size_t index, uint32_t start_ms)
{
    f->index = index;
    f->step_start_ms = start_ms;
    const umi_feedback_step_t *step = &f->seq.steps[index];
    output(f, step->tone_hz, step->led);
}

void umi_feedback_play(umi_feedback_t *f, umi_feedback_pattern_t pattern, bool muted,
                       uint32_t now_ms)
{
    f->seq = sequence_of(pattern);
    f->muted = muted;
    f->playing = true;
    enter_step(f, 0, now_ms);
}

void umi_feedback_stop(umi_feedback_t *f)
{
    if (f->playing) {
        f->playing = false;
        output(f, 0, UMI_LED_OFF);
    }
}

void umi_feedback_tick(umi_feedback_t *f, uint32_t now_ms)
{
    while (f->playing) {
        uint32_t end_ms = f->step_start_ms + f->seq.steps[f->index].duration_ms;
        if (umi_time_before(now_ms, end_ms)) {
            return;
        }
        size_t next = f->index + 1;
        if (next == f->seq.count) {
            if (!f->seq.loop) {
                umi_feedback_stop(f);
                return;
            }
            next = 0;
        }
        /* Steps chain from their scheduled end, not from now, so a late tick
         * does not stretch the pattern. */
        enter_step(f, next, end_ms);
    }
}

bool umi_feedback_playing(const umi_feedback_t *f)
{
    return f->playing;
}
