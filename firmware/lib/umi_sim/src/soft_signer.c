#include "umi/sim/soft_signer.h"

#include <string.h>

#include "uECC.h"
#include "uECC_vli.h"
#include "umi/sim/sha256.h"

/* micro-ecc's own deterministic signing loads the HMAC-DRBG output without
 * bits2int, so its nonces are not RFC 6979's. The backend's reference signer
 * (umi_protocol.signing) is RFC 6979, and golden vectors must match byte for
 * byte, so the nonce is derived here and the two ECDSA equations run on
 * micro-ecc's vetted field and point arithmetic. */

#define SCALAR_LEN 32
#define WORDS (SCALAR_LEN / uECC_WORD_SIZE)
/* A retry is needed with probability ~2^-128; bounded all the same. */
#define MAX_NONCE_TRIES 16

typedef struct {
    uint8_t k[UMI_SHA256_LEN];
    uint8_t v[UMI_SHA256_LEN];
} drbg_t;

static void hmac(const uint8_t key[UMI_SHA256_LEN], const uint8_t *a, size_t a_len,
                 const uint8_t *b, size_t b_len, const uint8_t *c, size_t c_len,
                 uint8_t out[UMI_SHA256_LEN])
{
    umi_hmac_sha256_t h;
    umi_hmac_sha256_init(&h, key, UMI_SHA256_LEN);
    umi_hmac_sha256_update(&h, a, a_len);
    umi_hmac_sha256_update(&h, b, b_len);
    umi_hmac_sha256_update(&h, c, c_len);
    umi_hmac_sha256_final(&h, out);
}

/* RFC 6979 §3.2 steps b-f for qlen = hlen = 256. */
static void drbg_init(drbg_t *d, const uint8_t x[SCALAR_LEN], const uint8_t h1_mod_n[SCALAR_LEN])
{
    memset(d->v, 0x01, sizeof d->v);
    memset(d->k, 0x00, sizeof d->k);
    for (uint8_t sep = 0; sep <= 1; sep++) {
        uint8_t v_sep[UMI_SHA256_LEN + 1];
        memcpy(v_sep, d->v, UMI_SHA256_LEN);
        v_sep[UMI_SHA256_LEN] = sep;
        hmac(d->k, v_sep, sizeof v_sep, x, SCALAR_LEN, h1_mod_n, SCALAR_LEN, d->k);
        hmac(d->k, d->v, sizeof d->v, NULL, 0, NULL, 0, d->v);
    }
}

/* Step h.2: next candidate T = V. */
static void drbg_next(drbg_t *d)
{
    hmac(d->k, d->v, sizeof d->v, NULL, 0, NULL, 0, d->v);
}

/* Step h.3: the candidate was unusable. */
static void drbg_reseed(drbg_t *d)
{
    uint8_t v0[UMI_SHA256_LEN + 1];
    memcpy(v0, d->v, UMI_SHA256_LEN);
    v0[UMI_SHA256_LEN] = 0x00;
    hmac(d->k, v0, sizeof v0, NULL, 0, NULL, 0, d->k);
    hmac(d->k, d->v, sizeof d->v, NULL, 0, NULL, 0, d->v);
}

static bool in_range(const uECC_word_t *value, const uECC_word_t *n)
{
    return !uECC_vli_isZero(value, WORDS) && uECC_vli_cmp(n, value, WORDS) == 1;
}

/* value mod n for value < 2^256 < 2n: at most one subtraction. */
static void reduce_once(uECC_word_t *value, const uECC_word_t *n)
{
    if (uECC_vli_cmp(n, value, WORDS) != 1) {
        uECC_vli_sub(value, value, n, WORDS);
    }
}

/* r = x(kG) mod n, s = k^-1 (e + r d) mod n. False when r or s is zero. */
static bool sign_with_k(const uECC_word_t *d, const uECC_word_t *e, const uECC_word_t *k,
                        uint8_t sig[UMI_SIGNING_SIGNATURE_LEN])
{
    uECC_Curve curve = uECC_secp256r1();
    const uECC_word_t *n = uECC_curve_n(curve);
    uECC_word_t point[2 * WORDS], r[WORDS], s[WORDS], k_inv[WORDS];
    uECC_point_mult(point, uECC_curve_G(curve), k, curve);
    uECC_vli_set(r, point, WORDS);
    reduce_once(r, n);
    if (uECC_vli_isZero(r, WORDS)) {
        return false;
    }
    uECC_vli_modMult(s, r, d, n, WORDS);
    uECC_vli_modAdd(s, s, e, n, WORDS);
    uECC_vli_modInv(k_inv, k, n, WORDS);
    uECC_vli_modMult(s, s, k_inv, n, WORDS);
    if (uECC_vli_isZero(s, WORDS)) {
        return false;
    }
    uECC_vli_nativeToBytes(sig, SCALAR_LEN, r);
    uECC_vli_nativeToBytes(sig + SCALAR_LEN, SCALAR_LEN, s);
    return true;
}

bool umi_soft_signer_init(umi_soft_signer_t *s, const uint8_t private_key[UMI_PRIVATE_KEY_LEN])
{
    memcpy(s->private_key, private_key, UMI_PRIVATE_KEY_LEN);
    s->public_key[0] = 0x04;
    return uECC_compute_public_key(s->private_key, s->public_key + 1, uECC_secp256r1()) == 1;
}

static bool sign(void *ctx, const uint8_t *msg, size_t len, uint8_t sig[UMI_SIGNING_SIGNATURE_LEN])
{
    umi_soft_signer_t *signer = ctx;
    const uECC_word_t *n = uECC_curve_n(uECC_secp256r1());

    uint8_t h1[UMI_SHA256_LEN];
    umi_sha256(msg, len, h1);
    uECC_word_t e[WORDS], d[WORDS], k[WORDS];
    uECC_vli_bytesToNative(e, h1, SCALAR_LEN);
    reduce_once(e, n); /* bits2int(h1) mod n = bits2octets(h1) */
    uint8_t h1_mod_n[SCALAR_LEN];
    uECC_vli_nativeToBytes(h1_mod_n, SCALAR_LEN, e);
    uECC_vli_bytesToNative(d, signer->private_key, SCALAR_LEN);

    drbg_t drbg;
    drbg_init(&drbg, signer->private_key, h1_mod_n);
    for (int tries = 0; tries < MAX_NONCE_TRIES; tries++) {
        drbg_next(&drbg);
        uECC_vli_bytesToNative(k, drbg.v, SCALAR_LEN);
        if (in_range(k, n) && sign_with_k(d, e, k, sig)) {
            return true;
        }
        drbg_reseed(&drbg);
    }
    return false;
}

static bool public_key(void *ctx, uint8_t out[UMI_PUBLIC_KEY_LEN])
{
    umi_soft_signer_t *signer = ctx;
    memcpy(out, signer->public_key, UMI_PUBLIC_KEY_LEN);
    return true;
}

umi_hal_signer_t umi_soft_signer_hal(umi_soft_signer_t *s)
{
    return (umi_hal_signer_t){
        .alg = UMI_SIG_ALG_ECDSA_P256,
        .sign = sign,
        .public_key = public_key,
        .ctx = s,
    };
}
