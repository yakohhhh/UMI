#include "fakes.h"

#include <string.h>

void fake_storage_init(fake_storage_t *s, uint32_t first_id)
{
    memset(s, 0, sizeof *s);
    s->next_id = first_id;
    s->free_kib = 10000;
}

static bool next_session_id(void *ctx, uint32_t *out)
{
    fake_storage_t *s = ctx;
    *out = s->next_id++;
    return true;
}

static bool open_session(void *ctx, uint32_t session_id)
{
    (void)session_id;
    fake_storage_t *s = ctx;
    s->len = 0;
    s->open = true;
    s->opened++;
    return true;
}

static bool write_bytes(void *ctx, const uint8_t *data, size_t len)
{
    fake_storage_t *s = ctx;
    if (!s->open || s->fail_writes || s->len + len > sizeof s->data) {
        return false;
    }
    memcpy(s->data + s->len, data, len);
    s->len += len;
    return true;
}

static bool flush(void *ctx)
{
    fake_storage_t *s = ctx;
    s->flushes++;
    return true;
}

static bool close_session(void *ctx)
{
    fake_storage_t *s = ctx;
    s->open = false;
    s->closed++;
    return true;
}

static uint32_t free_kib(void *ctx)
{
    fake_storage_t *s = ctx;
    return s->free_kib;
}

umi_hal_storage_t fake_storage_hal(fake_storage_t *s)
{
    return (umi_hal_storage_t){
        .next_session_id = next_session_id,
        .open = open_session,
        .write = write_bytes,
        .flush = flush,
        .close = close_session,
        .free_kib = free_kib,
        .ctx = s,
    };
}

void fake_indicator_init(fake_indicator_t *f)
{
    memset(f, 0, sizeof *f);
}

static void tone(void *ctx, uint16_t hz)
{
    fake_indicator_t *f = ctx;
    if (hz != 0 && f->tone_hz != hz && f->tone_count < FAKE_INDICATOR_LOG) {
        f->tones[f->tone_count++] = hz;
    }
    f->tone_hz = hz;
}

static void led(void *ctx, umi_led_color_t color)
{
    fake_indicator_t *f = ctx;
    if (color != f->led) {
        f->led_changes++;
    }
    f->led = color;
}

umi_hal_buzzer_t fake_buzzer_hal(fake_indicator_t *f)
{
    return (umi_hal_buzzer_t){.tone = tone, .ctx = f};
}

umi_hal_led_t fake_led_hal(fake_indicator_t *f)
{
    return (umi_hal_led_t){.set = led, .ctx = f};
}

void fake_log_read(fake_log_t *log, const uint8_t *data, size_t len)
{
    umi_log_reader_t reader;
    log->count = 0;
    log->result = umi_log_reader_open(&reader, data, len, &log->header);
    if (log->result != UMI_LOG_RECORD) {
        return;
    }
    umi_record_t rec;
    while ((log->result = umi_log_reader_next(&reader, &rec)) == UMI_LOG_RECORD) {
        if (log->count < FAKE_LOG_MAX_RECORDS) {
            log->records[log->count++] = rec;
        }
    }
}

size_t fake_log_count(const fake_log_t *log, uint8_t type)
{
    size_t n = 0;
    for (size_t i = 0; i < log->count; i++) {
        n += log->records[i].type == type;
    }
    return n;
}

const umi_record_t *fake_log_find(const fake_log_t *log, uint8_t type, size_t index)
{
    for (size_t i = 0; i < log->count; i++) {
        if (log->records[i].type == type && index-- == 0) {
            return &log->records[i];
        }
    }
    return NULL;
}
