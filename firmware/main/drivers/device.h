// The driver interface, mirroring wallvol/drivers/base.py. Each knob controls
// one device; the panel only ever calls these functions, so supporting a new
// brand means one new driver.
//
// Levels are 0-100 at this boundary; drivers convert to what the device uses.
#pragma once

#include <stdbool.h>
#include "esp_err.h"

typedef enum {
    CONTROL_LEVEL,        // a percentage (speakers, dimmers)
    CONTROL_TEMPERATURE,  // a target from display_min to display_max
    CONTROL_SWITCH,       // 0 = off, anything above = on
} control_t;

typedef struct device device_t;

typedef struct {
    const char *kind;     // "sonos", "syng", ... (matches config.json in the prototype)
    const char *brand;
    control_t control;
    float display_min, display_max;
    esp_err_t (*connect)(device_t *dev);
    // Real current level including changes made elsewhere; false if unknown
    bool (*get_level)(device_t *dev, float *level);
    esp_err_t (*set_level)(device_t *dev, float level);
    void (*close)(device_t *dev);
} device_driver_t;

struct device {
    const device_driver_t *driver;
    char host[64];
    char name[32];        // shown on the screen
    void *priv;           // driver state
};

// Look up a driver by kind; NULL if unknown
const device_driver_t *device_driver(const char *kind);

extern const device_driver_t sonos_driver;
extern const device_driver_t syng_driver;
extern const device_driver_t huum_driver;
