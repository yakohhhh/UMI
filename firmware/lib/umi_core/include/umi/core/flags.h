/* Rider flags: a FLAG record with the sensor snapshot of the press, signed by
 * the Clip (protocol/README.md §1.4), and FLAG_UNDO for a double press. */
#ifndef UMI_CORE_FLAGS_H
#define UMI_CORE_FLAGS_H

#include <stdbool.h>
#include <stdint.h>

#include "umi/hal/keyword.h"
#include "umi/hal/signer.h"
#include "umi/records.h"

/* What the sensors said at the moment of the press. */
typedef struct {
    int32_t lat_e7; /* last fix, 0 without one */
    int32_t lon_e7;
    uint16_t speed_cms;
    uint16_t vib_mms2;
    uint16_t noise_cdba;
} umi_snapshot_t;

typedef enum {
    UMI_FLAG_PRESSED,         /* press: no keyword asked */
    UMI_FLAG_UNDERSTOOD,      /* voice: keyword accepted, kind set */
    UMI_FLAG_NOT_UNDERSTOOD,  /* voice: nothing usable, kind left for after the ride */
} umi_flag_outcome_t;

typedef struct {
    umi_hal_signer_t signer;
    uint64_t device_id;
    uint32_t session_id;
    uint16_t next_seq;
    bool can_undo;
    uint16_t last_seq;
    uint32_t signing_failures;
} umi_flags_t;

void umi_flags_init(umi_flags_t *f, umi_hal_signer_t signer, uint64_t device_id);
void umi_flags_begin_session(umi_flags_t *f, uint32_t session_id);

/* A keyword counts when it names a hazard with at least
 * UMI_BUTTON_KEYWORD_MIN_CONFIDENCE. */
bool umi_keyword_accepted(const umi_keyword_result_t *kw);

/* Builds and signs a flag dated t_ms (session-relative). source is a
 * umi_flag_source_t; for a voice flag, kw is the recogniser's answer or NULL
 * when the window closed without one. A signing failure leaves the flag
 * unsigned rather than losing it: the rider still sees it after the ride. */
umi_flag_outcome_t umi_flags_create(umi_flags_t *f, uint32_t t_ms, uint8_t source,
                                    const umi_keyword_result_t *kw, const umi_snapshot_t *snap,
                                    umi_record_t *out);

/* Cancels the last flag of the session, once. False when there is none. */
bool umi_flags_undo(umi_flags_t *f, uint32_t t_ms, umi_record_t *out);

#endif /* UMI_CORE_FLAGS_H */
