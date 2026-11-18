/* Rider settings, written by the phone through the BLE Settings characteristic
 * (protocol/README.md §4) as TLV: type u8, length u8, value. */
#ifndef UMI_CORE_SETTINGS_H
#define UMI_CORE_SETTINGS_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

typedef enum {
    UMI_SETTING_VOICE = 0x01,
    UMI_SETTING_LANGUAGES = 0x02,
    UMI_SETTING_CHIRP = 0x03,
    UMI_SETTING_WARN_AHEAD = 0x04,
    UMI_SETTING_SENSORS = 0x05,
} umi_setting_id_t;

/* Languages bitmask: bit (lang - 1) for each umi_lang_t except none. */
#define UMI_LANG_BIT(lang) ((uint8_t)(1u << ((lang) - 1u)))

/* Sensors bitmask: what the rider lets the Clip measure. */
typedef enum {
    UMI_SENSOR_AIR = 0x01,   /* PM and temperature / humidity */
    UMI_SENSOR_NOISE = 0x02, /* microphone, dB(A) only */
} umi_sensor_bit_t;

typedef struct {
    bool voice;          /* voice keywords: opt-in */
    uint8_t languages;
    bool chirp;          /* confirmation chirps for presses */
    bool warn_ahead;     /* chirps near verified hazards: opt-in */
    uint8_t sensors;
} umi_settings_t;

/* Product defaults (README "Clip settings"): voice and warn-ahead off. */
umi_settings_t umi_settings_default(void);

/* Every setting as TLV; returns the length written, 0 if cap is too small. */
size_t umi_settings_encode(const umi_settings_t *s, uint8_t *out, size_t cap);

/* Applies a TLV write. Unknown types are skipped (forward compatibility); a
 * truncated item rejects the whole write and leaves *s unchanged. */
bool umi_settings_apply(umi_settings_t *s, const uint8_t *tlv, size_t len);

#endif /* UMI_CORE_SETTINGS_H */
