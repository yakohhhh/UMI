/* Checksums of the session log (protocol/README.md §1). Both are incremental:
 * pass the previous result back in to continue over more data. */
#ifndef UMI_CRC_H
#define UMI_CRC_H

#include <stddef.h>
#include <stdint.h>

/* CRC-16/CCITT-FALSE (poly 0x1021, init 0xFFFF, no reflection, no xor-out). */
#define UMI_CRC16_INIT 0xFFFFu
uint16_t umi_crc16_update(uint16_t crc, const void *data, size_t len);

/* CRC-32/ISO-HDLC, identical to zlib's crc32(): start from 0. */
#define UMI_CRC32_INIT 0u
uint32_t umi_crc32_update(uint32_t crc, const void *data, size_t len);

#endif /* UMI_CRC_H */
