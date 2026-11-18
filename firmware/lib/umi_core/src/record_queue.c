#include "umi/core/record_queue.h"

#include <string.h>

void umi_record_queue_init(umi_record_queue_t *q)
{
    q->count = 0;
}

bool umi_record_queue_push(umi_record_queue_t *q, const umi_record_t *rec)
{
    if (q->count == UMI_RECORD_QUEUE_LEN) {
        return false;
    }
    uint32_t t_ms = umi_record_t_ms(rec);
    size_t at = q->count;
    while (at > 0 && umi_record_t_ms(&q->items[at - 1]) > t_ms) {
        at--;
    }
    memmove(&q->items[at + 1], &q->items[at], (q->count - at) * sizeof q->items[0]);
    q->items[at] = *rec;
    q->count++;
    return true;
}

bool umi_record_queue_pop(umi_record_queue_t *q, umi_record_t *out)
{
    if (q->count == 0) {
        return false;
    }
    *out = q->items[0];
    q->count--;
    memmove(&q->items[0], &q->items[1], q->count * sizeof q->items[0]);
    return true;
}

bool umi_record_queue_pop_until(umi_record_queue_t *q, uint32_t horizon_ms, umi_record_t *out)
{
    if (q->count == 0 || umi_record_t_ms(&q->items[0]) > horizon_ms) {
        return false;
    }
    return umi_record_queue_pop(q, out);
}
