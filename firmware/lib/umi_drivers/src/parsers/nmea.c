#include "umi/drivers/nmea.h"

#include <string.h>

#include "umi/protocol_gen.h"

#define MAX_FIELDS 20
#define CM_PER_S_PER_KNOT_E4 514444 /* 1 kn = 51.4444 cm/s */

typedef struct {
    const char *p;
    size_t len;
} field_t;

static int hex_digit(char c)
{
    if (c >= '0' && c <= '9') {
        return c - '0';
    }
    if (c >= 'A' && c <= 'F') {
        return c - 'A' + 10;
    }
    if (c >= 'a' && c <= 'f') {
        return c - 'a' + 10;
    }
    return -1;
}

static bool is_digit(char c)
{
    return c >= '0' && c <= '9';
}

/* Unsigned decimal "123.45" scaled by 10^decimals, rounding extra digits away.
 * Empty fields fail. */
static bool parse_fixed(field_t f, unsigned decimals, uint64_t *out)
{
    uint64_t value = 0;
    unsigned frac_digits = 0;
    bool seen_dot = false, seen_digit = false, round_up = false;
    for (size_t i = 0; i < f.len; i++) {
        char c = f.p[i];
        if (c == '.' && !seen_dot) {
            seen_dot = true;
        } else if (is_digit(c)) {
            seen_digit = true;
            if (!seen_dot || frac_digits < decimals) {
                if (value > UINT64_MAX / 20) {
                    return false;
                }
                value = value * 10 + (uint64_t)(c - '0');
                frac_digits += seen_dot;
            } else if (frac_digits == decimals) {
                round_up = c >= '5';
                frac_digits++;
            }
        } else {
            return false;
        }
    }
    if (!seen_digit) {
        return false;
    }
    for (unsigned d = frac_digits > decimals ? decimals : frac_digits; d < decimals; d++) {
        value *= 10;
    }
    *out = value + round_up;
    return true;
}

static bool parse_digits(const char *p, size_t n, uint32_t *out)
{
    uint32_t v = 0;
    for (size_t i = 0; i < n; i++) {
        if (!is_digit(p[i])) {
            return false;
        }
        v = v * 10 + (uint32_t)(p[i] - '0');
    }
    *out = v;
    return true;
}

/* hhmmss[.sss] -> ms since midnight. */
static bool parse_time(field_t f, uint32_t *out)
{
    uint32_t hh, mm;
    uint64_t ss_ms;
    if (f.len < 6 || !parse_digits(f.p, 2, &hh) || !parse_digits(f.p + 2, 2, &mm) ||
        !parse_fixed((field_t){f.p + 4, f.len - 4}, 3, &ss_ms) || hh > 23 || mm > 59 ||
        ss_ms >= 61000) {
        return false;
    }
    *out = (hh * 3600u + mm * 60u) * 1000u + (uint32_t)ss_ms;
    return true;
}

/* Days since 1970-01-01 of a proleptic Gregorian date (H. Hinnant). */
static int64_t days_from_civil(int64_t y, uint32_t m, uint32_t d)
{
    y -= m <= 2;
    int64_t era = (y >= 0 ? y : y - 399) / 400;
    uint32_t yoe = (uint32_t)(y - era * 400);
    uint32_t doy = (153 * (m + (m > 2 ? (uint32_t)-3 : 9)) + 2) / 5 + d - 1;
    uint32_t doe = yoe * 365 + yoe / 4 - yoe / 100 + doy;
    return era * 146097 + (int64_t)doe - 719468;
}

/* ddmmyy -> days since epoch; years 00-99 are 2000-2099. */
static bool parse_date(field_t f, int64_t *days)
{
    uint32_t dd, mo, yy;
    if (f.len != 6 || !parse_digits(f.p, 2, &dd) || !parse_digits(f.p + 2, 2, &mo) ||
        !parse_digits(f.p + 4, 2, &yy) || dd < 1 || dd > 31 || mo < 1 || mo > 12) {
        return false;
    }
    *days = days_from_civil(2000 + (int64_t)yy, mo, dd);
    return true;
}

