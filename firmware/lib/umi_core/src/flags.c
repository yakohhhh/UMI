#include "umi/core/flags.h"

#include <string.h>

#include "umi/flag_signing.h"
#include "umi/protocol_gen.h"

void umi_flags_init(umi_flags_t *f, umi_hal_signer_t signer, uint64_t device_id)
{
    *f = (umi_flags_t){.signer = signer, .device_id = device_id};
}

void umi_flags_begin_session(umi_flags_t *f, uint32_t session_id)
{
    f->session_id = session_id;
    f->next_seq = 0;
    f->can_undo = false;
}

bool umi_keyword_accepted(const umi_keyword_result_t *kw)
{
    return kw != NULL && kw->kind > UMI_HAZARD_KIND_NONE && kw->kind <= UMI_HAZARD_KIND_DANGER &&
           kw->confidence >= UMI_BUTTON_KEYWORD_MIN_CONFIDENCE && kw->confidence <= 100;
}

static void sign(umi_flags_t *f, umi_flag_t *flag, umi_record_t *rec)
{
    if (f->signer.alg == UMI_SIG_ALG_NONE || f->signer.sign == NULL) {
        return;
    }
    uint8_t message[UMI_FLAG_MESSAGE_LEN];
    umi_flag_signing_message(f->device_id, f->session_id, rec, message);
    if (!f->signer.sign(f->signer.ctx, message, sizeof message, flag->signature)) {
        memset(flag->signature, 0, sizeof flag->signature);
        f->signing_failures++;
        return;
    }
    flag->sig_alg = f->signer.alg;
    flag->sig_len = UMI_SIGNING_SIGNATURE_LEN;
    umi_flag_encode(flag, rec);
}

umi_flag_outcome_t umi_flags_create(umi_flags_t *f, uint32_t t_ms, uint8_t source,
                                    const umi_keyword_result_t *kw, const umi_snapshot_t *snap,
                                    umi_record_t *out)
{
    umi_flag_t flag = {
        .t_ms = t_ms,
        .seq = f->next_seq++,
        .source = source,
        .kind = UMI_HAZARD_KIND_NONE,
        .lang = UMI_LANG_NONE,
        .lat_e7 = snap->lat_e7,
        .lon_e7 = snap->lon_e7,
        .speed_cms = snap->speed_cms,
        .vib_mms2 = snap->vib_mms2,
        .noise_cdba = snap->noise_cdba,
        .sig_alg = UMI_SIG_ALG_NONE,
    };
    umi_flag_outcome_t outcome = UMI_FLAG_PRESSED;
    if (source == UMI_FLAG_SOURCE_VOICE) {
        outcome = UMI_FLAG_NOT_UNDERSTOOD;
        if (kw != NULL) {
            /* Kept even below the threshold: it tells how the recogniser does
             * in the field, while kind = 0 leaves the answer to the rider. */
            flag.confidence = kw->confidence > 100 ? 100 : kw->confidence;
            flag.lang = kw->lang;
        }
        if (umi_keyword_accepted(kw)) {
            flag.kind = kw->kind;
            outcome = UMI_FLAG_UNDERSTOOD;
        }
    }
    umi_flag_encode(&flag, out);
    sign(f, &flag, out);
    f->can_undo = true;
    f->last_seq = flag.seq;
    return outcome;
}

bool umi_flags_undo(umi_flags_t *f, uint32_t t_ms, umi_record_t *out)
{
    if (!f->can_undo) {
        return false;
    }
    f->can_undo = false;
    umi_flag_undo_encode(&(umi_flag_undo_t){.t_ms = t_ms, .seq = f->last_seq}, out);
    return true;
}
