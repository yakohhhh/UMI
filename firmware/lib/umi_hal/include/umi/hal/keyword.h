/* On-device keyword recogniser, listening only while the voice window is open. */
#ifndef UMI_HAL_KEYWORD_H
#define UMI_HAL_KEYWORD_H

#include <stdbool.h>
#include <stdint.h>

typedef struct {
    uint8_t kind;       /* umi_hazard_kind_t */
    uint8_t confidence; /* 0-100 */
    uint8_t lang;       /* umi_lang_t */
} umi_keyword_result_t;

typedef struct {
    void (*start)(void *ctx);
    /* Returns true once, when the recogniser has a result for this window. */
    bool (*poll)(void *ctx, umi_keyword_result_t *out);
    void (*stop)(void *ctx);
    void *ctx;
} umi_hal_keyword_t;

#endif /* UMI_HAL_KEYWORD_H */
