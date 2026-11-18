#include "umi/sim/sha256.h"

#include <string.h>

static const uint32_t K[64] = {
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
};

static uint32_t rotr(uint32_t x, unsigned n)
{
    return (x >> n) | (x << (32 - n));
}

static void compress(uint32_t state[8], const uint8_t block[UMI_SHA256_BLOCK_LEN])
{
    uint32_t w[64];
    for (int i = 0; i < 16; i++) {
        w[i] = (uint32_t)block[4 * i] << 24 | (uint32_t)block[4 * i + 1] << 16 |
               (uint32_t)block[4 * i + 2] << 8 | block[4 * i + 3];
    }
    for (int i = 16; i < 64; i++) {
        uint32_t s0 = rotr(w[i - 15], 7) ^ rotr(w[i - 15], 18) ^ (w[i - 15] >> 3);
        uint32_t s1 = rotr(w[i - 2], 17) ^ rotr(w[i - 2], 19) ^ (w[i - 2] >> 10);
        w[i] = w[i - 16] + s0 + w[i - 7] + s1;
    }
    uint32_t a = state[0], b = state[1], c = state[2], d = state[3];
    uint32_t e = state[4], f = state[5], g = state[6], h = state[7];
    for (int i = 0; i < 64; i++) {
        uint32_t t1 = h + (rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25)) + ((e & f) ^ (~e & g)) + K[i] + w[i];
        uint32_t t2 = (rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22)) + ((a & b) ^ (a & c) ^ (b & c));
        h = g;
        g = f;
        f = e;
        e = d + t1;
        d = c;
        c = b;
        b = a;
        a = t1 + t2;
    }
    state[0] += a;
    state[1] += b;
    state[2] += c;
    state[3] += d;
    state[4] += e;
    state[5] += f;
    state[6] += g;
    state[7] += h;
}

void umi_sha256_init(umi_sha256_t *h)
{
    static const uint32_t iv[8] = {0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
                                   0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19};
    memcpy(h->state, iv, sizeof iv);
    h->total_len = 0;
    h->block_len = 0;
}

void umi_sha256_update(umi_sha256_t *h, const void *data, size_t len)
{
    const uint8_t *p = data;
    h->total_len += len;
    while (len > 0) {
        size_t n = UMI_SHA256_BLOCK_LEN - h->block_len;
        if (n > len) {
            n = len;
        }
        memcpy(h->block + h->block_len, p, n);
        h->block_len += n;
        p += n;
        len -= n;
        if (h->block_len == UMI_SHA256_BLOCK_LEN) {
            compress(h->state, h->block);
            h->block_len = 0;
        }
    }
}

void umi_sha256_final(umi_sha256_t *h, uint8_t out[UMI_SHA256_LEN])
{
    uint64_t bits = h->total_len * 8;
    uint8_t pad = 0x80;
    umi_sha256_update(h, &pad, 1);
    pad = 0;
    while (h->block_len != UMI_SHA256_BLOCK_LEN - 8) {
        umi_sha256_update(h, &pad, 1);
    }
    uint8_t len_be[8];
    for (int i = 0; i < 8; i++) {
        len_be[i] = (uint8_t)(bits >> (56 - 8 * i));
    }
    umi_sha256_update(h, len_be, 8);
    for (int i = 0; i < 8; i++) {
        out[4 * i] = (uint8_t)(h->state[i] >> 24);
        out[4 * i + 1] = (uint8_t)(h->state[i] >> 16);
        out[4 * i + 2] = (uint8_t)(h->state[i] >> 8);
        out[4 * i + 3] = (uint8_t)h->state[i];
    }
}

void umi_sha256(const void *data, size_t len, uint8_t out[UMI_SHA256_LEN])
{
    umi_sha256_t h;
    umi_sha256_init(&h);
    umi_sha256_update(&h, data, len);
    umi_sha256_final(&h, out);
}

void umi_hmac_sha256_init(umi_hmac_sha256_t *h, const uint8_t *key, size_t key_len)
{
    uint8_t inner_key[UMI_SHA256_BLOCK_LEN] = {0};
    memset(h->outer_key, 0, sizeof h->outer_key);
    memcpy(inner_key, key, key_len);
    memcpy(h->outer_key, key, key_len);
    for (size_t i = 0; i < UMI_SHA256_BLOCK_LEN; i++) {
        inner_key[i] ^= 0x36;
        h->outer_key[i] ^= 0x5c;
    }
    umi_sha256_init(&h->inner);
    umi_sha256_update(&h->inner, inner_key, sizeof inner_key);
}

void umi_hmac_sha256_update(umi_hmac_sha256_t *h, const void *data, size_t len)
{
    umi_sha256_update(&h->inner, data, len);
}

void umi_hmac_sha256_final(umi_hmac_sha256_t *h, uint8_t out[UMI_SHA256_LEN])
{
    uint8_t inner[UMI_SHA256_LEN];
    umi_sha256_final(&h->inner, inner);
    umi_sha256_t outer;
    umi_sha256_init(&outer);
    umi_sha256_update(&outer, h->outer_key, sizeof h->outer_key);
    umi_sha256_update(&outer, inner, sizeof inner);
    umi_sha256_final(&outer, out);
}
