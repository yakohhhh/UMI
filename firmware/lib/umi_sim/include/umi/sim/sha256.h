/* SHA-256 (FIPS 180-4) for the software signer. The Clip uses mbedTLS/PSA;
 * this keeps the host build free of a crypto library dependency. */
#ifndef UMI_SIM_SHA256_H
#define UMI_SIM_SHA256_H

#include <stddef.h>
#include <stdint.h>

#define UMI_SHA256_LEN 32
#define UMI_SHA256_BLOCK_LEN 64

typedef struct {
    uint32_t state[8];
    uint64_t total_len;
    uint8_t block[UMI_SHA256_BLOCK_LEN];
    size_t block_len;
} umi_sha256_t;

void umi_sha256_init(umi_sha256_t *h);
void umi_sha256_update(umi_sha256_t *h, const void *data, size_t len);
void umi_sha256_final(umi_sha256_t *h, uint8_t out[UMI_SHA256_LEN]);
void umi_sha256(const void *data, size_t len, uint8_t out[UMI_SHA256_LEN]);

/* HMAC-SHA-256 (RFC 2104), for RFC 6979 nonces. Keys up to one block. */
typedef struct {
    umi_sha256_t inner;
    uint8_t outer_key[UMI_SHA256_BLOCK_LEN];
} umi_hmac_sha256_t;

void umi_hmac_sha256_init(umi_hmac_sha256_t *h, const uint8_t *key, size_t key_len);
void umi_hmac_sha256_update(umi_hmac_sha256_t *h, const void *data, size_t len);
void umi_hmac_sha256_final(umi_hmac_sha256_t *h, uint8_t out[UMI_SHA256_LEN]);

#endif /* UMI_SIM_SHA256_H */
