/* Reorder buffer in front of the log writer. Records must be written in
 * non-decreasing t_ms, but some are only known after later ones: a flag is
 * dated at the press yet decided after the double-press gap or the voice
 * window, a brake is dated at its start yet confirmed by the next fix. Records
 * wait here, sorted, until no producer can still emit an older one. */
#ifndef UMI_CORE_RECORD_QUEUE_H
#define UMI_CORE_RECORD_QUEUE_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "umi/records.h"

/* Records wait at most hold_ms + voice_window_ms (a voice flag) plus the
 * application's one-second settle time: about a dozen records at the
 * recorder's rates, so 24 leaves room for bursts of events and flags. */
#define UMI_RECORD_QUEUE_LEN 24

typedef struct {
    umi_record_t items[UMI_RECORD_QUEUE_LEN]; /* sorted by t_ms, stable */
    size_t count;
} umi_record_queue_t;

void umi_record_queue_init(umi_record_queue_t *q);

/* Inserts after any record with the same t_ms. Fails when full. */
bool umi_record_queue_push(umi_record_queue_t *q, const umi_record_t *rec);

/* Removes the oldest record if its t_ms is at most horizon_ms. */
bool umi_record_queue_pop_until(umi_record_queue_t *q, uint32_t horizon_ms, umi_record_t *out);

/* Removes the oldest record regardless of time. */
bool umi_record_queue_pop(umi_record_queue_t *q, umi_record_t *out);

#endif /* UMI_CORE_RECORD_QUEUE_H */
