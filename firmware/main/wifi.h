// Wi-Fi station. Credentials come from menuconfig for now; the product gets
// them from the iPhone over Bluetooth during setup.
#pragma once

#include <stdbool.h>

// Connects and blocks until connected or `timeout_ms` passes. Keeps
// reconnecting in the background afterwards.
bool wifi_connect(int timeout_ms);
bool wifi_is_connected(void);
