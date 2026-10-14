#include "panel.h"

#include <math.h>
#include <stdio.h>
#include <string.h>
#include "encoder.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "lock.h"
#include "freertos/semphr.h"
#include "ui.h"

static const char *TAG = "panel";

// Same constants as the web prototype
#define STEP            2       // % per detent
#define IDLE_MS         6000
#define HOLD_DELAY_MS   3000    // hold this long before the lock ring appears
#define HOLD_FILL_MS    3000    // then it fills; the lock toggles when full
#define CLICK_GAP_MS    350     // clicks closer than this count together
#define POLL_MS         1500
#define TICK_MS         20

typedef struct {
    device_t *dev;
    bool connected;
    float level;          // NAN = unknown
    bool muted;
    float saved;          // level to restore on unmute
    float pending;        // NAN = nothing to send
    int64_t last_local;   // last local change (ms), to ignore stale polls
} knob_t;

static knob_t knobs[PANEL_MAX_KNOBS];
static int n_knobs, focus;
static bool awake;   // the lock lives in lock.c (NVS, passcode, signed iPhone unlock)
static int64_t awake_until;
static SemaphoreHandle_t lock;

// Knob push state
static int clicks;
static int64_t click_deadline, press_start;
static bool pressed, turned, held;
static int press_knob;

static int64_t now_ms(void) { return esp_timer_get_time() / 1000; }

static void wake(void)
{
    awake = true;
    awake_until = now_ms() + IDLE_MS;
}

static void format(const knob_t *k, ui_model_t *m)
{
    const device_driver_t *d = k->dev ? k->dev->driver : NULL;
    float lvl = k->muted ? k->saved : k->level;
    m->control = d ? d->control : CONTROL_LEVEL;
    m->unit[0] = '\0';
    if (isnan(lvl)) {
        strcpy(m->number, "--");
    } else if (m->control == CONTROL_SWITCH) {
        strcpy(m->number, lvl > 0 ? "ON" : "OFF");
    } else if (m->control == CONTROL_TEMPERATURE) {
        snprintf(m->number, sizeof m->number, "%d", (int)lroundf(d->display_min + lvl / 100 * (d->display_max - d->display_min)));
        strcpy(m->unit, "\xC2\xB0");   // °
    } else {
        snprintf(m->number, sizeof m->number, "%d", (int)lroundf(lvl));
    }
    m->bar = isnan(lvl) ? 0 : (int)lvl;
}

static void redraw(int hold_progress)
{
    ui_model_t m = { 0 };
    knob_t *k = &knobs[focus];
    m.awake = awake;
    m.has_device = k->dev != NULL;
    m.connected = k->connected;
    m.muted = k->muted;
    m.locked = lock_get();
    m.hold_progress = hold_progress;
    if (k->dev) strlcpy(m.name, k->dev->name, sizeof m.name);
    if (n_knobs > 1) snprintf(m.knob, sizeof m.knob, "KNOB %d", focus + 1);
    format(k, &m);
    static ui_model_t last;
    static bool drawn;
    if (drawn && memcmp(&m, &last, sizeof m) == 0) return;   // only redraw on change
    last = m;
    drawn = true;
    ui_show(&m);
}

// Ask the knob's network task to send this level (only the newest is sent)
static void set_level(knob_t *k, float level)
{
    k->level = level;
    k->pending = level;
    k->last_local = now_ms();
}

static void turn(int detents)
{
    knob_t *k = &knobs[focus];
    wake();
    if (!k->dev || lock_get() || !k->connected) return;
    float next;
    if (k->dev->driver->control == CONTROL_SWITCH) {
        next = detents > 0 ? 100 : 0;                       // right = on, left = off
    } else {
        float base = k->muted ? k->saved : k->level;
        if (isnan(base)) base = 20;                         // unknown (e.g. Syng): start quiet
        next = fminf(100, fmaxf(0, base + detents * STEP));
    }
    k->muted = false;
    if (next != k->level) set_level(k, next);
}

static void toggle_mute(void)
{
    knob_t *k = &knobs[focus];
    wake();
    if (!k->dev || lock_get() || !k->connected) return;
    if (k->dev->driver->control == CONTROL_SWITCH) {
        set_level(k, k->level > 0 ? 0 : 100);
    } else if (k->muted) {
        k->muted = false;
        set_level(k, isnan(k->saved) ? 20 : k->saved);
    } else {
        k->muted = true;
        k->saved = isnan(k->level) ? 20 : k->level;
        set_level(k, 0);
    }
    ESP_LOGI(TAG, "knob %d: %s", focus + 1, k->muted ? "muted" : "unmuted");
}

