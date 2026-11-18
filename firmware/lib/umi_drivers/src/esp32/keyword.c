/* Keyword recogniser: blocked on hardware. It needs the mic in its housing,
 * the 8 MB PSRAM and a keyword model trained on Catalan, Spanish and English
 * with Barcelona wind and traffic noise (docs/signalement-mains-libres.md,
 * "À valider avant de promettre la voix"). Until then a voice window never
 * hears a keyword: it times out and the flag is kept without a kind, which is
 * exactly the product's fallback. */
#include "umi/drivers/esp32/sensors.h"

static void start(void *ctx)
{
    (void)ctx;
}

static bool poll(void *ctx, umi_keyword_result_t *out)
{
    (void)ctx;
    (void)out;
    return false;
}

static void stop(void *ctx)
{
    (void)ctx;
}

umi_hal_keyword_t umi_esp32_keyword_hal(void)
{
    return (umi_hal_keyword_t){.start = start, .poll = poll, .stop = stop, .ctx = NULL};
}
