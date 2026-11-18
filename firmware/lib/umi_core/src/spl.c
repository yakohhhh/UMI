#include "umi/core/spl.h"

#include <math.h>

#define PI 3.14159265358979323846

/* IEC 61672-1 A-weighting pole frequencies, Hz. */
#define F1 20.598997
#define F2 107.65265
#define F3 737.86223
#define F4 12194.217

/* 0 dBFS is a full-scale sine, whose mean square is 1/2. */
#define SINE_MS_DB 3.0103f

static double bilinear_pole(double f_hz, double fs)
{
    double s = -2.0 * PI * f_hz;
    return (1.0 + s / (2.0 * fs)) / (1.0 - s / (2.0 * fs));
}

/* Biquad with a double zero at zero_z (+1 or -1) and poles p, q. */
static umi_biquad_t make_stage(double zero_z, double p, double q)
{
    return (umi_biquad_t){
        .b0 = 1.0f,
        .b1 = (float)(-2.0 * zero_z),
        .b2 = 1.0f,
        .a1 = (float)(-(p + q)),
        .a2 = (float)(p * q),
    };
}

static double stage_gain(const umi_biquad_t *s, double w)
{
    /* |B(e^jw)| / |A(e^jw)| for B = b0 + b1 z^-1 + b2 z^-2, A = 1 + a1 z^-1 + a2 z^-2. */
    double c1 = cos(w), s1 = sin(w), c2 = cos(2.0 * w), s2 = sin(2.0 * w);
    double br = s->b0 + s->b1 * c1 + s->b2 * c2, bi = -(s->b1 * s1 + s->b2 * s2);
    double ar = 1.0 + s->a1 * c1 + s->a2 * c2, ai = -(s->a1 * s1 + s->a2 * s2);
    return sqrt((br * br + bi * bi) / (ar * ar + ai * ai));
}

void umi_spl_init(umi_spl_t *m, uint32_t sample_rate_hz, float offset_db)
{
    double fs = (double)sample_rate_hz;
    double p1 = bilinear_pole(F1, fs), p2 = bilinear_pole(F2, fs);
    double p3 = bilinear_pole(F3, fs), p4 = bilinear_pole(F4, fs);
    *m = (umi_spl_t){
        .stage = {make_stage(1.0, p1, p1), make_stage(1.0, p2, p3), make_stage(-1.0, p4, p4)},
        .cal_db = UMI_SPL_MIC_REF_DB_SPL - UMI_SPL_MIC_SENSITIVITY_DBFS + SINE_MS_DB + offset_db,
        .block_len = sample_rate_hz * UMI_SPL_BLOCK_MS / 1000u,
    };
    double w = 2.0 * PI * 1000.0 / fs;
    double g = 1.0;
    for (int i = 0; i < 3; i++) {
        g *= stage_gain(&m->stage[i], w);
    }
    m->gain = (float)(1.0 / g);
}

void umi_spl_reset(umi_spl_t *m)
{
    m->block_n = 0;
    m->block_sum = 0.0f;
    m->next = 0;
    m->filled = 0;
}

static float run_stage(umi_biquad_t *s, float x)
{
    /* Direct form II transposed: the best behaved form in float. */
    float y = s->b0 * x + s->z1;
    s->z1 = s->b1 * x - s->a1 * y + s->z2;
    s->z2 = s->b2 * x - s->a2 * y;
    return y;
}

void umi_spl_process(umi_spl_t *m, const int32_t *pcm, size_t n)
{
    const float q31 = 1.0f / 2147483648.0f;
    for (size_t i = 0; i < n; i++) {
        float y = (float)pcm[i] * q31 * m->gain;
        for (int k = 0; k < 3; k++) {
            y = run_stage(&m->stage[k], y);
        }
        m->block_sum += y * y;
        if (++m->block_n == m->block_len) {
            m->blocks[m->next] = m->block_sum / (float)m->block_len;
            m->next = (uint8_t)((m->next + 1) % UMI_SPL_BLOCKS_PER_S);
            if (m->filled < UMI_SPL_BLOCKS_PER_S) {
                m->filled++;
            }
            m->block_n = 0;
            m->block_sum = 0.0f;
        }
    }
}

static float level_db(const umi_spl_t *m, double mean_square)
{
    /* Below the mic's noise floor anyway; avoids log10(0). */
    const double floor_ms = 1e-14;
    return m->cal_db + (float)(10.0 * log10(mean_square > floor_ms ? mean_square : floor_ms));
}

bool umi_spl_laeq_100ms(const umi_spl_t *m, float *dba)
{
    if (m->filled == 0) {
        return false;
    }
    uint8_t last = (uint8_t)((m->next + UMI_SPL_BLOCKS_PER_S - 1) % UMI_SPL_BLOCKS_PER_S);
    *dba = level_db(m, m->blocks[last]);
    return true;
}

bool umi_spl_laeq_1s(const umi_spl_t *m, float *dba)
{
    if (m->filled < UMI_SPL_BLOCKS_PER_S) {
        return false;
    }
    double sum = 0.0;
    for (unsigned i = 0; i < UMI_SPL_BLOCKS_PER_S; i++) {
        sum += m->blocks[i];
    }
    *dba = level_db(m, sum / UMI_SPL_BLOCKS_PER_S);
    return true;
}

float umi_spl_tone_rms(float dba)
{
    float cal_db = UMI_SPL_MIC_REF_DB_SPL - UMI_SPL_MIC_SENSITIVITY_DBFS + SINE_MS_DB;
    return powf(10.0f, (dba - cal_db) / 20.0f);
}