static void handle(const enc_event_t *ev)
{
    if (ev->knob >= 0 && ev->knob < n_knobs && ev->knob != focus) {
        focus = ev->knob;                                   // the screen follows the knob touched
        clicks = 0;
    }
    switch (ev->type) {
    case ENC_TURN:
        if (pressed) turned = true;                         // turning isn't holding
        turn(ev->value);
        break;
    case ENC_PRESS:
        pressed = true; turned = false; held = false;
        press_start = now_ms(); press_knob = ev->knob;
        break;
    case ENC_RELEASE:
        pressed = false;
        if (!turned && !held) {                             // a push
            if (!awake) wake();
            clicks++;
            click_deadline = now_ms() + CLICK_GAP_MS;
        }
        break;
    case TOUCH_WAKE:
        wake();
        break;
    case TOUCH_MUTE:
        if (awake) toggle_mute(); else wake();              // a touch on dark glass only wakes it
        break;
    case TOUCH_LEVEL: {
        knob_t *k = &knobs[focus];
        if (!awake) { wake(); break; }
        wake();
        if (!k->dev || lock_get() || !k->connected) break;
        k->muted = false;
        set_level(k, (float)(ev->value / STEP * STEP));
        break;
    }
    }
}

static void panel_task(void *arg)
{
    QueueHandle_t events = arg;
    enc_event_t ev;
    for (;;) {
        bool got = xQueueReceive(events, &ev, pdMS_TO_TICKS(TICK_MS));
        xSemaphoreTake(lock, portMAX_DELAY);
        if (got) handle(&ev);
        int64_t t = now_ms();
        if (clicks && t > click_deadline) {                 // 1 = wake, 2 = mute, 3 = device menu
            if (clicks == 2) toggle_mute();
            else if (clicks >= 3) { wake(); ESP_LOGI(TAG, "device menu: not in firmware yet"); }
            else wake();
            clicks = 0;
        }
        int progress = 0;
        if (pressed && !turned && !held) {
            int64_t h = t - press_start;
            if (h > HOLD_DELAY_MS) progress = (int)((h - HOLD_DELAY_MS) * 100 / HOLD_FILL_MS);
            if (progress >= 100) {
                held = true; progress = 0;
                lock_set(!lock_get());
                wake();
                ESP_LOGI(TAG, "panel %s", lock_get() ? "locked" : "unlocked");
            }
        }
        if (awake && t > awake_until) awake = false;        // 01 IDLE
        redraw(progress);
        xSemaphoreGive(lock);
    }
}

// One per knob: connects, sends the newest level, polls for changes made elsewhere
static void net_task(void *arg)
{
    knob_t *k = arg;
    int64_t next_poll = 0;
    for (;;) {
        if (!k->dev) { vTaskDelay(pdMS_TO_TICKS(500)); continue; }
        if (!k->connected) {
            bool ok = k->dev->driver->connect(k->dev) == ESP_OK;
            xSemaphoreTake(lock, portMAX_DELAY);
            k->connected = ok;
            xSemaphoreGive(lock);
            ESP_LOGI(TAG, "%s (%s at %s): %s", k->dev->name, k->dev->driver->kind, k->dev->host, ok ? "connected" : "connect failed");
            if (!ok) { vTaskDelay(pdMS_TO_TICKS(3000)); continue; }
        }
        xSemaphoreTake(lock, portMAX_DELAY);
        float send = k->pending;
        k->pending = NAN;
        xSemaphoreGive(lock);
        if (!isnan(send)) {
            int64_t t0 = now_ms();
            esp_err_t err = k->dev->driver->set_level(k->dev, send);
            ESP_LOGI(TAG, "%s: set_level(%.0f) %s in %lld ms", k->dev->name, send, err == ESP_OK ? "ok" : "failed", now_ms() - t0);
            if (err != ESP_OK) k->connected = false;
            continue;
        }
        if (now_ms() > next_poll) {
            next_poll = now_ms() + POLL_MS;
            float level;
            if (k->dev->driver->get_level(k->dev, &level)) {
                xSemaphoreTake(lock, portMAX_DELAY);
                bool busy = !isnan(k->pending) || now_ms() - k->last_local < POLL_MS;
                if (!busy) {
                    if (k->muted && level > 0) k->muted = false;   // unmuted elsewhere
                    if (!k->muted) k->level = level;
                }
                xSemaphoreGive(lock);
            }
        }
        vTaskDelay(pdMS_TO_TICKS(TICK_MS));
    }
}

static void on_lock_change(bool now_locked)
{
    xSemaphoreTake(lock, portMAX_DELAY);
    wake();                                                  // show that it's unlocked
    xSemaphoreGive(lock);
}

void panel_start(QueueHandle_t events, device_t *devices[], int knob_count)
{
    lock = xSemaphoreCreateMutex();
    lock_init(on_lock_change);
    n_knobs = knob_count;
    for (int i = 0; i < n_knobs; i++) {
        knobs[i] = (knob_t){ .dev = devices[i], .level = NAN, .saved = NAN, .pending = NAN };
        char name[16];
        snprintf(name, sizeof name, "net%d", i + 1);
        xTaskCreate(net_task, name, 8192, &knobs[i], 4, NULL);
    }
    wake();
    xTaskCreate(panel_task, "panel", 6144, events, 5, NULL);
}
