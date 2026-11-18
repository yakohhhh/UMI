#include "umi/core/button.h"

#include "umi/core/time.h"
#include "umi/protocol_gen.h"

void umi_button_init(umi_button_t *b)
{
    *b = (umi_button_t){.state = UMI_BUTTON_IDLE};
}

static void emit(umi_button_t *b, umi_gesture_kind_t kind, uint32_t t_ms)
{
    if (b->count == UMI_BUTTON_QUEUE_LEN) {
        /* The caller drains every tick, so this only drops under abuse; the
         * newest gesture matters most. */
        b->head = (uint8_t)((b->head + 1) % UMI_BUTTON_QUEUE_LEN);
        b->count--;
    }
    b->queue[(b->head + b->count) % UMI_BUTTON_QUEUE_LEN] = (umi_gesture_t){kind, t_ms};
    b->count++;
}

static void on_stable_edge(umi_button_t *b, uint32_t t_ms, bool pressed)
{
    switch (b->state) {
    case UMI_BUTTON_IDLE:
        if (pressed) {
            b->state = UMI_BUTTON_PRESSED;
            b->press_t_ms = t_ms;
            emit(b, UMI_GESTURE_DOWN, t_ms);
        }
        break;
    case UMI_BUTTON_PRESSED:
        if (!pressed) {
            b->state = UMI_BUTTON_RELEASED;
            b->release_t_ms = t_ms;
        }
        break;
    case UMI_BUTTON_RELEASED:
        if (pressed) {
            b->state = UMI_BUTTON_WAIT_UP;
            emit(b, UMI_GESTURE_DOUBLE, b->press_t_ms);
        }
        break;
    case UMI_BUTTON_WAIT_UP:
        if (!pressed) {
            b->state = UMI_BUTTON_IDLE;
        }
        break;
    }
}

static void advance(umi_button_t *b, uint32_t now_ms)
{
    /* A level counts once it has held for debounce_ms; it dates from its first
     * raw edge, so debouncing adds no error to gesture timings. */
    bool unsettled = b->raw_pressed != b->stable_pressed;
    if (unsettled && umi_elapsed_ms(now_ms, b->raw_t_ms) >= UMI_BUTTON_DEBOUNCE_MS) {
        b->stable_pressed = b->raw_pressed;
        unsettled = false;
        on_stable_edge(b, b->raw_t_ms, b->stable_pressed);
    }
    /* An edge still being debounced may land inside the hold or gap window, so
     * the timer waits for it rather than deciding on a level about to change. */
    if (b->state == UMI_BUTTON_PRESSED &&
        umi_elapsed_ms(now_ms, b->press_t_ms) >= UMI_BUTTON_HOLD_MS &&
        !(unsettled && umi_elapsed_ms(b->raw_t_ms, b->press_t_ms) < UMI_BUTTON_HOLD_MS)) {
        b->state = UMI_BUTTON_WAIT_UP;
        emit(b, UMI_GESTURE_HOLD, b->press_t_ms);
    } else if (b->state == UMI_BUTTON_RELEASED &&
               umi_elapsed_ms(now_ms, b->release_t_ms) > UMI_BUTTON_DOUBLE_PRESS_GAP_MS &&
               !(unsettled &&
                 umi_elapsed_ms(b->raw_t_ms, b->release_t_ms) <= UMI_BUTTON_DOUBLE_PRESS_GAP_MS)) {
        b->state = UMI_BUTTON_IDLE;
        emit(b, UMI_GESTURE_SHORT, b->press_t_ms);
    }
}

void umi_button_edge(umi_button_t *b, uint32_t t_ms, bool pressed)
{
    /* Settle everything that happened before this edge first, so a hold or a
     * gap that expired in between is decided in order. */
    advance(b, t_ms);
    if (pressed != b->raw_pressed) {
        b->raw_pressed = pressed;
        b->raw_t_ms = t_ms;
    }
}

void umi_button_tick(umi_button_t *b, uint32_t now_ms)
{
    advance(b, now_ms);
}

bool umi_button_next(umi_button_t *b, umi_gesture_t *out)
{
    if (b->count == 0) {
        return false;
    }
    *out = b->queue[b->head];
    b->head = (uint8_t)((b->head + 1) % UMI_BUTTON_QUEUE_LEN);
    b->count--;
    return true;
}

bool umi_button_pending_since(const umi_button_t *b, uint32_t *t_ms)
{
    if (b->state == UMI_BUTTON_PRESSED || b->state == UMI_BUTTON_RELEASED) {
        *t_ms = b->press_t_ms;
        return true;
    }
    if (b->state == UMI_BUTTON_IDLE && b->raw_pressed && !b->stable_pressed) {
        *t_ms = b->raw_t_ms;
        return true;
    }
    return false;
}
