/* Software flag signer for simulated Clips (ADR 0005: simulated and devkit
 * Clips use software keys and set the simulated header flag). ECDSA P-256
 * with deterministic nonces (RFC 6979), so a SIL run is reproducible byte for
 * byte. */
#ifndef UMI_SIM_SOFT_SIGNER_H
#define UMI_SIM_SOFT_SIGNER_H

#include <stdbool.h>
#include <stdint.h>

#include "umi/hal/signer.h"

#define UMI_PRIVATE_KEY_LEN 32

typedef struct {
    uint8_t private_key[UMI_PRIVATE_KEY_LEN];
    uint8_t public_key[UMI_PUBLIC_KEY_LEN];
} umi_soft_signer_t;

/* Fails if the key is not a valid P-256 scalar. */
bool umi_soft_signer_init(umi_soft_signer_t *s, const uint8_t private_key[UMI_PRIVATE_KEY_LEN]);

umi_hal_signer_t umi_soft_signer_hal(umi_soft_signer_t *s);

#endif /* UMI_SIM_SOFT_SIGNER_H */
