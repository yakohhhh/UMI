#include "umi/core/settings.h"

#include "umi/protocol_gen.h"

umi_settings_t umi_settings_default(void)
{
    return (umi_settings_t){
        .voice = false,
        .languages = UMI_LANG_BIT(UMI_LANG_CA) | UMI_LANG_BIT(UMI_LANG_ES) |
                     UMI_LANG_BIT(UMI_LANG_EN),
        .chirp = true,
        .warn_ahead = false,
        .sensors = UMI_SENSOR_AIR | UMI_SENSOR_NOISE,
    };
}

size_t umi_settings_encode(const umi_settings_t *s, uint8_t *out, size_t cap)
{
    const uint8_t items[][2] = {
        {UMI_SETTING_VOICE, s->voice},
        {UMI_SETTING_LANGUAGES, s->languages},
        {UMI_SETTING_CHIRP, s->chirp},
        {UMI_SETTING_WARN_AHEAD, s->warn_ahead},
        {UMI_SETTING_SENSORS, s->sensors},
    };
    size_t n = sizeof items / sizeof items[0];
    if (cap < n * 3) {
        return 0;
    }
    for (size_t i = 0; i < n; i++) {
        out[3 * i] = items[i][0];
        out[3 * i + 1] = 1;
        out[3 * i + 2] = items[i][1];
    }
    return n * 3;
}

bool umi_settings_apply(umi_settings_t *s, const uint8_t *tlv, size_t len)
{
    umi_settings_t next = *s;
    size_t pos = 0;
    while (pos < len) {
        if (len - pos < 2 || len - pos - 2 < tlv[pos + 1]) {
            return false;
        }
        uint8_t type = tlv[pos];
        uint8_t item_len = tlv[pos + 1];
        const uint8_t *value = &tlv[pos + 2];
        pos += 2u + item_len;
        if (item_len < 1) {
            continue;
        }
        switch (type) {
        case UMI_SETTING_VOICE:
            next.voice = value[0] != 0;
            break;
        case UMI_SETTING_LANGUAGES:
            next.languages = value[0];
            break;
        case UMI_SETTING_CHIRP:
            next.chirp = value[0] != 0;
            break;
        case UMI_SETTING_WARN_AHEAD:
            next.warn_ahead = value[0] != 0;
            break;
        case UMI_SETTING_SENSORS:
            next.sensors = value[0];
            break;
        default:
            break;
        }
    }
    *s = next;
    return true;
}