/* (d)ddmm.mmmm + hemisphere -> degrees x 1e7, in integers so no precision is
 * lost on the way to the fixed-point record. */
static bool parse_coord(field_t value, field_t hemi, unsigned deg_digits, char pos, char neg,
                        int32_t *out)
{
    uint32_t deg;
    uint64_t min_e7;
    if (value.len < deg_digits + 2 || hemi.len != 1 || !parse_digits(value.p, deg_digits, &deg) ||
        !parse_fixed((field_t){value.p + deg_digits, value.len - deg_digits}, 7, &min_e7) ||
        min_e7 >= 600000000u) {
        return false;
    }
    int64_t e7 = (int64_t)deg * 10000000 + (int64_t)((min_e7 + 30) / 60);
    int64_t limit_e7 = deg_digits == 2 ? 900000000 : 1800000000;
    if (e7 > limit_e7) {
        return false;
    }
    if (hemi.p[0] == neg) {
        e7 = -e7;
    } else if (hemi.p[0] != pos) {
        return false;
    }
    *out = (int32_t)e7;
    return true;
}

static size_t split(const char *body, size_t len, field_t *fields)
{
    size_t n = 0;
    size_t start = 0;
    for (size_t i = 0; i <= len && n < MAX_FIELDS; i++) {
        if (i == len || body[i] == ',') {
            fields[n++] = (field_t){body + start, i - start};
            start = i + 1;
        }
    }
    return n;
}

static bool parse_rmc(const field_t *f, size_t n, umi_nmea_rmc_t *out)
{
    /* RMC: 1 time, 2 status, 3-4 lat, 5-6 lon, 7 speed kn, 8 course, 9 date */
    if (n < 10 || !parse_time(f[1], &out->tod_ms) || f[2].len != 1) {
        return false;
    }
    *out = (umi_nmea_rmc_t){.tod_ms = out->tod_ms, .valid = f[2].p[0] == 'A'};
    int64_t days;
    if (parse_date(f[9], &days)) {
        out->has_date = true;
        out->unix_ms = days * 86400000 + out->tod_ms;
    }
    if (!out->valid) {
        return true;
    }
    if (!parse_coord(f[3], f[4], 2, 'N', 'S', &out->lat_e7) ||
        !parse_coord(f[5], f[6], 3, 'E', 'W', &out->lon_e7)) {
        return false;
    }
    uint64_t knots_e4, course_e2;
    if (parse_fixed(f[7], 4, &knots_e4)) {
        uint64_t cms = (knots_e4 * CM_PER_S_PER_KNOT_E4 + 50000000) / 100000000;
        out->speed_cms = cms > UINT16_MAX ? UINT16_MAX : (uint16_t)cms;
    }
    if (parse_fixed(f[8], 2, &course_e2)) {
        out->heading_cdeg = (uint16_t)(course_e2 % 36000);
    }
    return true;
}

static bool parse_gga(const field_t *f, size_t n, umi_nmea_gga_t *out)
{
    /* GGA: 1 time, 2-5 position, 6 quality, 7 satellites, 8 HDOP */
    uint32_t quality, sats;
    if (n < 9 || !parse_time(f[1], &out->tod_ms) || f[6].len != 1 ||
        !parse_digits(f[6].p, 1, &quality)) {
        return false;
    }
    out->quality = (uint8_t)quality;
    out->sats = (f[7].len > 0 && f[7].len <= 2 && parse_digits(f[7].p, f[7].len, &sats))
                    ? (uint8_t)sats
                    : 0;
    uint64_t hdop_d;
    if (parse_fixed(f[8], 1, &hdop_d)) {
        out->hdop_d = hdop_d >= UMI_FORMAT_HDOP_UNKNOWN ? UMI_FORMAT_HDOP_UNKNOWN - 1
                                                        : (uint8_t)hdop_d;
    } else {
        out->hdop_d = UMI_FORMAT_HDOP_UNKNOWN;
    }
    return true;
}

