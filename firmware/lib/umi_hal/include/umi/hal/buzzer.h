/* Piezo buzzer. */
#ifndef UMI_HAL_BUZZER_H
#define UMI_HAL_BUZZER_H

#include <stdint.h>

typedef struct {
    void (*tone)(void *ctx, uint16_t hz); /* 0 = silent */
    void *ctx;
} umi_hal_buzzer_t;

#endif /* UMI_HAL_BUZZER_H */
