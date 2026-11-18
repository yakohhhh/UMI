#include "umi/drivers/esp32/clock.h"
#include "umi/drivers/esp32/sensors.h"

#define RX_BUFFER 1024

esp_err_t umi_esp32_gnss_init(umi_esp32_gnss_t *g, uart_port_t port, gpio_num_t tx, gpio_num_t rx,
                              int baud)
{
    *g = (umi_esp32_gnss_t){.port = port};
    umi_nmea_init(&g->nmea);
    uart_config_t cfg = {
        .baud_rate = baud,
        .data_bits = UART_DATA_8_BITS,
        .parity = UART_PARITY_DISABLE,
        .stop_bits = UART_STOP_BITS_1,
        .flow_ctrl = UART_HW_FLOWCTRL_DISABLE,
        .source_clk = UART_SCLK_DEFAULT,
    };
    esp_err_t err = uart_driver_install(port, RX_BUFFER, 0, 0, NULL, 0);
    if (err == ESP_OK) {
        err = uart_param_config(port, &cfg);
    }
    return err == ESP_OK ? uart_set_pin(port, tx, rx, UART_PIN_NO_CHANGE, UART_PIN_NO_CHANGE) : err;
}

static bool poll(void *ctx, umi_gnss_fix_t *out)
{
    umi_esp32_gnss_t *g = ctx;
    for (;;) {
        if (g->pos == g->len) {
            int n = uart_read_bytes(g->port, g->buf, sizeof g->buf, 0);
            if (n <= 0) {
                return false;
            }
            g->len = (size_t)n;
            g->pos = 0;
        }
        /* Bytes after a completed epoch stay buffered for the next poll. */
        while (g->pos < g->len) {
            if (umi_nmea_feed_byte(&g->nmea, (char)g->buf[g->pos++], umi_esp32_now_ms(), out)) {
                return true;
            }
        }
    }
}

umi_hal_gnss_t umi_esp32_gnss_hal(umi_esp32_gnss_t *g)
{
    return (umi_hal_gnss_t){.poll = poll, .ctx = g};
}
