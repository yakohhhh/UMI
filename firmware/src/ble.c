#include "ble.h"

#include <string.h>

#include "esp_log.h"
#include "host/ble_hs.h"
#include "host/util/util.h"
#include "nimble/nimble_port.h"
#include "nimble/nimble_port_freertos.h"
#include "services/gap/ble_svc_gap.h"
#include "services/gatt/ble_svc_gatt.h"

/* NimBLE's NVS bond store; the header is not exported by ESP-IDF. */
void ble_store_config_init(void);

static const char *TAG = "umi-ble";

#define DEVICE_NAME "UMI Clip"
#define DEVICE_INFO_MAX (8 + 1 + 3 + UMI_PUBLIC_KEY_LEN + 32)
#define SESSION_INDEX_MAX 480 /* 40 sessions */
#define PENDING_INDICATIONS 4

static QueueHandle_t inbox;
static umi_ble_index_fn session_index;
static uint8_t device_info[DEVICE_INFO_MAX];
static size_t device_info_len;

/* Written by the core task, read by the host task. */
static portMUX_TYPE lock = portMUX_INITIALIZER_UNLOCKED;
static uint8_t status_bytes[UMI_BLE_LIVE_STATUS_LEN];
static umi_settings_t settings;

static uint16_t conn_handle = BLE_HS_CONN_HANDLE_NONE;
static uint8_t own_addr_type;
static uint16_t status_handle;
static uint16_t control_handle;

typedef struct {
    uint8_t opcode;
    uint8_t status;
} indication_t;

static QueueHandle_t indications;
static struct ble_npl_event status_event;
static struct ble_npl_event indicate_event;

static ble_uuid128_t uuids[8];

static void start_advertising(void);

/* ---------------------------------------------------------------- GATT */

static int append(struct ble_gatt_access_ctxt *ctxt, const void *data, size_t len)
{
    return os_mbuf_append(ctxt->om, data, (uint16_t)len) == 0 ? 0 : BLE_ATT_ERR_INSUFFICIENT_RES;
}

static int post_write(struct ble_gatt_access_ctxt *ctxt, umi_ble_msg_kind_t kind)
{
    umi_ble_msg_t msg = {.kind = kind};
    uint16_t len = 0;
    if (ble_hs_mbuf_to_flat(ctxt->om, msg.data, sizeof msg.data, &len) != 0) {
        return BLE_ATT_ERR_INVALID_ATTR_VALUE_LEN;
    }
    msg.len = len;
    return xQueueSend(inbox, &msg, 0) == pdTRUE ? 0 : BLE_ATT_ERR_PREPARE_QUEUE_FULL;
}

static int access(uint16_t conn, uint16_t attr, struct ble_gatt_access_ctxt *ctxt, void *arg)
{
    (void)conn;
    (void)attr;
    uint16_t id = (uint16_t)(uintptr_t)arg;
    uint8_t buf[SESSION_INDEX_MAX];
    switch (id) {
    case UMI_BLE_DEVICE_INFO:
        return append(ctxt, device_info, device_info_len);
    case UMI_BLE_LIVE_STATUS: {
        uint8_t copy[UMI_BLE_LIVE_STATUS_LEN];
        taskENTER_CRITICAL(&lock);
        memcpy(copy, status_bytes, sizeof copy);
        taskEXIT_CRITICAL(&lock);
        return append(ctxt, copy, sizeof copy);
    }
    case UMI_BLE_SESSION_INDEX:
        return append(ctxt, buf, session_index(buf, sizeof buf));
    case UMI_BLE_SETTINGS:
        if (ctxt->op == BLE_GATT_ACCESS_OP_WRITE_CHR) {
            return post_write(ctxt, UMI_BLE_MSG_SETTINGS);
        } else {
            umi_settings_t copy;
            taskENTER_CRITICAL(&lock);
            copy = settings;
            taskEXIT_CRITICAL(&lock);
            return append(ctxt, buf, umi_settings_encode(&copy, buf, sizeof buf));
        }
    case UMI_BLE_CONTROL_POINT: {
        uint16_t len = 0;
        umi_ble_command_t cmd;
        if (ble_hs_mbuf_to_flat(ctxt->om, buf, sizeof buf, &len) != 0 ||
            !umi_ble_command_parse(buf, len, &cmd)) {
            umi_ble_indicate(len > 0 ? buf[0] : 0, UMI_BLE_STATUS_INVALID);
            return 0;
        }
        return post_write(ctxt, UMI_BLE_MSG_COMMAND);
    }
    case UMI_BLE_HAZARDS:
        return post_write(ctxt, UMI_BLE_MSG_HAZARDS);
    default:
        return BLE_ATT_ERR_UNLIKELY;
    }
}

