#include "umi/drivers/esp32/clock.h"
#include "umi/drivers/esp32/sensors.h"

#define PMS_BAUD 9600
#define RX_BUFFER 256

esp_err_t umi_esp32_pm_init(umi_esp32_pm_t *p, uart_port_t port, gpio_num_t tx, gpio_num_t rx)
{
    *p = (umi_esp32_pm_t){.port = port};
    umi_pms_init(&p->pms);
    uart_config_t cfg = {
        .baud_rate = PMS_BAUD,
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

static bool poll(void *ctx, umi_pm_reading_t *out)
{
    umi_esp32_pm_t *p = ctx;
    uint8_t byte;
    /* A frame is 32 bytes a second: byte-wise reads cost nothing here. */
    while (uart_read_bytes(p->port, &byte, 1, 0) == 1) {
        umi_pms_frame_t frame;
        if (umi_pms_feed(&p->pms, byte, &frame)) {
            *out = (umi_pm_reading_t){
                .t_ms = umi_esp32_now_ms(),
                .pm1_ugm3 = frame.pm1_atm,
                .pm25_ugm3 = frame.pm25_atm,
                .pm10_ugm3 = frame.pm10_atm,
            };
            return true;
        }
    }
    return false;
}

umi_hal_pm_t umi_esp32_pm_hal(umi_esp32_pm_t *p)
{
    return (umi_hal_pm_t){.poll = poll, .ctx = p};
}
