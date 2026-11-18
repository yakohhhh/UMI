#include "umi/flag_signing.h"

#include <string.h>

#include "umi/bytes.h"

void umi_flag_signing_message(uint64_t device_id, uint32_t session_id, const umi_record_t *flag,
                              uint8_t out[UMI_FLAG_MESSAGE_LEN])
{
    uint8_t *p = out;
    memcpy(p, UMI_SIGNING_FLAG_CONTEXT, UMI_FLAG_CONTEXT_LEN);
    p += UMI_FLAG_CONTEXT_LEN;
    umi_put_u64le(p, device_id);
    p += 8;
    umi_put_u32le(p, session_id);
    p += 4;
    memcpy(p, flag->payload, UMI_FLAG_SIGNED_PREFIX_LEN);
}
