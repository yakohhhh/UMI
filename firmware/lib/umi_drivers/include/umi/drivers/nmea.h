/* NMEA 0183 parser for the GNSS receiver: $--RMC and $--GGA from any talker
 * (GN combined, GP GPS, GA Galileo, GL GLONASS, GB BeiDou), checksum required.
 * One fix is produced per epoch, when RMC and GGA of the same UTC time have
 * both arrived, in either order. Pure C: fed by the UART driver on the Clip
 * and by the simulated GNSS on the host. */
#ifndef UMI_DRIVERS_NMEA_H
#define UMI_DRIVERS_NMEA_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "umi/hal/gnss.h"

/* NMEA caps sentences at 82 characters; receivers in high-precision modes
 * go a little over. */
#define UMI_NMEA_MAX_SENTENCE 120

typedef struct {
    bool valid;        /* status A */
    uint32_t tod_ms;   /* UTC time of day */
    int64_t unix_ms;   /* with the date, when has_date */
    bool has_date;
    int32_t lat_e7;
    int32_t lon_e7;
    uint16_t speed_cms;
    uint16_t heading_cdeg;
} umi_nmea_rmc_t;

typedef struct {
    uint32_t tod_ms;
    uint8_t quality; /* 0 = no fix */
    uint8_t sats;
    uint8_t hdop_d;
} umi_nmea_gga_t;

typedef enum {
    UMI_NMEA_RMC,
    UMI_NMEA_GGA,
    UMI_NMEA_IGNORED, /* valid, but a sentence we do not use */
    UMI_NMEA_INVALID, /* bad framing, checksum or field */
} umi_nmea_kind_t;

typedef struct {
    umi_nmea_kind_t kind;
    union {
        umi_nmea_rmc_t rmc;
        umi_nmea_gga_t gga;
    } as;
} umi_nmea_sentence_t;

/* Parses one sentence, from '$' to the checksum, without line ending. */
umi_nmea_kind_t umi_nmea_parse(const char *sentence, size_t len, umi_nmea_sentence_t *out);

typedef struct {
    char line[UMI_NMEA_MAX_SENTENCE + 1];
    size_t len;
    bool in_sentence;
    bool has_rmc;
    umi_nmea_rmc_t rmc;
    bool has_gga;
    umi_nmea_gga_t gga;
    uint32_t rejected; /* sentences that failed to parse, for diagnostics */
} umi_nmea_t;

void umi_nmea_init(umi_nmea_t *p);

/* Feeds one complete sentence received at t_ms; true when it completes an
 * epoch, written to *out. */
bool umi_nmea_feed_sentence(umi_nmea_t *p, const char *sentence, size_t len, uint32_t t_ms,
                            umi_gnss_fix_t *out);

/* Feeds raw UART bytes; same result as feed_sentence at each line end. */
bool umi_nmea_feed_byte(umi_nmea_t *p, char c, uint32_t t_ms, umi_gnss_fix_t *out);

#endif /* UMI_DRIVERS_NMEA_H */
