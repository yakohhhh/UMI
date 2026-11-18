#include "umi/drivers/esp32/signer.h"

#include <string.h>

#define KEY_NVS_NAME "flag_key"
#define KEY_BITS 256
#define KEY_LEN (KEY_BITS / 8)
#define ALG PSA_ALG_DETERMINISTIC_ECDSA(PSA_ALG_SHA_256)

static psa_key_attributes_t attributes(psa_key_usage_t usage)
{
    psa_key_attributes_t attr = PSA_KEY_ATTRIBUTES_INIT;
    psa_set_key_type(&attr, PSA_KEY_TYPE_ECC_KEY_PAIR(PSA_ECC_FAMILY_SECP_R1));
    psa_set_key_bits(&attr, KEY_BITS);
    psa_set_key_usage_flags(&attr, usage);
    psa_set_key_algorithm(&attr, ALG);
    return attr;
}

/* First boot: a fresh key, exported once to be persisted. */
static esp_err_t create_key(umi_esp32_signer_t *s, nvs_handle_t nvs)
{
    psa_key_attributes_t attr = attributes(PSA_KEY_USAGE_SIGN_MESSAGE | PSA_KEY_USAGE_EXPORT);
    if (psa_generate_key(&attr, &s->key) != PSA_SUCCESS) {
        return ESP_FAIL;
    }
    uint8_t raw[KEY_LEN];
    size_t len = 0;
    psa_status_t status = psa_export_key(s->key, raw, sizeof raw, &len);
    esp_err_t err = status == PSA_SUCCESS && len == KEY_LEN ? nvs_set_blob(nvs, KEY_NVS_NAME, raw, len)
                                                             : ESP_FAIL;
    memset(raw, 0, sizeof raw);
    return err == ESP_OK ? nvs_commit(nvs) : err;
}

static esp_err_t load_key(umi_esp32_signer_t *s, const uint8_t raw[KEY_LEN])
{
    psa_key_attributes_t attr = attributes(PSA_KEY_USAGE_SIGN_MESSAGE);
    return psa_import_key(&attr, raw, KEY_LEN, &s->key) == PSA_SUCCESS ? ESP_OK : ESP_FAIL;
}

esp_err_t umi_esp32_signer_init(umi_esp32_signer_t *s, nvs_handle_t nvs)
{
    if (psa_crypto_init() != PSA_SUCCESS) {
        return ESP_FAIL;
    }
    uint8_t raw[KEY_LEN];
    size_t len = sizeof raw;
    esp_err_t err = nvs_get_blob(nvs, KEY_NVS_NAME, raw, &len);
    if (err == ESP_OK && len == KEY_LEN) {
        err = load_key(s, raw);
    } else if (err == ESP_ERR_NVS_NOT_FOUND) {
        err = create_key(s, nvs);
    } else {
        err = ESP_ERR_INVALID_SIZE;
    }
    memset(raw, 0, sizeof raw);
    if (err != ESP_OK) {
        return err;
    }
    size_t pub_len = 0;
    psa_status_t status = psa_export_public_key(s->key, s->public_key, sizeof s->public_key, &pub_len);
    return status == PSA_SUCCESS && pub_len == UMI_PUBLIC_KEY_LEN ? ESP_OK : ESP_FAIL;
}

static bool sign(void *ctx, const uint8_t *msg, size_t len, uint8_t sig[UMI_SIGNING_SIGNATURE_LEN])
{
    umi_esp32_signer_t *s = ctx;
    size_t sig_len = 0;
    /* PSA's ECDSA output is already raw r || s, big-endian. */
    psa_status_t status =
        psa_sign_message(s->key, ALG, msg, len, sig, UMI_SIGNING_SIGNATURE_LEN, &sig_len);
    return status == PSA_SUCCESS && sig_len == UMI_SIGNING_SIGNATURE_LEN;
}

static bool public_key(void *ctx, uint8_t out[UMI_PUBLIC_KEY_LEN])
{
    umi_esp32_signer_t *s = ctx;
    memcpy(out, s->public_key, UMI_PUBLIC_KEY_LEN);
    return true;
}

umi_hal_signer_t umi_esp32_signer_hal(umi_esp32_signer_t *s)
{
    return (umi_hal_signer_t){
        .alg = UMI_SIG_ALG_ECDSA_P256,
        .sign = sign,
        .public_key = public_key,
        .ctx = s,
    };
}
