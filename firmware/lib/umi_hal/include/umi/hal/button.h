/* The sealed flag button: raw contact edges, bounces included. Debouncing and
 * gestures are umi_core's job so they are the same on every target. */
#ifndef UMI_HAL_BUTTON_H
#define UMI_HAL_BUTTON_H

#include <stdbool.h>
#include <stdint.h>

typedef struct {
    uint32_t t_ms;
    bool pressed;
} umi_button_edge_t;

typedef struct {
    bool (*poll)(void *ctx, umi_button_edge_t *out);
    void *ctx;
} umi_hal_button_t;

#endif /* UMI_HAL_BUTTON_H */
