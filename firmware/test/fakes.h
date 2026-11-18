/* Test doubles shared by the unit test suites (compiled into each of them). */
#ifndef UMI_TEST_FAKES_H
#define UMI_TEST_FAKES_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "umi/hal/hal.h"
#include "umi/session_log.h"

/* RAM storage keeping the bytes of the last session opened. */
typedef struct {
    uint8_t data[32 * 1024];
    size_t len;
    bool open;
    bool fail_writes;
    uint32_t next_id;
    uint32_t opened;
    uint32_t closed;
    uint32_t flushes;
    uint32_t free_kib;
} fake_storage_t;

void fake_storage_init(fake_storage_t *s, uint32_t first_id);
umi_hal_storage_t fake_storage_hal(fake_storage_t *s);

/* Buzzer and LED that remember every change. */
#define FAKE_INDICATOR_LOG 64

typedef struct {
    uint16_t tone_hz;
    umi_led_color_t led;
    uint16_t tones[FAKE_INDICATOR_LOG]; /* every non-zero tone started, in order */
    size_t tone_count;
    size_t led_changes;
} fake_indicator_t;

void fake_indicator_init(fake_indicator_t *f);
umi_hal_buzzer_t fake_buzzer_hal(fake_indicator_t *f);
umi_hal_led_t fake_led_hal(fake_indicator_t *f);

/* A decoded session log. */
#define FAKE_LOG_MAX_RECORDS 400

typedef struct {
    umi_header_t header;
    umi_log_result_t result; /* UMI_LOG_END for a complete log */
    umi_record_t records[FAKE_LOG_MAX_RECORDS];
    size_t count;
} fake_log_t;

/* Reads a whole log; result is the open error or the last reader result. */
void fake_log_read(fake_log_t *log, const uint8_t *data, size_t len);

/* Number of records of a type, and the i-th of them (NULL if none). */
size_t fake_log_count(const fake_log_t *log, uint8_t type);
const umi_record_t *fake_log_find(const fake_log_t *log, uint8_t type, size_t index);

#endif /* UMI_TEST_FAKES_H */
