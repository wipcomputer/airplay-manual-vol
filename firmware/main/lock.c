#include "lock.h"

#include <stdio.h>
#include <string.h>
#include <time.h>
#include "cJSON.h"
#include "esp_http_server.h"
#include "esp_log.h"
#include "esp_netif_sntp.h"
#include "esp_random.h"
#include "mbedtls/md.h"
#include "nvs.h"
#include "sdkconfig.h"

static const char *TAG = "lock";

#define WINDOW_S 60
#define NONCES 16
#define PANEL_ID "panel-1"   // the product's id comes from setup

static bool locked;
static uint8_t key[32];
static bool have_key;
static char used[NONCES][33];
static int next_used;
static void (*changed)(bool);

static void save(void)
{
    nvs_handle_t h;
    if (nvs_open("lock", NVS_READWRITE, &h) != ESP_OK) return;
    nvs_set_u8(h, "locked", locked);
    nvs_commit(h);
    nvs_close(h);
}

static int unhex(const char *hex, uint8_t *out, size_t n)
{
    if (strlen(hex) != n * 2) return -1;
    for (size_t i = 0; i < n; i++) {
        unsigned b;
        if (sscanf(hex + 2 * i, "%2x", &b) != 1) return -1;
        out[i] = (uint8_t)b;
    }
    return 0;
}

static void load_key(void)
{
    nvs_handle_t h;
    size_t len = sizeof key;
    if (unhex(CONFIG_WVP_UNLOCK_KEY, key, sizeof key) == 0) {   // set in menuconfig (development)
        have_key = true;
        return;
    }
    if (nvs_open("lock", NVS_READWRITE, &h) != ESP_OK) return;
    if (nvs_get_blob(h, "key", key, &len) != ESP_OK || len != sizeof key) {
        // Until Bluetooth setup hands the key to the iPhone, make one and print it once
        esp_fill_random(key, sizeof key);
        nvs_set_blob(h, "key", key, sizeof key);
        nvs_commit(h);
        char hex[65];
        for (int i = 0; i < 32; i++) sprintf(hex + 2 * i, "%02x", key[i]);
        ESP_LOGW(TAG, "new unlock key (development only; the iPhone gets it at setup): %s", hex);
    }
    have_key = true;
    nvs_close(h);
}

static const char *check(const char *body)
{
    cJSON *j = cJSON_Parse(body);
    if (!j) return "bad request";
    const cJSON *ts = cJSON_GetObjectItem(j, "ts"), *nonce = cJSON_GetObjectItem(j, "nonce"), *sig = cJSON_GetObjectItem(j, "sig");
    const char *err = NULL;
    time_t now = time(NULL);
    if (!have_key) err = "no paired iPhone";
    else if (!cJSON_IsNumber(ts) || !cJSON_IsString(nonce) || !cJSON_IsString(sig)) err = "bad request";
    else if (now < 1700000000) err = "clock not set yet";
    else if (llabs((long long)now - (long long)ts->valuedouble) > WINDOW_S) err = "message too old";
    else if (strlen(nonce->valuestring) == 0 || strlen(nonce->valuestring) > 32) err = "bad nonce";
    else {
        for (int i = 0; i < NONCES; i++)
            if (strcmp(used[i], nonce->valuestring) == 0) err = "message already used";
    }
    if (!err) {
        char msg[96], hex[65];
        uint8_t mac[32];
        snprintf(msg, sizeof msg, "%s|%lld|%s", PANEL_ID, (long long)ts->valuedouble, nonce->valuestring);
        mbedtls_md_hmac(mbedtls_md_info_from_type(MBEDTLS_MD_SHA256), key, sizeof key,
                        (const uint8_t *)msg, strlen(msg), mac);
        for (int i = 0; i < 32; i++) sprintf(hex + 2 * i, "%02x", mac[i]);
        // constant-time compare
        unsigned diff = strlen(sig->valuestring) != 64;
        for (int i = 0; i < 64 && sig->valuestring[i]; i++) diff |= (unsigned)(hex[i] ^ sig->valuestring[i]);
        if (diff) err = "signature doesn't match";
        else strlcpy(used[next_used++ % NONCES], nonce->valuestring, sizeof used[0]);
    }
    cJSON_Delete(j);
    return err;
}

static esp_err_t on_unlock(httpd_req_t *req)
{
    char body[256];
    int n = httpd_req_recv(req, body, sizeof body - 1);
    if (n <= 0) return httpd_resp_send_err(req, HTTPD_400_BAD_REQUEST, "no body");
    body[n] = '\0';
    const char *err = check(body);
    httpd_resp_set_type(req, "application/json");
    if (err) {
        ESP_LOGW(TAG, "unlock refused: %s", err);
        httpd_resp_set_status(req, "403 Forbidden");
        char out[96];
        snprintf(out, sizeof out, "{\"ok\":false,\"error\":\"%s\"}", err);
        return httpd_resp_sendstr(req, out);
    }
    ESP_LOGI(TAG, "signed unlock verified: unlocked");
    lock_set(false);
    if (changed) changed(false);
    return httpd_resp_sendstr(req, "{\"ok\":true}");
}

void lock_init(void (*on_change)(bool locked))
{
    changed = on_change;
    nvs_handle_t h;
    uint8_t v = 0;
    if (nvs_open("lock", NVS_READONLY, &h) == ESP_OK) {
        nvs_get_u8(h, "locked", &v);
        nvs_close(h);
    }
    locked = v;
    load_key();

    esp_sntp_config_t sntp = ESP_NETIF_SNTP_DEFAULT_CONFIG("pool.ntp.org");   // unlock messages are time-checked
    esp_netif_sntp_init(&sntp);

    httpd_handle_t server = NULL;
    httpd_config_t cfg = HTTPD_DEFAULT_CONFIG();
    if (httpd_start(&server, &cfg) == ESP_OK) {
        httpd_uri_t uri = { .uri = "/unlock", .method = HTTP_POST, .handler = on_unlock };
        httpd_register_uri_handler(server, &uri);
        ESP_LOGI(TAG, "unlock endpoint ready; panel %s", locked ? "locked" : "unlocked");
    }
}

bool lock_get(void) { return locked; }

void lock_set(bool value)
{
    locked = value;
    save();
}
