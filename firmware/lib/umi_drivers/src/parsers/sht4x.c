#include "umi/drivers/sht4x.h"

#include "umi/bytes.h"

uint8_t umi_sht4x_crc8(const uint8_t *data, size_t len)
{
    uint8_t crc = 0xFF;
    for (size_t i = 0; i < len; i++) {
        crc ^= data[i];
        for (int bit = 0; bit < 8; bit++) {
            crc = (crc & 0x80) ? (uint8_t)((crc << 1) ^ 0x31) : (uint8_t)(crc << 1);
        }
    }
    return crc;
}

bool umi_sht4x_decode(const uint8_t raw[UMI_SHT4X_MEASURE_LEN], float *temp_c, float *rh_pct)
{
    if (umi_sht4x_crc8(raw, 2) != raw[2] || umi_sht4x_crc8(raw + 3, 2) != raw[5]) {
        return false;
    }
    float t_ticks = (float)umi_get_u16be(raw);
    float rh_ticks = (float)umi_get_u16be(raw + 3);
    *temp_c = -45.0f + 175.0f * t_ticks / 65535.0f;
    float rh = -6.0f + 125.0f * rh_ticks / 65535.0f;
    *rh_pct = rh < 0.0f ? 0.0f : rh > 100.0f ? 100.0f : rh;
    return true;
}
