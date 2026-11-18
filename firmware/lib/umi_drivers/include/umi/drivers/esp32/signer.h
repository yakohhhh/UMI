/* Flag signer on the Clip: ECDSA P-256 / SHA-256 through PSA Crypto (mbedTLS),
 * deterministic (RFC 6979) like the reference signer.
 *
 * The key is generated on the device at first boot and kept in NVS. That is
 * the devkit-grade half of ADR 0005: production keeps it under NVS encryption
 * with flash encryption and secure boot, which are enabled at provisioning
 * (docs/hardware/assumptions.md, bring-up checklist). */
#ifndef UMI_DRIVERS_ESP32_SIGNER_H
#define UMI_DRIVERS_ESP32_SIGNER_H

#include <stdint.h>

#include "esp_err.h"
#include "nvs.h"
#include "psa/crypto.h"
#include "umi/hal/signer.h"

typedef struct {
    psa_key_id_t key;
    uint8_t public_key[UMI_PUBLIC_KEY_LEN];
} umi_esp32_signer_t;

esp_err_t umi_esp32_signer_init(umi_esp32_signer_t *s, nvs_handle_t nvs);
umi_hal_signer_t umi_esp32_signer_hal(umi_esp32_signer_t *s);

#endif /* UMI_DRIVERS_ESP32_SIGNER_H */
