// HUUM sauna: HUUM's cloud API (as wallvol/drivers/huum.py), HTTPS with the
// HUUM account in HTTP Basic auth: https://api.huum.eu/action/home/{status,start,stop}.
// The knob sets the target (°C 40-110, shown in °F); level 0 stops the sauna.
// Like the HUUM app, it won't start while the door is open.
//
// The device's host field holds "user:password" for now (menuconfig); the
// product gets the login from the iPhone at setup and keeps it in NVS.
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "cJSON.h"
#include "esp_crt_bundle.h"
#include "esp_http_client.h"
#include "esp_log.h"
#include "device.h"

static const char *TAG = "huum";

// api.huum.eu answers a bad login with 403 JSON (the older sauna.huum.eu host
// answers with an empty 200, which cJSON_Parse rejects as a failure anyway)
#define API "https://api.huum.eu/action/home/"
#define MIN_C 40
#define MAX_C 110
#define HEATING 231
#define OFFLINE 230

typedef struct {
    int status;
    bool door_closed;
    int temperature;     // °C now
    int target;          // °C, -1 if none
} huum_status_t;

static esp_err_t call(device_t *dev, const char *action, const char *body, huum_status_t *out)
{
    char url[96], user[64] = "", *pass = NULL;
    snprintf(url, sizeof url, API "%s", action);
    strlcpy(user, dev->host, sizeof user);
    if ((pass = strchr(user, ':'))) *pass++ = '\0';

    esp_http_client_config_t cfg = {
        .url = url, .method = body ? HTTP_METHOD_POST : HTTP_METHOD_GET, .timeout_ms = 8000,
        .auth_type = HTTP_AUTH_TYPE_BASIC, .username = user, .password = pass ? pass : "",
        .crt_bundle_attach = esp_crt_bundle_attach,     // public CA, so verify normally
    };
    esp_http_client_handle_t c = esp_http_client_init(&cfg);
    if (body) esp_http_client_set_header(c, "Content-Type", "application/json");
    esp_err_t err = esp_http_client_open(c, body ? strlen(body) : 0);
    char resp[768] = "";
    if (err == ESP_OK && body && esp_http_client_write(c, body, strlen(body)) < 0) err = ESP_FAIL;
    if (err == ESP_OK) {
        esp_http_client_fetch_headers(c);
        int code = esp_http_client_get_status_code(c);
        int n = esp_http_client_read_response(c, resp, sizeof resp - 1);
        resp[n > 0 ? n : 0] = '\0';
        if (code != 200) {
            ESP_LOGW(TAG, "%s: HTTP %d%s", action, code, code == 401 ? " (check the HUUM login)" : "");
            err = ESP_FAIL;
        }
    }
    esp_http_client_cleanup(c);
    if (err != ESP_OK || !out) return err;

    cJSON *j = cJSON_Parse(resp);
    if (!j) return ESP_FAIL;
    const cJSON *v;
    out->status = (v = cJSON_GetObjectItem(j, "statusCode")) ? v->valueint : 0;
    out->door_closed = cJSON_IsTrue(cJSON_GetObjectItem(j, "door"));
    v = cJSON_GetObjectItem(j, "temperature");   // HUUM sends it as a string or a number
    out->temperature = cJSON_IsNumber(v) ? v->valueint : cJSON_IsString(v) ? atoi(v->valuestring) : 0;
    v = cJSON_GetObjectItem(j, "targetTemperature");   // also a string in practice ("90")
    out->target = cJSON_IsNumber(v) ? v->valueint : cJSON_IsString(v) && v->valuestring[0] ? atoi(v->valuestring) : -1;
    cJSON_Delete(j);
    return ESP_OK;
}

static esp_err_t huum_connect(device_t *dev)
{
    huum_status_t s;
    if (call(dev, "status", NULL, &s) != ESP_OK) return ESP_FAIL;
    if (s.status == OFFLINE) {
        ESP_LOGW(TAG, "the sauna is offline");
        return ESP_FAIL;
    }
    return ESP_OK;
}

static bool huum_get_level(device_t *dev, float *level)
{
    huum_status_t s;
    if (call(dev, "status", NULL, &s) != ESP_OK) return false;
    if (s.status != HEATING || s.target < 0) { *level = 0; return true; }
    float l = (float)(s.target - MIN_C) / (MAX_C - MIN_C) * 100;
    *level = l < 1 ? 1 : l > 100 ? 100 : l;
    return true;
}

static esp_err_t huum_set_level(device_t *dev, float level)
{
    if (level <= 0) return call(dev, "stop", "{}", NULL);
    huum_status_t s;
    if (call(dev, "status", NULL, &s) != ESP_OK) return ESP_FAIL;
    if (s.status != HEATING && !s.door_closed) {
        ESP_LOGW(TAG, "not starting: the sauna door is open");
        return ESP_ERR_INVALID_STATE;
    }
    char body[48];
    snprintf(body, sizeof body, "{\"targetTemperature\":%d}", (int)(MIN_C + level / 100 * (MAX_C - MIN_C) + 0.5f));
    return call(dev, "start", body, NULL);
}

const device_driver_t huum_driver = {
    .kind = "huum", .brand = "HUUM", .control = CONTROL_TEMPERATURE,
    .display_min = 104, .display_max = 230,      // 40-110 °C in °F
    .connect = huum_connect, .get_level = huum_get_level, .set_level = huum_set_level,
};
