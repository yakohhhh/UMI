/* Flag button gestures from raw contact edges ([button] in constants.toml):
 * a short press flags, a hold opens the voice window, a double press undoes.
 *
 * A short press is only known once the double-press gap has passed without a
 * second press, so every gesture is reported with the time of its first press:
 * that is the moment the rider meant. */
#ifndef UMI_CORE_BUTTON_H
#define UMI_CORE_BUTTON_H

#include <stdbool.h>
#include <stdint.h>

typedef enum {
    UMI_GESTURE_DOWN,   /* first press of a gesture, as soon as it is debounced */
    UMI_GESTURE_SHORT,  /* one press shorter than hold_ms, no second press */
    UMI_GESTURE_HOLD,   /* held for hold_ms: emitted while still held */
    UMI_GESTURE_DOUBLE, /* second press within double_press_gap_ms of the release */
} umi_gesture_kind_t;

typedef struct {
    umi_gesture_kind_t kind;
    uint32_t t_ms; /* first press of the gesture */
} umi_gesture_t;

typedef enum {
    UMI_BUTTON_IDLE,
    UMI_BUTTON_PRESSED,
    UMI_BUTTON_RELEASED, /* waiting for a possible second press */
    UMI_BUTTON_WAIT_UP,  /* gesture decided, waiting for the release */
} umi_button_state_t;

#define UMI_BUTTON_QUEUE_LEN 4

typedef struct {
    /* debouncer */
    bool raw_pressed;
    uint32_t raw_t_ms;
    bool stable_pressed;
    /* gestures */
    umi_button_state_t state;
    uint32_t press_t_ms;
    uint32_t release_t_ms;
    umi_gesture_t queue[UMI_BUTTON_QUEUE_LEN];
    uint8_t head;
    uint8_t count;
} umi_button_t;

void umi_button_init(umi_button_t *b);

/* Feed raw edges in time order; bounces are fine. */
void umi_button_edge(umi_button_t *b, uint32_t t_ms, bool pressed);

/* Advances timers (debounce, hold, double-press gap) to now_ms. */
void umi_button_tick(umi_button_t *b, uint32_t now_ms);

bool umi_button_next(umi_button_t *b, umi_gesture_t *out);

/* While a gesture is undecided, the earliest time it may still report, so the
 * recorder holds back later records until the flag can be ordered among them. */
bool umi_button_pending_since(const umi_button_t *b, uint32_t *t_ms);

#endif /* UMI_CORE_BUTTON_H */
