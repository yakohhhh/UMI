/* The message a Clip signs for each flag (protocol/README.md §1.4):
 * "UMI-FLAG-v1" || device_id (u64 LE) || session_id (u32 LE) || FLAG payload bytes 0-27. */
#ifndef UMI_FLAG_SIGNING_H
#define UMI_FLAG_SIGNING_H

#include <stdint.h>

#include "umi/records.h"

#define UMI_FLAG_CONTEXT_LEN (sizeof UMI_SIGNING_FLAG_CONTEXT - 1)
#define UMI_FLAG_MESSAGE_LEN (UMI_FLAG_CONTEXT_LEN + 8 + 4 + UMI_FLAG_SIGNED_PREFIX_LEN)

/* flag must be an encoded FLAG record; its signature fields are not read. */
void umi_flag_signing_message(uint64_t device_id, uint32_t session_id, const umi_record_t *flag,
                              uint8_t out[UMI_FLAG_MESSAGE_LEN]);

#endif /* UMI_FLAG_SIGNING_H */
