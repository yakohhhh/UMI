/* Sound level meter: A-weighting IIR on the mic's PCM, then LAeq over 100 ms
 * blocks and over the last second (SAMPLE.noise_cdba). Only levels leave this
 * module; the PCM is discarded as it is processed.
 *
 * The A-weighting filter is the IEC 61672 analog prototype through the bilinear
 * transform, computed at init for the mic's rate. At 16 kHz it is within
 * 0.05 dB of the standard up to 2 kHz and 0.5 dB low at 4 kHz, where little
 * street noise energy lies. */
#ifndef UMI_CORE_SPL_H
#define UMI_CORE_SPL_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

/* ICS-43434-like digital MEMS mic: a 94 dB SPL, 1 kHz tone reads -26 dBFS,
 * where 0 dBFS is a full-scale sine (AES17). To confirm on the actual part. */
#define UMI_SPL_MIC_SENSITIVITY_DBFS (-26.0f)
#define UMI_SPL_MIC_REF_DB_SPL 94.0f

#define UMI_SPL_BLOCK_MS 100u
#define UMI_SPL_BLOCKS_PER_S 10u

typedef struct {
    float b0, b1, b2, a1, a2;
    float z1, z2;
} umi_biquad_t;

typedef struct {
    umi_biquad_t stage[3];
    float gain;     /* makes the response exactly 0 dB at 1 kHz */
    float cal_db;   /* level of a mean square of 1.0 */
    uint32_t block_len;
    uint32_t block_n;
    float block_sum;
    float blocks[UMI_SPL_BLOCKS_PER_S]; /* mean squares of the last complete blocks */
    uint8_t next;
    uint8_t filled;
} umi_spl_t;

/* offset_db: per-unit calibration on top of the datasheet sensitivity. */
void umi_spl_init(umi_spl_t *m, uint32_t sample_rate_hz, float offset_db);

/* Restart the averages, keeping the filter (e.g. after the mic was off). */
void umi_spl_reset(umi_spl_t *m);

/* pcm: Q31 mono samples. */
void umi_spl_process(umi_spl_t *m, const int32_t *pcm, size_t n);

/* LAeq of the last complete 100 ms block, dB(A). */
bool umi_spl_laeq_100ms(const umi_spl_t *m, float *dba);

/* LAeq of the last second (10 complete blocks), dB(A). */
bool umi_spl_laeq_1s(const umi_spl_t *m, float *dba);

/* RMS (full scale = 1) of a 1 kHz tone that reads dba: what a simulated mic
 * must produce. */
float umi_spl_tone_rms(float dba);

#endif /* UMI_CORE_SPL_H */
