/* What the rider hears and sees ([feedback] in constants.toml). The number and
 * pitch of chirps carry the meaning; the LED only accompanies them. */
#ifndef UMI_CORE_FEEDBACK_H
#define UMI_CORE_FEEDBACK_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "umi/hal/buzzer.h"
#include "umi/hal/led.h"

typedef enum {
    UMI_FEEDBACK_FLAG,                    /* 1 high chirp + orange flash */
    UMI_FEEDBACK_LISTENING,               /* orange pulse while the voice window is open */
    UMI_FEEDBACK_KEYWORD_UNDERSTOOD,      /* 2 rising chirps */
    UMI_FEEDBACK_KEYWORD_NOT_UNDERSTOOD,  /* 1 low chirp: the flag is kept without a kind */
    UMI_FEEDBACK_UNDO,                    /* 2 short high chirps */
    UMI_FEEDBACK_WARN_AHEAD,              /* 2 low chirps */
} umi_feedback_pattern_t;

typedef struct {
    uint16_t duration_ms;
    uint16_t tone_hz; /* 0 = silent */
    umi_led_color_t led;
} umi_feedback_step_t;

typedef struct {
    const umi_feedback_step_t *steps;
    size_t count;
    bool loop; /* repeats until stopped or replaced */
} umi_feedback_sequence_t;

typedef struct {
    umi_hal_buzzer_t buzzer;
    umi_hal_led_t led;
    umi_feedback_sequence_t seq;
    size_t index;
    uint32_t step_start_ms;
    bool playing;
    bool muted; /* LED only for this sequence */
} umi_feedback_t;

void umi_feedback_init(umi_feedback_t *f, umi_hal_buzzer_t buzzer, umi_hal_led_t led);

/* Starts a pattern now, cutting whatever was playing. muted keeps the LED and
 * silences the buzzer (the rider turned confirmation chirps off). */
void umi_feedback_play(umi_feedback_t *f, umi_feedback_pattern_t pattern, bool muted,
                       uint32_t now_ms);
void umi_feedback_stop(umi_feedback_t *f);
void umi_feedback_tick(umi_feedback_t *f, uint32_t now_ms);
bool umi_feedback_playing(const umi_feedback_t *f);

#endif /* UMI_CORE_FEEDBACK_H */
