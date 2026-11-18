/* Device time is a u32 millisecond counter that wraps after ~49 days, so times
 * are only ever compared through their difference. */
#ifndef UMI_CORE_TIME_H
#define UMI_CORE_TIME_H

#include <stdbool.h>
#include <stdint.h>

static inline uint32_t umi_elapsed_ms(uint32_t now_ms, uint32_t since_ms)
{
    return now_ms - since_ms;
}

/* True when a is strictly earlier than b. */
static inline bool umi_time_before(uint32_t a, uint32_t b)
{
    return (int32_t)(a - b) < 0;
}

static inline uint32_t umi_time_min(uint32_t a, uint32_t b)
{
    return umi_time_before(a, b) ? a : b;
}

#endif /* UMI_CORE_TIME_H */
