# Status

Last updated 2026-10-13 (late). HANDOFF.md is the planning doc as exported;
PRODUCT_PLAN.md started as one and is kept current. This file tracks what has
actually been done.

## Product

A Decora wall control for the whole house: 1 to 3 knobs plus one screen and an
ESP32-S3 (2-, 3- or 4-gang plates), no hub. Each knob controls its own device
(a speaker, Master Volume, a Matter plug or dimmer, a HUUM sauna, a Traeger
grill), and the screen follows the knob being touched. Panels in a home share
one device list and stay in sync. The earlier touch-LED-bar idea is superseded.

## Phase 1: Mac proof (mostly done)

- [x] Sonos P5: volume read/set via SoCo while AirPlaying. Confirmed by ear and on the iPhone.
- [x] HomePod (LR 1), password off: read/set via pyatv. Confirmed by ear.
- [x] HomePod (LR 1), password on: works with a one-time pairing, a forced MRP
      tunnel and a Digest login. Confirmed by ear. See [FINDINGS.md](FINDINGS.md).
- [x] Home app "Allow Speaker & TV Access" must be "Anyone on the Same Network".
      "Only People Sharing This Home" is not yet tested.
- [x] Group test: three speakers AirPlaying, HP - LR 1 halved (18.5 to 9.3, password on);
      the other two did not move on the iPhone's AirPlay sliders. Confirmed by Parker.
- [ ] Latency per step not recorded.
- [ ] Pairing persistence across a HomePod restart not tested.
- [ ] `spike/knob.py` keyboard "virtual knob" not written.
- [x] Syng Cell pair (Den 05 Cells): volume set through HP - LR 1 as group leader
      (music started by Siri on the HomePod). Both Cells moved, others didn't. Confirmed by ear.
      Doesn't work when the iPhone leads the group.
- [x] Syng direct control, any sender: JSON-RPC `source_set_volume` over wss:8765 on the
      primary Cell, no auth. Found via the Syng Space app's own log (Mac App Store build).
      Confirmed by ear with the iPhone AirPlaying to the Cells only.
