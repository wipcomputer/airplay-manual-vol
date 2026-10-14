// Sonos: UPnP RenderingControl over plain HTTP on port 1400 (what SoCo does).
// No pairing or account. Works while the speaker plays an AirPlay stream.
// See docs/FINDINGS.md#sonos.
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "esp_http_client.h"
#include "esp_log.h"
#include "device.h"

static const char *TAG = "sonos";

#define SERVICE "urn:schemas-upnp-org:service:RenderingControl:1"

// POST one SOAP action; the response body (if any) goes into `out`
static esp_err_t soap(device_t *dev, const char *action, const char *args, char *out, size_t out_len)
{
    char url[160], soap_action[128], body[640];
    snprintf(url, sizeof url, "http://%s:1400/MediaRenderer/RenderingControl/Control", dev->host);
    snprintf(soap_action, sizeof soap_action, "\"" SERVICE "#%s\"", action);
    snprintf(body, sizeof body,
             "<?xml version=\"1.0\"?>"
             "<s:Envelope xmlns:s=\"http://schemas.xmlsoap.org/soap/envelope/\" "
             "s:encodingStyle=\"http://schemas.xmlsoap.org/soap/encoding/\"><s:Body>"
             "<u:%s xmlns:u=\"" SERVICE "\"><InstanceID>0</InstanceID><Channel>Master</Channel>%s</u:%s>"
             "</s:Body></s:Envelope>",
             action, args, action);

    esp_http_client_config_t cfg = { .url = url, .method = HTTP_METHOD_POST, .timeout_ms = 2000 };
    esp_http_client_handle_t client = esp_http_client_init(&cfg);
    esp_http_client_set_header(client, "Content-Type", "text/xml; charset=\"utf-8\"");
    esp_http_client_set_header(client, "SOAPACTION", soap_action);

    esp_err_t err = esp_http_client_open(client, strlen(body));
    if (err == ESP_OK && esp_http_client_write(client, body, strlen(body)) < 0) err = ESP_FAIL;
    if (err == ESP_OK) {
        esp_http_client_fetch_headers(client);
        int status = esp_http_client_get_status_code(client);
        int n = out ? esp_http_client_read_response(client, out, out_len - 1) : 0;
        if (out) out[n > 0 ? n : 0] = '\0';
        if (status != 200) {
            ESP_LOGW(TAG, "%s %s: HTTP %d", dev->host, action, status);
            err = ESP_FAIL;
        }
    }
    esp_http_client_cleanup(client);
    return err;
}

static esp_err_t sonos_connect(device_t *dev)
{
    float level;
    return dev->driver->get_level(dev, &level) ? ESP_OK : ESP_FAIL;   // reachable?
}

static bool sonos_get_level(device_t *dev, float *level)
{
    char resp[512];
    if (soap(dev, "GetVolume", "", resp, sizeof resp) != ESP_OK) return false;
    const char *v = strstr(resp, "<CurrentVolume>");
    if (!v) return false;
    *level = (float)atoi(v + strlen("<CurrentVolume>"));
    return true;
}

static esp_err_t sonos_set_level(device_t *dev, float level)
{
    char args[64];
    snprintf(args, sizeof args, "<DesiredVolume>%d</DesiredVolume>", (int)(level + 0.5f));
    return soap(dev, "SetVolume", args, NULL, 0);
}

const device_driver_t sonos_driver = {
    .kind = "sonos", .brand = "Sonos", .control = CONTROL_LEVEL, .display_min = 0, .display_max = 100,
    .connect = sonos_connect, .get_level = sonos_get_level, .set_level = sonos_set_level,
};
