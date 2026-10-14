// The panel lock, and unlocking it with an iPhone (NFC tap + Face ID).
//
// The lock state is kept in NVS so it survives power cuts. A paired iPhone
// unlocks by POSTing {"ts":..., "nonce":"...", "sig":"..."} to
// http://<panel>/unlock, where sig = HMAC-SHA256(key, "<panel id>|<ts>|<nonce>")
// in hex; ts must be within 60 s of the panel's clock (SNTP) and the nonce
// unused. Same rules as the web prototype (wallvol/server.py).
#pragma once

#include <stdbool.h>

// Loads the lock state and key, syncs the clock, starts the unlock endpoint.
// `on_change` runs (from another task) when an iPhone unlocks the panel.
void lock_init(void (*on_change)(bool locked));
bool lock_get(void);
void lock_set(bool locked);   // the knob hold