- [ ] Syng: read the current volume (needed for the panel's display).
- [x] Syng identification: `_syng._tcp` mDNS with homeID/roomID/role.

## Deviations from the plan

- Syng no longer needs the HomePod route: it has its own local control.
- Other non-Syng, non-Sonos AirPlay speakers can only be controlled through a
  HomePod group leader (music started on the HomePod).

- Plain `atvremote set_volume` does not work on a password-protected HomePod.
  `spike/homepod_pair.py` and `spike/homepod_volume.py` implement the working path.
- pyatv can report a successful volume change that never reached the speaker
  (RAOP answers from local state). Always confirm by ear.

## Web prototype (done)

`./run.sh` starts a local server with the drivers (`wallvol/drivers/`: Sonos,
HomePod, Syng, Matter, HUUM, Traeger, simulated devices) and a browser panel
drawn from the Model 01 mockups. It changes the real devices. Interaction,
decided 2026-10-13: push the knob or touch the screen to wake it; double-push
the knob or tap the mute circle to mute; triple-push for the MENU (Devices,
Settings); hold the knob ~6 s to lock (on a sauna, holding starts or stops it).
The full map is [UX.md](UX.md). The browser panel is the behaviour spec for
the firmware.

- [x] Out-of-box setup simulated: factory reset → SET UP code → phone flow (Wi-Fi sim,
      live speaker scan, room name, real HomePod pairing) → panel live. ESP32-style chip
      log narrates each step. Installable as the `wallvol` command (pyproject.toml).
- [x] One panel controls many devices: triple-push the knob for the MENU → Devices
      (switch, or + Add device). Devices sync across all panels in the home; each
      knob keeps its own active device. AirPlay password asked once per home.
- [x] Master Volume (in Devices with 2+ speakers): all speakers together, balance kept.
- [x] MENU and Settings: Brightness, Dim Brightness (asleep at 5 % by default),
      Temperature °F / °C, Name (typed on the iPhone), Auto Update, Lock panel.
      1 click picks, 2 go back, 3 go to the top MENU; lists end with ‹ Back / Exit.
- [x] Sauna start / stop by long press (timer ring or knob), session countdown ring.
- [x] Up to 3 knobs + one screen (2/3/4-gang plates); each knob its own device; screen follows the focused knob.
- [x] Device kinds: level (%), temperature (°F or °C target), switch (on/off). Simulated light, dimmer, sauna, grill in setup (labeled "(demo)", hidden behind "Show demo devices").
- [~] Real driver: Matter plugs/dimmers (Parker's Tapo P400M 2-outlet plug and P430M dimmer). Bridge + driver + setup step built; awaiting a pairing code to test.
- [x] Real driver: HUUM sauna. Signed in with Parker's account; reads his Crane Sauna live (heating, 90 °C target = 194 °F, NOW 192 °F), now renamed "Crane Sauna" on the panel, with the session ring and time left from its startDate / endDate. Start / stop and target changes from the panel used on the real sauna by Parker; a target change first reset the session timer, fixed by sending the running session's startDate / endDate (Parker to confirm in the HUUM app).
- [ ] HUUM sauna name and sauna list: the API we use (api.huum.eu/action/home/status) has no name and only one sauna; 16 guessed paths (saunas, info, user, profile, v1/v2...) all 404. The new HUUM app shows names and "Add sauna" (Sauna ID + code), so it uses an undocumented API. Next step: capture the app's traffic (e.g. Proxyman on the iPhone) to find it. Until then the name is typed in setup ("e.g. Crane Sauna") or in Settings → Name, "+ Add sauna" is commented out, and the README asks for help from anyone with two saunas.
- [~] Real driver: Traeger grill. Built (Cognito sign-in, MQTT status, set temperature only while cooking, never start/stop); awaiting Parker's test.
- [ ] Try setup from a real iPhone with `--lan`.
- [ ] Real-hardware design for panel-to-panel sync (local network peer sync, or via the iOS app).
- [ ] Remove a speaker from the home (no UI yet).
- [ ] Add an "Offline" screen state to the mockups (the prototype shows OFFLINE in red).
- [ ] Restyle the plate after the Buster + Punch brushed-steel look (on hold, Parker's call).
- [ ] Pair HP - BR 1 and the HomePod Mini.

## Next

1. Real-device runs: Matter pairing (Tapo P400M / P430M), Traeger account.
2. Order the desk prototype parts and bring up the board (Sonos first).
3. Finish phase 1 leftovers: restart persistence, latency.
4. Later: the C core + WebAssembly simulator restructure (below), then port the
   firmware to-do list in one go.

## Phase 2: firmware (started 2026-10-13)

- [x] ESP-IDF project builds for ESP32-S3 (Waveshare ESP32-S3-Touch-LCD-1.9). See firmware/README.md.
- [x] Screen (LVGL), touch, encoders, Wi-Fi, panel behaviour, Sonos and Syng drivers written.
- [ ] Order the desk prototype parts (hardware/BUY.md).
- [ ] Bring-up on the board: verify pins, display offset, touch, encoder direction.
- [ ] First "turn the knob, the speaker changes" on real hardware (Sonos first).
- [ ] MENU / Devices / Settings, setup screen, BLE provisioning, OTA updater (see the firmware to-do below).
- [ ] HomePod driver on the chip.

## Apps and extras

- [x] Apple Watch sauna app stub (apps/watch-sauna): builds and runs in the simulator with the demo sauna.
- [ ] Try the watch app with the real HUUM account and on a real watch.
- [x] NFC unlock in the demo: per-panel key handed to the iPhone at setup, lock held by the panel, HMAC-SHA256 signed unlock with timestamp + single-use nonce, phone unlock screen (Face ID simulated).
- [x] 4-digit unlock code (set on the panel at the first lock: SET CODE / CONFIRM CODE; salted hash; knob or touch keypad; 5 tries then 30 s) in the demo.
- [ ] Unlock code on the ESP32 screen.
- [x] Apple: Developer Program and the wip.computer domain already in place (docs/APPLE.md).
- [ ] NFC unlock on the ESP32 (lock in NVS, verify the HMAC) and in the real iOS app (Keychain, Core NFC tag URL, Face ID).

## Testing

- [x] tests/e2e_test.py: 30 browser checks across setup, sign-ins, Matter, demo device, knob, codes, NFC unlock, Master Volume, sauna start / stop and timer, °F / °C, menus and Settings, rename, dimming, reset (all passing 2026-10-13).
- [x] tests/test_huum.py: the HUUM driver against a captured real reply.
- [x] Real-account run: HUUM sign-in and live status.
- [ ] Real-account runs: Traeger, Matter pairing; HUUM target change / stop.

## Firmware parity with the demo (deferred while features are moving fast)

Decision (Parker, 2026-10-13): keep the HTML demo as the place to try
features for now. Later, restructure into one C core (panel logic + LVGL
screen) with an ESP32 build and a WebAssembly simulator build that becomes
the demo (the industry-standard "simulator from the same code" setup), and
port everything below in one go. Emscripten is installed for that.

### Security

- [x] Demo server API locked down (Host allowlist, JSON + Origin, per-launch
      token incl. the QR link for the phone, Matter bridge secret, device error
      text as text). See SECURITY.md. Firmware to-do: the panel's own local API
      needs the same (and pairing-based auth for the iPhone app).

### Firmware to-do (demo features not on the chip yet)

Demo features the chip doesn't have yet: MENU (triple-push) with Devices and
Settings, Master Volume, SET / CONFIRM / ENTER CODE keypad, live readings
(NOW / PROBE), several devices per knob, panel sync, BLE setup, Matter and
Traeger drivers; sauna start / stop by long press on the timer ring with the
session countdown (HUUM startDate / endDate); °F / °C home setting (double-tap
the temperature); "same kind" list (tap the name, + Add sauna); device rename;
Brightness / Dim Brightness (backlight PWM; asleep = 5 % by default instead of
dark); menu navigation (1 click pick, 2 = back, 3 = top MENU, ‹ Back / Exit
items, lists that scroll); knob hold on a sauna = start / stop; **Auto Update**
(OTA: check the firmware repo's signed GitHub releases daily, install at night
with esp_https_ota and a rollback partition; setting per panel); HUUM target
change keeps the session (send startDate / endDate).
