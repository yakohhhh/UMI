/* Plantower PMS frame parser (PMSA003, PMS5003...): 32-byte frames
 * 42 4D | length 28 | 13 x u16 data | u16 sum of the previous 30 bytes,
 * all big-endian. Pure C, used by the UART driver and the simulated sensor. */
#ifndef UMI_DRIVERS_PMS_H
#define UMI_DRIVERS_PMS_H

#include <stdbool.h>
#include <stdint.h>

#define UMI_PMS_FRAME_LEN 32

typedef struct {
    uint16_t pm1_cf1; /* "standard particle", factory calibration */
    uint16_t pm25_cf1;
    uint16_t pm10_cf1;
    uint16_t pm1_atm; /* "atmospheric environment": what ambient monitoring uses */
    uint16_t pm25_atm;
    uint16_t pm10_atm;
} umi_pms_frame_t;

bool umi_pms_parse(const uint8_t frame[UMI_PMS_FRAME_LEN], umi_pms_frame_t *out);

/* Byte-stream reassembly with resynchronisation on the 42 4D start bytes. */
typedef struct {
    uint8_t buf[UMI_PMS_FRAME_LEN];
    uint8_t len;
    uint32_t rejected;
} umi_pms_t;

void umi_pms_init(umi_pms_t *p);
bool umi_pms_feed(umi_pms_t *p, uint8_t byte, umi_pms_frame_t *out);

#endif /* UMI_DRIVERS_PMS_H */
