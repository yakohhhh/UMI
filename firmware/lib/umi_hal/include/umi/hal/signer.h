/* Flag signer (ADR 0005): ECDSA P-256 over SHA-256 of the message, raw r || s.
 * The private key never leaves the implementation. */
#ifndef UMI_HAL_SIGNER_H
#define UMI_HAL_SIGNER_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "umi/protocol_gen.h"

#define UMI_PUBLIC_KEY_LEN 65 /* uncompressed SEC1 point: 0x04 || X || Y */

typedef struct {
    uint8_t alg; /* umi_sig_alg_t; UMI_SIG_ALG_NONE means flags stay unsigned */
    bool (*sign)(void *ctx, const uint8_t *msg, size_t len,
                 uint8_t sig[UMI_SIGNING_SIGNATURE_LEN]);
    bool (*public_key)(void *ctx, uint8_t out[UMI_PUBLIC_KEY_LEN]);
    void *ctx;
} umi_hal_signer_t;

#endif /* UMI_HAL_SIGNER_H */
