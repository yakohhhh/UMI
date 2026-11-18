/* UMI Clip firmware entry point: brings the parts up and runs the application
 * (umi_core's umi_clip) in one task. With UMI_HW_SIM the sensors are simulated
 * from a scenario embedded in flash; the button, buzzer, LED, flash storage,
 * signer and BLE are real either way. */
#include <inttypes.h>
#include <string.h>

#include "ble.h"
#include "board.h"
#include "esp_log.h"
#include "esp_mac.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "nvs.h"
#include "nvs_flash.h"
#include "umi/bytes.h"
#include "umi/core/clip.h"
#include "umi/core/version.h"
#include "umi/drivers/esp32/board.h"
#include "umi/drivers/esp32/button.h"
#include "umi/drivers/esp32/clock.h"
#include "umi/drivers/esp32/indicators.h"
#include "umi/drivers/esp32/signer.h"
#include "umi/drivers/esp32/storage.h"
#if UMI_HW_SIM
#include "umi/sim/world.h"
#else
#include "umi/drivers/esp32/sensors.h"
#endif

static const char *TAG = "umi";

#define STEP_MS (1000u / UMI_RATES_IMU_HZ)
#define STATUS_PERIOD_MS 1000u
#define CORE_STACK 12288
#define CORE_PRIORITY 5
#define INBOX_LEN 8
#define NVS_NAMESPACE "umi"
#define HW_REV_CLIP 1 /* first Clip board revision */
#define SESSION_INDEX_ENTRIES 40 /* 480 bytes: one long BLE read */

#if UMI_HW_SIM
/* test/scenarios/devkit-demo.scn, NUL-terminated by EMBED_TXTFILES. */
extern const char scenario_text[] asm("_binary_devkit_demo_scn_start");
#endif

typedef struct {
    nvs_handle_t nvs;
    umi_esp32_storage_t storage;
    umi_esp32_signer_t signer;
    umi_esp32_button_t button;
    umi_esp32_buzzer_t buzzer;
    umi_esp32_led_t led;
    umi_esp32_board_t board;
#if UMI_HW_SIM
    umi_sim_world_t world;
    bool scenario_done;
#else
    i2c_master_bus_handle_t i2c;
    umi_esp32_imu_t imu;
    umi_esp32_gnss_t gnss;
    umi_esp32_pm_t pm;
    umi_esp32_mic_t mic;
    umi_esp32_env_t env;
    umi_esp32_fuel_t fuel;
#endif
    umi_clip_t clip;
    QueueHandle_t inbox;
} app_t;

static app_t app;

/* Provisioning burns a device_id into NVS; until then the factory MAC stands
 * in, which is unique per chip. */
static uint64_t device_id(void)
{
    uint64_t id;
    if (nvs_get_u64(app.nvs, "device_id", &id) == ESP_OK) {
        return id;
    }
    uint8_t mac[6];
    ESP_ERROR_CHECK(esp_read_mac(mac, ESP_MAC_BASE));
    id = 0;
    for (int i = 0; i < 6; i++) {
        id = id << 8 | mac[i];
    }
    return id;
}

static umi_settings_t load_settings(void)
{
    umi_settings_t settings = umi_settings_default();
    uint8_t tlv[32];
    size_t len = sizeof tlv;
    if (nvs_get_blob(app.nvs, "settings", tlv, &len) == ESP_OK) {
        umi_settings_apply(&settings, tlv, len);
    }
    return settings;
}

static void save_settings(const umi_settings_t *settings)
{
    uint8_t tlv[32];
    size_t len = umi_settings_encode(settings, tlv, sizeof tlv);
    if (nvs_set_blob(app.nvs, "settings", tlv, len) != ESP_OK || nvs_commit(app.nvs) != ESP_OK) {
        ESP_LOGW(TAG, "settings not saved");
    }
}

