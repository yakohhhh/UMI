/* The ESP32-S3's internal temperature sensor (STATUS.board_temp_cc). */
#ifndef UMI_DRIVERS_ESP32_BOARD_H
#define UMI_DRIVERS_ESP32_BOARD_H

#include "driver/temperature_sensor.h"
#include "esp_err.h"
#include "umi/hal/board.h"

typedef struct {
    temperature_sensor_handle_t sensor;
} umi_esp32_board_t;

esp_err_t umi_esp32_board_init(umi_esp32_board_t *b);
umi_hal_board_t umi_esp32_board_hal(umi_esp32_board_t *b);

#endif /* UMI_DRIVERS_ESP32_BOARD_H */