#define ARG(id) ((void *)(uintptr_t)(id))
/* Everything but Device Info needs an encrypted (bonded) link. */
#define ENC_READ (BLE_GATT_CHR_F_READ | BLE_GATT_CHR_F_READ_ENC)
#define ENC_WRITE (BLE_GATT_CHR_F_WRITE | BLE_GATT_CHR_F_WRITE_ENC)

static const struct ble_gatt_svc_def services[] = {
    {
        .type = BLE_GATT_SVC_TYPE_PRIMARY,
        .uuid = &uuids[UMI_BLE_SERVICE].u,
        .characteristics = (struct ble_gatt_chr_def[]){
            {.uuid = &uuids[UMI_BLE_DEVICE_INFO].u, .access_cb = access,
             .arg = ARG(UMI_BLE_DEVICE_INFO), .flags = BLE_GATT_CHR_F_READ},
            {.uuid = &uuids[UMI_BLE_LIVE_STATUS].u, .access_cb = access,
             .arg = ARG(UMI_BLE_LIVE_STATUS), .flags = ENC_READ | BLE_GATT_CHR_F_NOTIFY,
             .val_handle = &status_handle},
            {.uuid = &uuids[UMI_BLE_SESSION_INDEX].u, .access_cb = access,
             .arg = ARG(UMI_BLE_SESSION_INDEX), .flags = ENC_READ},
            {.uuid = &uuids[UMI_BLE_CONTROL_POINT].u, .access_cb = access,
             .arg = ARG(UMI_BLE_CONTROL_POINT), .flags = ENC_WRITE | BLE_GATT_CHR_F_INDICATE,
             .val_handle = &control_handle},
            {.uuid = &uuids[UMI_BLE_TRANSFER_DATA].u, .access_cb = access,
             .arg = ARG(UMI_BLE_TRANSFER_DATA), .flags = BLE_GATT_CHR_F_NOTIFY},
            {.uuid = &uuids[UMI_BLE_SETTINGS].u, .access_cb = access,
             .arg = ARG(UMI_BLE_SETTINGS), .flags = ENC_READ | ENC_WRITE},
            {.uuid = &uuids[UMI_BLE_HAZARDS].u, .access_cb = access,
             .arg = ARG(UMI_BLE_HAZARDS), .flags = ENC_WRITE},
            {0},
        },
    },
    {0},
};

/* ---------------------------------------------------------------- host-task events */

static void on_status_event(struct ble_npl_event *ev)
{
    (void)ev;
    ble_gatts_chr_updated(status_handle);
}

static void on_indicate_event(struct ble_npl_event *ev)
{
    (void)ev;
    indication_t ind;
    while (xQueueReceive(indications, &ind, 0) == pdTRUE) {
        if (conn_handle == BLE_HS_CONN_HANDLE_NONE) {
            continue;
        }
        const uint8_t payload[2] = {ind.opcode, ind.status};
        struct os_mbuf *om = ble_hs_mbuf_from_flat(payload, sizeof payload);
        if (om != NULL) {
            ble_gatts_indicate_custom(conn_handle, control_handle, om);
        }
    }
}

void umi_ble_publish_status(const umi_live_status_t *status)
{
    uint8_t bytes[UMI_BLE_LIVE_STATUS_LEN];
    umi_live_status_encode(status, bytes);
    taskENTER_CRITICAL(&lock);
    bool changed = memcmp(bytes, status_bytes, sizeof bytes) != 0;
    memcpy(status_bytes, bytes, sizeof bytes);
    taskEXIT_CRITICAL(&lock);
    if (changed) {
        ble_npl_eventq_put(nimble_port_get_dflt_eventq(), &status_event);
    }
}

void umi_ble_publish_settings(const umi_settings_t *s)
{
    taskENTER_CRITICAL(&lock);
    settings = *s;
    taskEXIT_CRITICAL(&lock);
}

void umi_ble_indicate(uint8_t opcode, uint8_t status)
{
    indication_t ind = {opcode, status};
    if (xQueueSend(indications, &ind, 0) == pdTRUE) {
        ble_npl_eventq_put(nimble_port_get_dflt_eventq(), &indicate_event);
    }
}

/* ---------------------------------------------------------------- GAP */