static void bind_sensors(umi_hal_t *hal)
{
#if UMI_HW_SIM
    if (!umi_sim_world_init(&app.world, scenario_text, NULL, NULL)) {
        ESP_LOGE(TAG, "embedded scenario is not a v1 SIL scenario");
        abort();
    }
    umi_sim_world_bind(&app.world, hal);
#else
    i2c_master_bus_config_t bus = {
        .i2c_port = -1,
        .sda_io_num = UMI_PIN_I2C_SDA,
        .scl_io_num = UMI_PIN_I2C_SCL,
        .clk_source = I2C_CLK_SRC_DEFAULT,
        .glitch_ignore_cnt = 7,
        .flags.enable_internal_pullup = true,
    };
    ESP_ERROR_CHECK(i2c_new_master_bus(&bus, &app.i2c));
    /* A part that does not answer is logged and left silent: the Clip still
     * records what the others measure. */
    if (umi_esp32_imu_init(&app.imu, app.i2c) != ESP_OK) {
        ESP_LOGE(TAG, "IMU not found");
    }
    if (umi_esp32_env_init(&app.env, app.i2c) != ESP_OK ||
        umi_esp32_fuel_init(&app.fuel, app.i2c) != ESP_OK) {
        ESP_LOGE(TAG, "I2C devices not added");
    }
    ESP_ERROR_CHECK(umi_esp32_gnss_init(&app.gnss, UMI_GNSS_UART, UMI_PIN_GNSS_TX, UMI_PIN_GNSS_RX,
                                        UMI_GNSS_BAUD));
    ESP_ERROR_CHECK(umi_esp32_pm_init(&app.pm, UMI_PM_UART, UMI_PIN_PM_TX, UMI_PIN_PM_RX));
    ESP_ERROR_CHECK(umi_esp32_mic_init(&app.mic, UMI_PIN_MIC_BCLK, UMI_PIN_MIC_WS, UMI_PIN_MIC_SD,
                                       UMI_MIC_RATE_HZ));
    hal->imu = umi_esp32_imu_hal(&app.imu);
    hal->gnss = umi_esp32_gnss_hal(&app.gnss);
    hal->pm = umi_esp32_pm_hal(&app.pm);
    hal->env = umi_esp32_env_hal(&app.env);
    hal->mic = umi_esp32_mic_hal(&app.mic, UMI_MIC_RATE_HZ);
    hal->keyword = umi_esp32_keyword_hal();
    hal->battery = umi_esp32_fuel_hal(&app.fuel);
#endif
}

static size_t session_index(uint8_t *out, size_t cap)
{
    umi_esp32_session_info_t list[SESSION_INDEX_ENTRIES];
    size_t n = umi_esp32_storage_list(&app.storage, list, SESSION_INDEX_ENTRIES);
    size_t len = 0;
    for (size_t i = 0; i < n && len + 12 <= cap; i++, len += 12) {
        umi_put_u32le(out + len, list[i].session_id);
        umi_put_u32le(out + len + 4, list[i].size);
        umi_put_u32le(out + len + 8, list[i].first_unix_s);
    }
    return len;
}

static uint8_t run_command(const umi_ble_command_t *cmd, uint32_t now_ms)
{
    switch (cmd->opcode) {
    case UMI_BLE_OP_SET_TIME:
        umi_clip_set_time(&app.clip, now_ms, cmd->arg.set_time_unix_ms);
        return UMI_BLE_STATUS_OK;
    case UMI_BLE_OP_HAZARDS_BEGIN:
        return umi_warn_ahead_begin(umi_clip_hazards(&app.clip), cmd->arg.hazards_count)
                   ? UMI_BLE_STATUS_OK
                   : UMI_BLE_STATUS_INVALID;
    case UMI_BLE_OP_HAZARDS_END:
        return umi_warn_ahead_commit(umi_clip_hazards(&app.clip)) ? UMI_BLE_STATUS_OK
                                                                  : UMI_BLE_STATUS_INVALID;
    case UMI_BLE_OP_DELETE: {
        esp_err_t err = umi_esp32_storage_delete(&app.storage, cmd->arg.delete_session_id);
        return err == ESP_OK ? UMI_BLE_STATUS_OK
               : err == ESP_ERR_NOT_FOUND ? UMI_BLE_STATUS_NOT_FOUND
                                          : UMI_BLE_STATUS_FAILED;
    }
    default:
        /* START_TRANSFER and ACK: the chunked transfer is a follow-up. */
        return UMI_BLE_STATUS_UNSUPPORTED;
    }
}

static void handle_ble(const umi_ble_msg_t *msg, uint32_t now_ms)
{
    switch (msg->kind) {
    case UMI_BLE_MSG_COMMAND: {
        umi_ble_command_t cmd;
        if (umi_ble_command_parse(msg->data, msg->len, &cmd)) {
            umi_ble_indicate(cmd.opcode, run_command(&cmd, now_ms));
        }
        break;
    }
    case UMI_BLE_MSG_SETTINGS: {
        umi_settings_t settings = app.clip.settings;
        if (umi_settings_apply(&settings, msg->data, msg->len)) {
            umi_clip_set_settings(&app.clip, &settings);
            umi_ble_publish_settings(&settings);
            save_settings(&settings);
        }
        break;
    }
    case UMI_BLE_MSG_HAZARDS: {
        umi_hazard_t hazards[UMI_BLE_MAX_WRITE / UMI_BLE_HAZARD_LEN];
        int n = umi_ble_hazards_parse(msg->data, msg->len, hazards,
                                      sizeof hazards / sizeof hazards[0]);
        if (n < 0 || !umi_warn_ahead_add(umi_clip_hazards(&app.clip), hazards, (size_t)n)) {
            ESP_LOGW(TAG, "hazards write refused");
        }
        break;
    }
    }
}

static void publish_status(void)
{
    umi_live_status_t status;
    umi_clip_live_status(&app.clip, &status);
    size_t pending = umi_esp32_storage_pending(&app.storage);
    status.sessions_pending = pending > UINT16_MAX ? UINT16_MAX : (uint16_t)pending;
    umi_ble_publish_status(&status);
}

