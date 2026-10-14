// The panel's behaviour: the firmware port of wallvol/web/index.html (see
// docs/UX.md). Knobs, wake, mute, lock, idle, the level bar, and a network
// task per knob that sends the newest level and polls the device.
#pragma once

#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "device.h"

#define PANEL_MAX_KNOBS 3

// Starts the panel. `devices[i]` is knob i's device (NULL = none yet).
void panel_start(QueueHandle_t events, device_t *devices[], int knob_count);
