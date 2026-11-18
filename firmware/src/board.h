/* Pin maps. The devkit map uses what the ESP32-S3-DevKitC-1 has on board (BOOT
 * button, RGB LED) plus a piezo; the Clip map is a draft until the board
 * schematic exists (docs/hardware/assumptions.md). Both avoid the strapping
 * pins and GPIO 33-37, which the N16R8 module's octal PSRAM uses. */
#ifndef UMI_BOARD_H
#define UMI_BOARD_H

#include "driver/gpio.h"
#include "driver/uart.h"

#if UMI_HW_SIM

#define UMI_PIN_BUTTON GPIO_NUM_0 /* BOOT button, active low */
#define UMI_PIN_LED GPIO_NUM_48   /* on-board WS2812 (GPIO 38 on board v1.1) */
#define UMI_PIN_BUZZER GPIO_NUM_4 /* external piezo through a transistor */

#else

#define UMI_PIN_BUTTON GPIO_NUM_1
#define UMI_PIN_LED GPIO_NUM_38
#define UMI_PIN_BUZZER GPIO_NUM_2
#define UMI_PIN_I2C_SDA GPIO_NUM_8 /* IMU, SHT40, MAX17048 */
#define UMI_PIN_I2C_SCL GPIO_NUM_9
#define UMI_GNSS_UART UART_NUM_1
#define UMI_PIN_GNSS_TX GPIO_NUM_17 /* to the receiver's RX */
#define UMI_PIN_GNSS_RX GPIO_NUM_18
#define UMI_GNSS_BAUD 9600          /* u-blox factory default */
#define UMI_PM_UART UART_NUM_2
#define UMI_PIN_PM_TX GPIO_NUM_10
#define UMI_PIN_PM_RX GPIO_NUM_11
#define UMI_PIN_MIC_BCLK GPIO_NUM_5
#define UMI_PIN_MIC_WS GPIO_NUM_6
#define UMI_PIN_MIC_SD GPIO_NUM_7

#endif

/* One rate for the SPL meter and the keyword recogniser. */
#define UMI_MIC_RATE_HZ 16000u

#endif /* UMI_BOARD_H */
