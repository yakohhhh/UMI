/* Fixed-width integer packing. The session log and BLE payloads are little-endian;
 * a few sensor protocols (Plantower, Sensirion) are big-endian. */
#ifndef UMI_BYTES_H
#define UMI_BYTES_H

#include <stdint.h>

static inline void umi_put_u16le(uint8_t *p, uint16_t v)
{
    p[0] = (uint8_t)v;
    p[1] = (uint8_t)(v >> 8);
}

static inline void umi_put_u32le(uint8_t *p, uint32_t v)
{
    umi_put_u16le(p, (uint16_t)v);
    umi_put_u16le(p + 2, (uint16_t)(v >> 16));
}

static inline void umi_put_u64le(uint8_t *p, uint64_t v)
{
    umi_put_u32le(p, (uint32_t)v);
    umi_put_u32le(p + 4, (uint32_t)(v >> 32));
}

static inline void umi_put_i16le(uint8_t *p, int16_t v) { umi_put_u16le(p, (uint16_t)v); }
static inline void umi_put_i32le(uint8_t *p, int32_t v) { umi_put_u32le(p, (uint32_t)v); }
static inline void umi_put_i64le(uint8_t *p, int64_t v) { umi_put_u64le(p, (uint64_t)v); }

static inline uint16_t umi_get_u16le(const uint8_t *p)
{
    return (uint16_t)(p[0] | (uint16_t)(p[1] << 8));
}

static inline uint32_t umi_get_u32le(const uint8_t *p)
{
    return (uint32_t)umi_get_u16le(p) | ((uint32_t)umi_get_u16le(p + 2) << 16);
}

static inline uint64_t umi_get_u64le(const uint8_t *p)
{
    return (uint64_t)umi_get_u32le(p) | ((uint64_t)umi_get_u32le(p + 4) << 32);
}

static inline int16_t umi_get_i16le(const uint8_t *p) { return (int16_t)umi_get_u16le(p); }
static inline int32_t umi_get_i32le(const uint8_t *p) { return (int32_t)umi_get_u32le(p); }
static inline int64_t umi_get_i64le(const uint8_t *p) { return (int64_t)umi_get_u64le(p); }

static inline uint16_t umi_get_u16be(const uint8_t *p)
{
    return (uint16_t)((uint16_t)(p[0] << 8) | p[1]);
}

#endif /* UMI_BYTES_H */
