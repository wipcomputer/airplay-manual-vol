// The panel's screen, drawn with LVGL. Mirrors the states in docs/UX.md:
// 01 idle, 02 volume, 03 muted, 04 locked, offline (05 setup, 06 devices later).
#pragma once

#include <stdbool.h>
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "device.h"

typedef struct {
    bool awake;
    bool has_device;
    bool connected;
    bool muted;
    bool locked;
    int hold_progress;     // 0-100 while the lock ring fills, else 0
    control_t control;
    char name[32];         // device name, e.g. "LIVING ROOM"
    char knob[20];         // "KNOB 2" when the panel has several knobs, else ""
    char number[12];       // "42", "185", "ON"
    char unit[4];          // "°" for temperatures
    int bar;               // 0-100
} ui_model_t;

// Builds the screen; touches are posted to `events` (encoder.h event types)
void ui_init(QueueHandle_t events);

// Redraws from the model (takes the LVGL lock)
void ui_show(const ui_model_t *m);
