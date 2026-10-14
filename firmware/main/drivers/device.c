#include <string.h>
#include "device.h"

static const device_driver_t *const DRIVERS[] = { &sonos_driver, &syng_driver, &huum_driver };

const device_driver_t *device_driver(const char *kind)
{
    for (size_t i = 0; i < sizeof DRIVERS / sizeof DRIVERS[0]; i++) {
        if (strcmp(DRIVERS[i]->kind, kind) == 0) return DRIVERS[i];
    }
    return NULL;
}
