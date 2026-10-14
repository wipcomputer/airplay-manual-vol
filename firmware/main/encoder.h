// Rotary encoders with push switches (EC11 / PEC11R), one per knob.
// Quadrature is decoded in a GPIO interrupt; events are queued for the panel.
#pragma once

#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"

// The panel's input events: knobs, plus touches from the screen (ui.c), all on
// one queue so the panel task handles them in order.
typedef enum {
    ENC_TURN,       // value: +1 / -1 detents
    ENC_PRESS,      // switch went down
    ENC_RELEASE,    // switch came up
    TOUCH_WAKE,     // any touch on the glass
    TOUCH_MUTE,     // the mute circle
    TOUCH_LEVEL,    // the level bar; value: 0-100
} enc_event_type_t;

typedef struct {
    enc_event_type_t type;
    int knob;       // 0-based
    int value;
} enc_event_t;

// Starts `count` encoders (pins from menuconfig) and returns their event queue
QueueHandle_t encoder_init(int count);
