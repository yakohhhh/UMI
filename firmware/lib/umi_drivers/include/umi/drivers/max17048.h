/* Maxim MAX17048 fuel gauge register decoding (big-endian 16-bit registers). */
#ifndef UMI_DRIVERS_MAX17048_H
#define UMI_DRIVERS_MAX17048_H

#include <stdint.h>

#define UMI_MAX17048_I2C_ADDR 0x36
#define UMI_MAX17048_REG_VCELL 0x02
#define UMI_MAX17048_REG_SOC 0x04
#define UMI_MAX17048_REG_CRATE 0x16

/* VCELL: 78.125 µV per LSB. */
static inline uint16_t umi_max17048_mv(uint16_t vcell)
{
    return (uint16_t)(((uint32_t)vcell * 5u + 32u) / 64u);
}

/* SOC: 1/256 % per LSB; the gauge may report slightly over 100 % when full. */
static inline uint8_t umi_max17048_pct(uint16_t soc)
{
    uint32_t pct = ((uint32_t)soc + 128u) >> 8;
    return pct > 100u ? 100u : (uint8_t)pct;
}

/* CRATE: signed, 0.208 %/h per LSB; positive while charging. */
static inline int32_t umi_max17048_crate_milli_pct_h(uint16_t crate)
{
    return (int32_t)(int16_t)crate * 208;
}

#endif /* UMI_DRIVERS_MAX17048_H */