umi_nmea_kind_t umi_nmea_parse(const char *s, size_t len, umi_nmea_sentence_t *out)
{
    /* $TTSSS,...*HH: at least the talker, sentence id and checksum. */
    if (len < 10 || s[0] != '$' || s[len - 3] != '*') {
        return UMI_NMEA_INVALID;
    }
    int hi = hex_digit(s[len - 2]), lo = hex_digit(s[len - 1]);
    uint8_t sum = 0;
    for (size_t i = 1; i < len - 3; i++) {
        sum ^= (uint8_t)s[i];
    }
    if (hi < 0 || lo < 0 || sum != (uint8_t)(hi << 4 | lo)) {
        return UMI_NMEA_INVALID;
    }
    field_t fields[MAX_FIELDS];
    size_t n = split(s + 1, len - 4, fields);
    if (fields[0].len != 5) {
        return UMI_NMEA_INVALID;
    }
    const char *type = fields[0].p + 2;
    if (memcmp(type, "RMC", 3) == 0) {
        out->kind = parse_rmc(fields, n, &out->as.rmc) ? UMI_NMEA_RMC : UMI_NMEA_INVALID;
    } else if (memcmp(type, "GGA", 3) == 0) {
        out->kind = parse_gga(fields, n, &out->as.gga) ? UMI_NMEA_GGA : UMI_NMEA_INVALID;
    } else {
        out->kind = UMI_NMEA_IGNORED;
    }
    return out->kind;
}

void umi_nmea_init(umi_nmea_t *p)
{
    *p = (umi_nmea_t){0};
}

static void make_fix(const umi_nmea_rmc_t *rmc, const umi_nmea_gga_t *gga, uint32_t t_ms,
                     umi_gnss_fix_t *out)
{
    bool fixed = rmc->valid && gga->quality > 0;
    *out = (umi_gnss_fix_t){
        .t_ms = t_ms,
        /* Without GSA there is no fix dimension; four satellites are the
         * minimum for a 3D solution. */
        .fix = !fixed ? UMI_FIX_NONE : gga->sats >= 4 ? UMI_FIX_THREE_D : UMI_FIX_TWO_D,
        .hdop_d = gga->hdop_d,
        .sats = gga->sats,
        .has_utc = rmc->has_date,
        .unix_ms = rmc->unix_ms,
    };
    if (fixed) {
        out->lat_e7 = rmc->lat_e7;
        out->lon_e7 = rmc->lon_e7;
        out->speed_cms = rmc->speed_cms;
        out->heading_cdeg = rmc->heading_cdeg;
    }
}

bool umi_nmea_feed_sentence(umi_nmea_t *p, const char *sentence, size_t len, uint32_t t_ms,
                            umi_gnss_fix_t *out)
{
    umi_nmea_sentence_t s;
    switch (umi_nmea_parse(sentence, len, &s)) {
    case UMI_NMEA_RMC:
        p->rmc = s.as.rmc;
        p->has_rmc = true;
        p->has_gga = p->has_gga && p->gga.tod_ms == p->rmc.tod_ms;
        break;
    case UMI_NMEA_GGA:
        p->gga = s.as.gga;
        p->has_gga = true;
        p->has_rmc = p->has_rmc && p->gga.tod_ms == p->rmc.tod_ms;
        break;
    case UMI_NMEA_INVALID:
        p->rejected++;
        return false;
    case UMI_NMEA_IGNORED:
        return false;
    }
    if (!(p->has_rmc && p->has_gga)) {
        return false;
    }
    make_fix(&p->rmc, &p->gga, t_ms, out);
    p->has_rmc = false;
    p->has_gga = false;
    return true;
}

bool umi_nmea_feed_byte(umi_nmea_t *p, char c, uint32_t t_ms, umi_gnss_fix_t *out)
{
    if (c == '$') {
        p->in_sentence = true;
        p->len = 0;
    }
    if (!p->in_sentence) {
        return false;
    }
    if (c == '\r' || c == '\n') {
        p->in_sentence = false;
        return umi_nmea_feed_sentence(p, p->line, p->len, t_ms, out);
    }
    if (p->len == UMI_NMEA_MAX_SENTENCE) {
        p->in_sentence = false;
        p->rejected++;
        return false;
    }
    p->line[p->len++] = c;
    return false;
}
