/* Status LED. Colour never carries meaning alone: chirps always come with it. */
#ifndef UMI_HAL_LED_H
#define UMI_HAL_LED_H

typedef enum {
    UMI_LED_OFF,
    UMI_LED_ORANGE,
} umi_led_color_t;

typedef struct {
    void (*set)(void *ctx, umi_led_color_t color);
    void *ctx;
} umi_hal_led_t;

#endif /* UMI_HAL_LED_H */
