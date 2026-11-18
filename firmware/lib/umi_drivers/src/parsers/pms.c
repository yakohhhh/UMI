#include "umi/drivers/pms.h"

#include "umi/bytes.h"

#define START_1 0x42
#define START_2 0x4D
#define BODY_LEN 28

bool umi_pms_parse(const uint8_t frame[UMI_PMS_FRAME_LEN], umi_pms_frame_t *out)
{
    if (frame[0] != START_1 || frame[1] != START_2 || umi_get_u16be(frame + 2) != BODY_LEN) {
        return false;
    }
    uint16_t sum = 0;
    for (int i = 0; i < UMI_PMS_FRAME_LEN - 2; i++) {
        sum = (uint16_t)(sum + frame[i]);
    }
    if (sum != umi_get_u16be(frame + UMI_PMS_FRAME_LEN - 2)) {
        return false;
    }
    *out = (umi_pms_frame_t){
        .pm1_cf1 = umi_get_u16be(frame + 4),
        .pm25_cf1 = umi_get_u16be(frame + 6),
        .pm10_cf1 = umi_get_u16be(frame + 8),
        .pm1_atm = umi_get_u16be(frame + 10),
        .pm25_atm = umi_get_u16be(frame + 12),
        .pm10_atm = umi_get_u16be(frame + 14),
    };
    return true;
}

void umi_pms_init(umi_pms_t *p)
{
    *p = (umi_pms_t){0};
}

bool umi_pms_feed(umi_pms_t *p, uint8_t byte, umi_pms_frame_t *out)
{
    if ((p->len == 0 && byte != START_1) || (p->len == 1 && byte != START_2)) {
        /* Out of sync: a 0x42 may still start the next frame. */
        p->len = byte == START_1 ? 1 : 0;
        return false;
    }
    p->buf[p->len++] = byte;
    if (p->len < UMI_PMS_FRAME_LEN) {
        return false;
    }
    p->len = 0;
    if (umi_pms_parse(p->buf, out)) {
        return true;
    }
    p->rejected++;
    return false;
}