static void log_changes(umi_clip_stats_t *seen)
{
    const umi_clip_stats_t *now = &app.clip.stats;
    if (memcmp(seen, now, sizeof *now) != 0) {
        ESP_LOGI(TAG, "sessions %" PRIu32 " flags %" PRIu32 " undos %" PRIu32 " events %" PRIu32
                      " warnings %" PRIu32,
                 now->sessions, now->flags, now->undos, now->events, now->warnings);
        *seen = *now;
    }
}

static void core_task(void *param)
{
    (void)param;
    TickType_t wake = xTaskGetTickCount();
    uint32_t last_status_ms = 0;
    umi_clip_stats_t seen = {0};
    for (;;) {
        uint32_t now = umi_esp32_now_ms();
        umi_ble_msg_t msg;
        while (xQueueReceive(app.inbox, &msg, 0) == pdTRUE) {
            handle_ble(&msg, now);
        }
#if UMI_HW_SIM
        umi_sim_world_advance(&app.world, now);
        if (!app.scenario_done && umi_sim_world_finished(&app.world)) {
            /* The ride is over: close it like an auto-stop would, minus the
             * five still minutes the scenario does not script. */
            app.scenario_done = true;
            umi_clip_shutdown(&app.clip, now);
            ESP_LOGI(TAG, "scenario finished, session closed");
        }
#endif
        umi_clip_step(&app.clip, now);
        if (now - last_status_ms >= STATUS_PERIOD_MS) {
            last_status_ms = now;
            publish_status();
            log_changes(&seen);
        }
        xTaskDelayUntil(&wake, pdMS_TO_TICKS(STEP_MS));
    }
}

void app_main(void)
{
    esp_err_t err = nvs_flash_init();
    if (err == ESP_ERR_NVS_NO_FREE_PAGES || err == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        err = nvs_flash_init();
    }
    ESP_ERROR_CHECK(err);
    ESP_ERROR_CHECK(nvs_open(NVS_NAMESPACE, NVS_READWRITE, &app.nvs));
    ESP_ERROR_CHECK(umi_esp32_storage_init(&app.storage, app.nvs));
    ESP_ERROR_CHECK(umi_esp32_signer_init(&app.signer, app.nvs));
    ESP_ERROR_CHECK(umi_esp32_button_init(&app.button, UMI_PIN_BUTTON, true));
    ESP_ERROR_CHECK(umi_esp32_buzzer_init(&app.buzzer, UMI_PIN_BUZZER));
    ESP_ERROR_CHECK(umi_esp32_led_init(&app.led, UMI_PIN_LED));
    ESP_ERROR_CHECK(umi_esp32_board_init(&app.board));

    umi_hal_t hal = {
        .button = umi_esp32_button_hal(&app.button),
        .buzzer = umi_esp32_buzzer_hal(&app.buzzer),
        .led = umi_esp32_led_hal(&app.led),
        .board = umi_esp32_board_hal(&app.board),
        .storage = umi_esp32_storage_hal(&app.storage),
        .signer = umi_esp32_signer_hal(&app.signer),
    };
    bind_sensors(&hal);

    umi_identity_t identity = {
        .device_id = device_id(),
        .hw_rev = UMI_HW_SIM ? UMI_HW_REV_DEVKIT : HW_REV_CLIP,
        .fw_version = {UMI_FW_VERSION_MAJOR, UMI_FW_VERSION_MINOR, UMI_FW_VERSION_PATCH},
        .header_flags = UMI_HW_SIM ? UMI_HEADER_FLAG_SIMULATED : 0,
        .activity = UMI_ACTIVITY_UNKNOWN,
    };
    umi_settings_t settings = load_settings();
    umi_clip_init(&app.clip, &hal, &identity, &settings);
    ESP_LOGI(TAG, "device %016" PRIx64 " fw %d.%d.%d%s", identity.device_id, UMI_FW_VERSION_MAJOR,
             UMI_FW_VERSION_MINOR, UMI_FW_VERSION_PATCH, UMI_HW_SIM ? " (simulated sensors)" : "");

    umi_device_info_t info = {
        .device_id = identity.device_id,
        .hw_rev = identity.hw_rev,
        .fw_version = {UMI_FW_VERSION_MAJOR, UMI_FW_VERSION_MINOR, UMI_FW_VERSION_PATCH},
        .serial = "",
    };
    memcpy(info.public_key, app.signer.public_key, UMI_PUBLIC_KEY_LEN);
    app.inbox = xQueueCreate(INBOX_LEN, sizeof(umi_ble_msg_t));
    ESP_ERROR_CHECK(app.inbox != NULL ? ESP_OK : ESP_ERR_NO_MEM);
    umi_ble_publish_settings(&settings);
    ESP_ERROR_CHECK(umi_ble_start(&info, app.inbox, session_index));

    xTaskCreatePinnedToCore(core_task, "umi-core", CORE_STACK, NULL, CORE_PRIORITY, NULL, 1);
}
