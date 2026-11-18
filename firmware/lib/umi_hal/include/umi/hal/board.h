/* Board housekeeping that has no better home: the SoC's own temperature. */
#ifndef UMI_HAL_BOARD_H
#define UMI_HAL_BOARD_H

#include <stdbool.h>
#include <stdint.h>

typedef struct {
    bool (*temp_cc)(void *ctx, int16_t *out); /* 0.01 °C */
    void *ctx;
} umi_hal_board_t;

#endif /* UMI_HAL_BOARD_H */