static int on_gap_event(struct ble_gap_event *event, void *arg)
{
    (void)arg;
    switch (event->type) {
    case BLE_GAP_EVENT_CONNECT:
        if (event->connect.status == 0) {
            conn_handle = event->connect.conn_handle;
        } else {
            start_advertising();
        }
        return 0;
    case BLE_GAP_EVENT_DISCONNECT:
        conn_handle = BLE_HS_CONN_HANDLE_NONE;
        start_advertising();
        return 0;
    case BLE_GAP_EVENT_ADV_COMPLETE:
        start_advertising();
        return 0;
    case BLE_GAP_EVENT_REPEAT_PAIRING: {
        /* The phone lost its bond: forget ours and pair again. */
        struct ble_gap_conn_desc desc;
        if (ble_gap_conn_find(event->repeat_pairing.conn_handle, &desc) == 0) {
            ble_store_util_delete_peer(&desc.peer_id_addr);
        }
        return BLE_GAP_REPEAT_PAIRING_RETRY;
    }
    default:
        return 0;
    }
}

static void start_advertising(void)
{
    struct ble_hs_adv_fields fields = {
        .flags = BLE_HS_ADV_F_DISC_GEN | BLE_HS_ADV_F_BREDR_UNSUP,
        .uuids128 = &uuids[UMI_BLE_SERVICE],
        .num_uuids128 = 1,
        .uuids128_is_complete = 1,
    };
    struct ble_hs_adv_fields response = {
        .name = (const uint8_t *)DEVICE_NAME,
        .name_len = sizeof DEVICE_NAME - 1,
        .name_is_complete = 1,
    };
    struct ble_gap_adv_params params = {
        .conn_mode = BLE_GAP_CONN_MODE_UND,
        .disc_mode = BLE_GAP_DISC_MODE_GEN,
    };
    if (ble_gap_adv_set_fields(&fields) != 0 || ble_gap_adv_rsp_set_fields(&response) != 0 ||
        ble_gap_adv_start(own_addr_type, NULL, BLE_HS_FOREVER, &params, on_gap_event, NULL) != 0) {
        ESP_LOGE(TAG, "advertising failed");
    }
}

static void on_sync(void)
{
    if (ble_hs_util_ensure_addr(0) == 0 && ble_hs_id_infer_auto(0, &own_addr_type) == 0) {
        start_advertising();
    }
}

static void on_reset(int reason)
{
    ESP_LOGW(TAG, "host reset, reason %d", reason);
}

static void host_task(void *param)
{
    (void)param;
    nimble_port_run();
    nimble_port_freertos_deinit();
}

esp_err_t umi_ble_start(const umi_device_info_t *info, QueueHandle_t inbox_queue,
                        umi_ble_index_fn index_fn)
{
    inbox = inbox_queue;
    session_index = index_fn;
    device_info_len = umi_device_info_encode(info, device_info, sizeof device_info);
    indications = xQueueCreate(PENDING_INDICATIONS, sizeof(indication_t));
    if (device_info_len == 0 || indications == NULL) {
        return ESP_ERR_INVALID_SIZE;
    }
    for (uint16_t id = 0; id < sizeof uuids / sizeof uuids[0]; id++) {
        uuids[id].u.type = BLE_UUID_TYPE_128;
        umi_ble_uuid128(id, uuids[id].value);
    }

    esp_err_t err = nimble_port_init();
    if (err != ESP_OK) {
        return err;
    }
    ble_npl_event_init(&status_event, on_status_event, NULL);
    ble_npl_event_init(&indicate_event, on_indicate_event, NULL);

    /* LE Secure Connections with bonding. The Clip has no display or keys, so
     * pairing is Just Works; see the BLE follow-up for MITM protection. */
    ble_hs_cfg.sync_cb = on_sync;
    ble_hs_cfg.reset_cb = on_reset;
    ble_hs_cfg.store_status_cb = ble_store_util_status_rr;
    ble_hs_cfg.sm_io_cap = BLE_HS_IO_NO_INPUT_OUTPUT;
    ble_hs_cfg.sm_bonding = 1;
    ble_hs_cfg.sm_sc = 1;
    ble_hs_cfg.sm_mitm = 0;
    ble_hs_cfg.sm_our_key_dist = BLE_SM_PAIR_KEY_DIST_ENC | BLE_SM_PAIR_KEY_DIST_ID;
    ble_hs_cfg.sm_their_key_dist = BLE_SM_PAIR_KEY_DIST_ENC | BLE_SM_PAIR_KEY_DIST_ID;

    ble_svc_gap_init();
    ble_svc_gatt_init();
    if (ble_gatts_count_cfg(services) != 0 || ble_gatts_add_svcs(services) != 0 ||
        ble_svc_gap_device_name_set(DEVICE_NAME) != 0) {
        return ESP_FAIL;
    }
    ble_store_config_init();
    nimble_port_freertos_init(host_task);
    return ESP_OK;
}
