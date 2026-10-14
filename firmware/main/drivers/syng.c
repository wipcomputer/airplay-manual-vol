// Syng Cell: JSON-RPC 2.0 over a secure WebSocket on the primary Cell, port
// 8765. No login. A stereo pair follows its primary. See docs/FINDINGS.md#syng.
//
//   {"jsonrpc":"2.0","id":N,"method":"source_set_volume",
//    "params":{"source_id":"airplay2","volume":0.0-1.0}}
//
// Reading the volume isn't solved yet, so get_level returns the last level set.
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "esp_log.h"
#include "esp_websocket_client.h"
#include "freertos/FreeRTOS.h"
#include "device.h"

static const char *TAG = "syng";

typedef struct {
    esp_websocket_client_handle_t ws;
    int next_id;
    bool have_level;
    float level;
} syng_t;

static esp_err_t syng_connect(device_t *dev)
{
    syng_t *s = dev->priv;
    if (!s) {
        s = dev->priv = calloc(1, sizeof *s);
        s->next_id = 1;
    }
    if (s->ws && esp_websocket_client_is_connected(s->ws)) return ESP_OK;
    if (s->ws) {
        esp_websocket_client_destroy(s->ws);
        s->ws = NULL;
    }
    char uri[128];
    snprintf(uri, sizeof uri, "wss://%s:8765/", dev->host);
    esp_websocket_client_config_t cfg = {
        .uri = uri,
        // The Cell's certificate is signed by Syng's private CA (not yet embedded);
        // CONFIG_ESP_TLS_SKIP_SERVER_CERT_VERIFY is set for this reason.
        .skip_cert_common_name_check = true,
        .network_timeout_ms = 3000,
        .reconnect_timeout_ms = 3000,
    };
    s->ws = esp_websocket_client_init(&cfg);
    if (!s->ws || esp_websocket_client_start(s->ws) != ESP_OK) return ESP_FAIL;
    for (int i = 0; i < 50 && !esp_websocket_client_is_connected(s->ws); i++) vTaskDelay(pdMS_TO_TICKS(100));
    if (!esp_websocket_client_is_connected(s->ws)) {
        ESP_LOGW(TAG, "%s: not connected", dev->host);
        return ESP_FAIL;
    }
    return ESP_OK;
}

static bool syng_get_level(device_t *dev, float *level)
{
    syng_t *s = dev->priv;
    if (!s || !s->have_level) return false;
    *level = s->level;
    return true;
}

static esp_err_t syng_set_level(device_t *dev, float level)
{
    if (syng_connect(dev) != ESP_OK) return ESP_FAIL;
    syng_t *s = dev->priv;
    char msg[160];
    int n = snprintf(msg, sizeof msg,
                     "{\"jsonrpc\":\"2.0\",\"id\":%d,\"method\":\"source_set_volume\","
                     "\"params\":{\"source_id\":\"airplay2\",\"volume\":%.3f}}",
                     s->next_id++, level / 100.0f);
    // The Cell answers {"result":"Ok"}; fire-and-forget keeps the knob responsive,
    // and a failed send reconnects on the next turn.
    if (esp_websocket_client_send_text(s->ws, msg, n, pdMS_TO_TICKS(1000)) < 0) return ESP_FAIL;
    s->have_level = true;
    s->level = level;
    return ESP_OK;
}

static void syng_close(device_t *dev)
{
    syng_t *s = dev->priv;
    if (s && s->ws) esp_websocket_client_destroy(s->ws);
    free(s);
    dev->priv = NULL;
}

const device_driver_t syng_driver = {
    .kind = "syng", .brand = "Syng", .control = CONTROL_LEVEL, .display_min = 0, .display_max = 100,
    .connect = syng_connect, .get_level = syng_get_level, .set_level = syng_set_level, .close = syng_close,
};
