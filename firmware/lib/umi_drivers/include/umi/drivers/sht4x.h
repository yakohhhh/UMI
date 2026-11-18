/* Sensirion SHT4x (SHT40) measurement decoding: 6 bytes, temperature and
 * humidity words each followed by a CRC-8 (poly 0x31, init 0xFF). */
#ifndef UMI_DRIVERS_SHT4X_H
#define UMI_DRIVERS_SHT4X_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define UMI_SHT4X_CMD_MEASURE_HIGH 0xFD /* high repeatability, ~9 ms */
#define UMI_SHT4X_MEASURE_LEN 6

uint8_t umi_sht4x_crc8(const uint8_t *data, size_t len);

/* Fails on a CRC mismatch; humidity is clamped to 0-100 % as the datasheet
 * recommends. */
bool umi_sht4x_decode(const uint8_t raw[UMI_SHT4X_MEASURE_LEN], float *temp_c, float *rh_pct);

#endif /* UMI_DRIVERS_SHT4X_H */
