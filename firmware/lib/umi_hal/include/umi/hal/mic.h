/* MEMS microphone. The PCM stream only ever reaches the in-firmware SPL meter
 * and the keyword recogniser: it is never stored or sent (ADR 0006). */
#ifndef UMI_HAL_MIC_H
#define UMI_HAL_MIC_H

#include <stddef.h>
#include <stdint.h>

typedef struct {
    uint32_t sample_rate_hz;
    /* Copies up to max mono samples captured since the previous call, as Q31
     * (full scale = INT32_MAX), oldest first. */
    size_t (*read)(void *ctx, int32_t *pcm, size_t max);
    void *ctx;
} umi_hal_mic_t;

#endif /* UMI_HAL_MIC_H */
