// Wall Volume Panel firmware: boot, Wi-Fi, screen, knobs, panel.
#include <string.h>
#include "board.h"
#include "device.h"
#include "encoder.h"
#include "esp_log.h"
#include "nvs_flash.h"
#include "panel.h"
#include "sdkconfig.h"
#include "ui.h"
#include "wifi.h"

static const char *TAG = "main";

// Knob devices from menuconfig (until setup from the iPhone app exists)
static device_t *make_device(const char *kind, const char *host, const char *name)
{
    const device_driver_t *drv = device_driver(kind);
    if (!drv || !host[0]) {
        ESP_LOGW(TAG, "no device: driver \"%s\", host \"%s\"", kind, host);
        return NULL;
    }
    static device_t devs[PANEL_MAX_KNOBS];
    static int used;
    device_t *d = &devs[used++];
    d->driver = drv;
    strlcpy(d->host, host, sizeof d->host);
    strlcpy(d->name, name, sizeof d->name);
    return d;
}

void app_main(void)
{
    ESP_LOGI(TAG, "Wall Volume Panel, firmware 0.1.0");
    esp_err_t err = nvs_flash_init();
    if (err == ESP_ERR_NVS_NO_FREE_PAGES || err == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        err = nvs_flash_init();
    }
    ESP_ERROR_CHECK(err);

    board_init();
    QueueHandle_t events = encoder_init(CONFIG_WVP_KNOB_COUNT);
    ui_init(events);

    if (!wifi_connect(15000)) ESP_LOGW(TAG, "Wi-Fi not connected yet; still trying");

    device_t *devices[PANEL_MAX_KNOBS] = { 0 };
    devices[0] = make_device(CONFIG_WVP_KNOB1_DRIVER, CONFIG_WVP_KNOB1_HOST, CONFIG_WVP_KNOB1_NAME);
#if CONFIG_WVP_KNOB_COUNT >= 2
    devices[1] = make_device(CONFIG_WVP_KNOB2_DRIVER, CONFIG_WVP_KNOB2_HOST, CONFIG_WVP_KNOB2_NAME);
#endif
#if CONFIG_WVP_KNOB_COUNT >= 3
    devices[2] = make_device(CONFIG_WVP_KNOB3_DRIVER, CONFIG_WVP_KNOB3_HOST, CONFIG_WVP_KNOB3_NAME);
#endif
    panel_start(events, devices, CONFIG_WVP_KNOB_COUNT);
}
