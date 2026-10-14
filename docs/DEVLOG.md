# Dev log

The running story of the project, newest first: what was done, decided,
tested, and left open, so anyone (or any AI) can pick up where the last
session stopped. Commit messages carry the full detail of each change; this
log ties them together, including the dead ends and the reasons behind
decisions. Times are local (Pacific).

---

## 2026-10-14

### 08:30 · Private repo, notes folders, public repo

- The repo folder is now `~/AI/wip-computer-inc/repos/airplay-manual-vol-private`
  and it's on GitHub as `wipcomputer/airplay-manual-vol-private` (private).
- Parker wants a public `wipcomputer/airplay-manual-vol` (MIT), like his other
  repos. Going forward each repo has two notes folders, `ai/` and
  `ai-private/`. Neither is published; a future `ai-public/` would be. All
  docs stay in `docs/` and are public.
- The public repo is a copy of `main` without `ai/`, `ai-private/` and
  anything in `.gitignore`, as one fresh commit (no history, so the
  retired Matter keys in the private history stay private). It's done by hand
  for now: `deploy-public` leaves out `ai/` but not `ai-private/`.
  `CLAUDE.md` stays public (it only points Claude Code at AGENTS.md).
- Before publishing: moved one company-account detail out of docs/APPLE.md
  into `ai-private/apple.md` (Parker's call), and SECURITY.md now says the
  old commits exist only in the private repo.

## Where things stand (end of 2026-10-13)

- **Proven on real speakers:** per-speaker volume from a third device while an
  iPhone AirPlays, for Sonos, HomePod (with or without an AirPlay password) and
  Syng. See [FINDINGS.md](FINDINGS.md).
- **Web prototype** (`wallvol`): a live, installable demo of the panel that
  drives the real speakers, with setup, multi-panel homes, up to three knobs
  per panel, device kinds and simulated whole-house devices.
- **Firmware** (`firmware/`): ESP-IDF project for the Waveshare
  ESP32-S3-Touch-LCD-1.9 that **builds**: screen, touch, knobs, Wi-Fi, panel
  behaviour, Sonos and Syng drivers. Nothing has run on hardware yet (no board
  yet; pins unverified). HomePod, the Devices menu and BLE setup still to do.
- **Hardware:** parts list and where to buy; 3D-printable parts (CadQuery) and
  a 3D viewer in progress.
- **Open product questions:** see [STATUS.md](STATUS.md) and
  [PRODUCT_PLAN.md](PRODUCT_PLAN.md).

---

## 2026-10-13

### 00:40 · Knob always turns; help copy; screw easter egg

- Parker still didn't see the knob turn: turn() updated the angle only after
  its early returns, so on the SET UP screen (his panel was factory fresh), in
  menus, on the code pad and while locked the knob never moved. spinKnob()
  now runs first for every detent (a real knob turns whatever the screen
  shows). e2e checks it on the setup screen.
- "How to use the panel" rewritten as grouped bullets (Knob and screen,
  Menu, Sauna, Lock, Setup) and brought up to date (it still said "device
  menu" and "goes dark").
- Easter egg, unannounced (no cursor, tooltip or README mention): click a
  plate screw and it turns 60° counterclockwise; the third click spins it
  out and opens the 3D parts viewer (/hardware/viewer.html).
- e2e ports from WALLVOL_E2E_PORT / WALLVOL_E2E_MATTER_PORT (defaults 8099 /
  5599), since the reviewer's runs and mine collided on the fixed ports.

### 00:20 · Desktop: hover to turn the knob; setup list spacing

- Parker: turning the knob on a desktop should work by moving the mouse over
  it, no click. Rest the pointer on the knob (250 ms), then right / left =
  up / down, 8 px per detent; a quick pass over it does nothing (the demo
  drives real devices). Drag-in-a-circle and the wheel still work. e2e checks
  it (34).
- Setup: the "Demo devices (simulated)" heading overlapped its card (its
  negative margin relies on the page's flex gap, which didn't apply inside the
  demo block), and with no bottom button the last card ran into the phone's
  rounded corner. Both fixed.
- Review (airplay-tam-security-02) found two hover bugs, both fixed: a slow
  steady pass turned the knob (arming counted time since entering, not
  stillness; now 250 ms with under 3 px of movement), and after a press-drag
  the first nudge added the whole drag distance (hover now re-arms on press,
  release and while a button is down). e2e covers both.
- Parker: "the knob doesn't look like it's turning". Since the first version
  only the knurl rotated: its pattern repeats every 4° and a detent is 12°, so
  every step looked identical. The spun face now turns with it, with a short
  ease.
- Then Parker: drop hover-to-turn ("don't make it scroll without clicking").
  Removed; drag in a circle and the wheel remain. The face rotation and the
  setup spacing fix stay.

### 23:50 · Security hardening of the demo server (branch security-hardening)

The other session's security review (now "airplay-tam-security", the
reviewer; this session codes) found the API open to any website (blind
text/plain POSTs: start the sauna, start-over), DNS rebinding, LAN access with
`--lan`, the same on the Matter bridge, and a panel-page XSS through device
error text. Fixed: Host allowlist, JSON + matching Origin for changes, a
per-launch token (injected into pages for this computer, carried by the setup
QR link for the phone), a per-launch secret + Host check on the bridge, error
text cleaned on the server and rendered as text. e2e 33 checks (Security
section) + tests/test_security.py. Worked in a worktree; awaiting the
reviewer before merging.

### 23:45 · SECURITY.md: the retired Matter keys

Added SECURITY.md so anyone reading the history (or a secret scanner's alert)
knows the Matter controller identity in `a9629c8`..`7ad97a3` is retired: it was
replaced in `f73f2c3` before any device was paired, so nothing trusts it.
Decided not to rewrite history. The key is stored as hex inside matter.js
JSON, not PEM, so GitHub's built-in scanning is unlikely to match it.
Third-party scanners might; close any alert as revoked.

### 23:30 · Repo-wide doc review

Docs still described the first version (one speaker per panel, a Devices
menu on triple-push, a screen that goes dark, sauna mute = off). Updated:
AGENTS.md, CONTRIBUTING.md (drivers beyond speakers, `audio` / `startable`,
"local first" since HUUM and Traeger are cloud-only), STATUS (product, demo
features, next steps, test counts), PRODUCT_PLAN (whole-house panel, MENU and
Settings, sauna, Syng found, decided unlock), UX (menus, rules, setup demo
devices and rename, household / panel settings), APPLE (rows 1-3 done),
FINDINGS (new HUUM section), firmware/README (what the chip has vs the
demo), hardware/PARTS (optional NFC stickers), the watch README (on hold,
known HUUM gaps), pyproject and module docstrings. README by the main session.

### 23:10 · Settings → Name; + Add sauna off; help wanted

- Parker has one sauna, so "+ Add sauna" is commented out of the name-tap list.
- Settings → Name opens a rename screen on the iPhone (`/setup?mode=rename`);
  the panel stays on SETTINGS and shows the new name.
- README: "Help wanted: two HUUM saunas" (what we'd need from someone with
  two saunas or a capture of the HUUM app's traffic).

### 22:45 · Live tuning with Parker: layout, menus, timer reset

- **Timer reset (real sauna):** each knob detent sent HUUM a bare `start`,
  which begins a new 3 h session, so the panel's and the HUUM app's timers
  restarted. The driver now sends the running session's startDate / endDate
  with a target change (test_huum covers both cases). The probe to confirm on
  the real sauna was blocked by the safety classifier; after restarting the
  demo server the session end stayed put. Parker to confirm in the HUUM app.
- **Layout:** first attempt (centered number, bar moved to the edge) was wrong;
  Parker: keep the bar, move the number to the bar's middle, ring + time as one
  unit centered below. Done; Parker: "placement is much better".
- **Hold:** the start/stop ring waits 1 s before filling so triple clicks
  aren't eaten; holding the knob on a sauna = the same start/stop, no red ring.
- **Menus:** Parker got stuck in SETTINGS (no way out). Now: every list ends
  with ‹ Back / Exit; 2 clicks = back (iPod MENU), 3 clicks = top MENU from
  anywhere; pages from SETTINGS return to SETTINGS on every exit; lists scroll
  by swipe. Bug found: pickMenu cleared the return-to-Settings marker before
  the °F/°C choice used it. Also: the poll's re-render replaced menu items
  under a finger and swallowed taps; the list is only rebuilt when it changes.
- **Auto Update** setting (per panel, sim OTA log). **Dim Brightness** 0-100 %.
- **+ Add sauna** opens the phone straight on the HUUM sign-in.
- e2e: 30 checks, all passing. (Its wake tap had to move to a corner: the
  centered number counted it as half a double-tap.)

### 21:30 · Sauna timer ring, °F / °C, Settings and brightness

Parker's asks, all built in the demo and covered by the e2e test (28 checks):
- **Sauna start / stop** by long press (1.5 s) on the screen, like the HUUM
  app; the knob only sets the target while it's off. Parker then asked for "a
  round timer... a full circle that is getting more empty, with the numbers
  below": the bottom control is now that ring (⏻ when off + HOLD TO START;
  steam icon + orange ring + "2:56:44" while heating). HUUM gives startDate /
  endDate; the sim sauna runs 3 h sessions. Works with the real Crane Sauna.
- Bug on the way: the display's `power` modifier class matched the button's
  own `.power { display: none }` rule and hid the whole screen. Renamed to
  `startable`.
- **°F / °C**: double-tap the temperature; home-wide (`POST /api/units`).
- **Tap the name**: every device of that kind (SAUNAS) + "+ Add sauna".
- **Rename**: `POST /api/devices/{id}/rename`; Parker's sauna is now "Crane
  Sauna". Setup's name field hints "e.g. Crane Sauna".
- **Triple-click = MENU** (Devices, Settings). Settings: Brightness, Dim
  Brightness, Temperature, Lock panel. Brightness is per panel
  (`POST /api/panels/{pid}/screen`). The sleeping screen now **dims to 5 %**
  (Parker) instead of going black.
- Flaky e2e "ENTER CODE" check: a poll sent before the lock POST landed
  briefly unlocked the page. The panel now ignores the server's lock state for
  2.5 s after a local change.
- HUUM name / sauna list: no endpoint found (see STATUS). Next: capture the
  new HUUM app's traffic.

### 19:15 · First real device: Parker's HUUM sauna

- Parker signed in with his HUUM account. Sign-in worked; the panel then
  showed "TypeError: unsupported operand type(s) for -: 'str' and 'int'".
- Real status reply: {"statusCode": 231, "door": true, "temperature": "90",
  "targetTemperature": "90", ...}: temperatures are strings. Python and C
  drivers now parse string-or-number. tests/test_huum.py uses that captured
  reply (target 194 °F, NOW 194°, DOOR OPEN, not heating).
- After the fix the panel shows his Crane Sauna live: connected, 194 °F
  target (90 °C), NOW 192 °F.
- The offline label said "NO SPEAKER" for any device; now "OFFLINE".
- Firmware builds; e2e 18/18.
- Open: °C vs °F on the panel (his HUUM app is in °C); changing the target
  and stopping from the panel not yet tried on the real sauna.

### 19:05 · Demo-as-firmware-emulator: agreed direction, deferred

- Parker asked whether the demo should be the firmware running in an
  emulator. Advice given: yes, it's the standard embedded-UI practice (one
  codebase split into HAL + app/UI, with a desktop/browser simulator built
  from the same code; LVGL, TouchGFX, Qt for MCUs, Embedded Wizard, Slint all
  ship one; design mockups like Figma stay throwaway). For us: a C core
  (panel logic + LVGL) with ESP32 and WebAssembly builds; plate, knob and
  phone stay HTML; the server stands in for the network.
- Decision: not yet. Parker is adding features fast, so the HTML demo stays
  the place to try them; the firmware gets a running to-do list (STATUS)
  instead of per-change ports, and the restructure happens when things
  settle. Emscripten installed for later.

### 18:55 · Master Volume

- Parker: with more than one speaker, the Devices menu gets a "Master
  Volume" entry; on a knob it controls all speakers like the iPhone's
  volume. No groups.
- Server: MasterLink/MasterDriver (virtual device "master"): reports the
  loudest speaker's level (as iOS), sets every connected speaker to
  level × its ratio to the loudest (ratios remembered through 0, unknown
  levels follow the master), all at once. Appears in /api/panels devices
  right after the speakers when the home has 2+ audio devices; selectable
  per knob. Drivers gained `audio = True` (Sonos, HomePod, Syng, demo
  speakers). Two demo speakers added (Kitchen, Patio).
- e2e: 18/18 pass, incl. Master Volume in the menu, loudest level shown,
  40/20 → 50/25 after +10.
- Parker: keep the firmware in step with every demo change. Honest status:
  the chip is behind (no Devices menu, Master Volume, code keypad,
  readings, multi-device knobs). AGENTS.md now requires parity per change;
  catching up next.

### 18:45 · "HUUM sauna" did nothing: sign-in code had been deleted; e2e test

- Parker: clicking HUUM sauna did nothing. Cause: the list redesign
  (112e7dd) replaced a slice of setup.html that also held the HUUM/Traeger
  sign-in screens (ACCOUNTS, account(), accountFinish()); the rows called a
  function that no longer existed. Restored from 112e7dd^.
- Lesson: I was checking with screenshots and API calls, which can't catch a
  dead button. Added **tests/e2e_test.py** (Playwright, real clicks, own
  server on :8099 with throwaway settings): 15 checks covering setup and all
  add options, wrong HUUM/Traeger logins showing their errors, Matter code
  validation, a demo device end to end, knob, SET/CONFIRM CODE, wrong/right
  code, NFC unlock, factory reset, and no JS errors. All 15 pass. AGENTS.md
  now says to run it after UI changes.

### 18:35 · Demo devices could be mistaken for real ones

- Parker picked "Sauna" in setup expecting his real HUUM sauna (Crane Sauna,
  89 °C, heating to 90 °C in the HUUM app) and got the simulated one
  (110°, NOW 70°): "I didn't log in on the demo".
- Simulated devices are now named "... (demo)" and hidden behind a "Show
  demo devices" row in setup. The real sauna/grill only appear after signing
  in under "Add by code or account" (HUUM has no local discovery).

### 18:30 · Unlock code is set on the panel, not the iPhone; "device" wording

- Parker: the code is a knob + panel thing. Removed the code field from the
  iPhone setup. The first knob hold now shows SET CODE then CONFIRM CODE on
  the panel's screen (knob turn/push or touch); mismatch → DIDN'T MATCH and
  start over; EXIT cancels without locking; on success the code is saved
  (salted hash, POST /set-code, refused while locked) and the panel locks.
- Setup said "Choose a speaker / Looking for speakers" while scanning; now
  "devices" everywhere it means any device.

### 18:20 · Real iPhone size; reset clears the page; HUUM host fix

- HUUM probe with a wrong login found the API host problem: sauna.huum.eu
  answers with an empty 200, api.huum.eu with a proper 403. Driver (Python
  and C) moved to api.huum.eu, empty replies = rejected login. Traeger's
  Cognito client id and API checked valid the same way. Real-account tests
  of HUUM / Traeger / Matter still need Parker in setup.
- Reset: the page kept each knob's old device in the status lines; a reset
  or start-over now clears all knob state, menus, code entry, last command.
- Phone frame: an iPhone 16 Pro (71.5 x 149.6 mm, 402 x 874 pt, Dynamic
  Island) at the panel's px-per-mm, so both scale together; the setup page
  renders at 402 pt and is scaled down. The Wi-Fi step's row was broken by
  the list redesign (now a proper row with an icon). `?phone=setup` opens
  the phone on load.

### 18:10 · Setup device list redesigned

- Parker: "this UI needs work, and it needs to work." The device list's
  cards were being squashed by the flex layout (rows clipped, no way to
  scroll to the rest) and mixed real and demo devices with long wrapped
  lines.
- Now: sections (In your home / On your network / Add by code or account /
  Demo devices), a coloured icon per device type, one truncating subtitle,
  badges (Set up, Password) and chevrons; rows are a 3-column grid so long
  text truncates; the page scrolls instead of squashing. The intro
  paragraph is gone ("For knob 1").
- Checked with headless Chrome renders (note: headless won't go narrower
  than ~500 px, which first looked like clipping).
- Parker is already an Apple developer with wip.computer: APPLE.md and
  STATUS updated.

### 18:00 · Unlock code; firmware HUUM + lock; what we need from Apple

- Parker's lock spec: **hold to lock; unlock with a 4-digit code or an
  iPhone tap.** The hold no longer unlocks.
- Setup (new panels) asks for the code; the panel keeps a salted SHA-256.
  POST /unlock-code: 5 wrong tries → 30 s lockout. Locked panel: touch, turn
  or push opens ENTER CODE (dots + keypad 1-9 / DEL / 0 / EXIT; knob turns
  move the highlight, push presses; taps and typing work too; closes after
  10 s idle). Tested via the API: wrong ×5 → locked out (even the right code
  refused), after 30 s the right code unlocks. Keypad not clicked through in
  a browser yet.
- Firmware: HUUM driver in C (HTTPS, cert bundle, door check), lock state in
  NVS, signed iPhone unlock endpoint (mbedtls HMAC, SNTP, nonce ring). Builds;
  76 % of the OTA slot free. The code keypad on the chip is next.
- Parker asked about sharing saved passwords and what's needed from Apple:
  docs/APPLE.md (Developer Program $99/yr, a domain for the App
  Clip/NFC links; MFi and Matter certification optional; Password AutoFill
  for HUUM/Traeger logins with Face ID, sent to the panel over the encrypted
  setup connection; an app can't read the Keychain on its own).

### 17:45 · NFC unlock with an iPhone (demo, end to end)

- Each panel gets a secret unlock key at setup, handed to the iPhone in the
  setup response (Bluetooth in the product); the demo phone keeps it in
  browser storage, standing in for the Keychain. Factory reset forgets it.
- The lock moved from the web page into the panel (server): POST /lock from
  the knob hold, `locked` in /api/panels.
- POST /unlock checks HMAC-SHA256(key, "panel|ts|nonce"): timestamp within
  60 s, nonce never seen, constant-time compare. The tag itself only holds a
  URL, so copying it, or replaying a message, does nothing.
- Panel: locked screen says HOLD KNOB / OR TAP IPHONE; a "Tap iPhone (NFC)"
  button opens /unlock in the phone frame: "Unlock with Face ID" (simulated),
  signs with WebCrypto, and the panel unlocks.
- Tested through the API with real signatures: wrong key refused, 5-minute
  old message refused, fresh one unlocked, replay refused. The browser
  WebCrypto path hasn't been clicked through yet.
- Firmware and real iOS app sides are still to do (STATUS).

### 17:30 · Traeger grill, live readings; Matter keys leak fixed

- Order from Parker for the wall panel: sauna, lights, Traeger. Watch app
  on hold.
- **Leak fixed:** with the repo as the settings folder, the Matter bridge's
  fabric (root key pair, NOCs) lived in `./matter/` and an earlier
  `git add -A` committed it. Untracked + gitignored, fabric deleted and
  regenerated. No device had been commissioned and nothing was pushed, so
  the key in history controls nothing.
- `wallvol/drivers/traeger.py`: Traeger cloud as documented by the community
  HA integrations: Cognito sign-in, `/users/self` for grills, pre-signed MQTT
  over WebSocket (paho-mqtt) for status on `prod/thing/update/<thing>`,
  `/things/<thing>/commands` ("90" refresh, "11,<°F>" set). **Safety:** only
  changes the set temperature while the grill is cooking (system_status 4-8),
  never ignites or shuts down; level 0 ignored; 5 °F steps.
- Live readings: drivers may implement `get_reading()`; the screen shows
  "NOW 165°" (and "PROBE 140°", "DOOR OPEN", "OFFLINE") under the target.
  HUUM shows the sauna's temperature and door; Traeger the grill and probe;
  the simulated sauna and grill heat ~1°/s so the demo shows it.
- Setup: "Connect a Traeger grill" (same sign-in step as HUUM).
- Tested: simulated sauna through the API (reading climbed 70 → 76 °F over
  6 s at a 95% target). Not yet tested with the real grill or sauna.

### 17:15 · Apple Watch sauna app; NFC unlock idea

- `apps/watch-sauna/`: a watch-only SwiftUI app (XcodeGen project, watchOS
  10+). Digital Crown = target temperature, current temperature in red while
  heating, Start/Stop, door-open warning and the same start refusal as the
  HUUM app; HUUM cloud directly with the login in the Keychain; a demo sauna
  (`-demo`, `-heat`). Builds with xcodebuild and runs in the watchOS 26.2
  simulator (screenshot in docs/images/watch-sauna.png). The Matter bridge
  now exits with its server (it was surviving restarts and blocking the next
  one).
- Parker asked whether an iPhone could be required to unlock a locked panel
  via NFC. Answer and plan: a passive NFC tag behind the glass opens the app;
  Face ID; an unlock signed with a key from setup. The panel can't read the
  iPhone (Apple restricts card emulation to Wallet keys). Recorded in
  PRODUCT_PLAN, UX and STATUS; not built yet.

### 17:05 · HUUM sauna

- `wallvol/drivers/huum.py`: HUUM's cloud API (the one the HUUM app and Home
  Assistant use): Basic auth to sauna.huum.eu, status / start / stop,
  °C 40-110 shown as a °F target (104-230). Level 0 stops it. Refuses to
  start with the door open, like the HUUM app. Written directly on aiohttp
  (three calls) rather than adding the `huum` library.
- Setup: "Connect a HUUM sauna" asks for the HUUM app login in the setup
  page (never in chat), checks it once, and stores it only in the local
  settings. Generic `/setup/account` endpoint, ready for Traeger.
- Not yet tested with the real sauna.

### 16:55 · Matter lights (real devices)

- Parker's outside lights: **Tapo P400M** (outdoor plug, two outlets) and
  **Tapo P430M** (outdoor dimmer plug), both Wi-Fi Matter.
- `wallvol/matter/bridge.mjs`: a local Matter controller on matter.js
  0.17.9 (Node), started by the server on 127.0.0.1:5541, storing its fabric
  in the settings folder. Commission with a Home app pairing code
  (multi-admin: Apple Home keeps the device), read and set on/off and level.
- `wallvol/drivers/matter.py`: matter-switch (ON/OFF) and matter-dimmer (%)
  through the bridge. Each endpoint is its own device, so the P400M becomes
  "Outside Light 1" and "2".
- Setup: "Add a Matter device" (pairing code + name), adds every endpoint
  to the home and syncs other panels. run.sh installs the bridge.
- Not yet tested with the real plugs: needs a pairing code from Parker.

### 16:45 · 3D parts and viewer

- `hardware/cad/model.py` (CadQuery) builds the wall mockup to real Decora
  standards: printed strap, screen face (window + acrylic recess), knob face,
  board housing, encoder bracket and acrylic cover, plus stand-ins for the
  board, encoder, knob, plate and box. Board and box sizes are APPROX until
  measured.
- Outputs committed: STL per part for 1/2/3-knob panels, printables as STL +
  STEP, the acrylic as DXF, and `parts.json`, which the viewer reads.
- `hardware/viewer.html` (three.js): rotate, explode slider, show/hide parts,
  print/buy tags, 1-3 knobs. Served by the demo at /hardware/viewer.html.
- Demo buttons now only appear when they'd do something.

### 16:15 – now · ESP32 firmware begins

- **Hardware chosen for the prototype** (Parker: "you tell me what the best
  parts are, and dev for that"): **Waveshare ESP32-S3-Touch-LCD-1.9**, the same
  1.9" 170×320 screen size as the product spec, with capacitive touch (CST816),
  ESP32-S3R8, 16 MB flash, 8 MB PSRAM and USB-C, plus **EC11-type push
  encoders** (Bourns PEC11R-4220F-S0024). An M5Stack Dial was the faster
  alternative but has a round screen.
- **Framework: ESP-IDF v5.5.5** (installed at ~/esp/esp-idf), not Arduino,
  because the product needs OTA updates, BLE provisioning, TLS and the HomePod
  crypto. v5.5 over v6 for component maturity. Graphics with LVGL 9.
- **Pins are settings, not guesses.** Waveshare's docs don't publish this
  board's GPIO map (the only table found is for their separate screen module),
  so every pin is in `idf.py menuconfig` with defaults marked VERIFY.
- Written so far: partition table with two OTA slots, sdkconfig defaults, the
  C driver interface mirroring the Python one, Sonos (SOAP/HTTP) and Syng
  (JSON-RPC/wss) drivers, board bring-up (ST7789 + CST816 + LVGL + backlight),
  encoders (interrupt quadrature decoding, push switch), Wi-Fi.
- Then the panel state machine (a port of the web prototype: click counting,
  hold-to-lock with the 3 s delay, idle, mute, the touch level bar, a screen
  that follows the focused knob), the LVGL screen, a network task per knob
  (newest-level sends, 1.5 s polling, reconnects) and `main.c`.
- **First build passes** (16:40). Fixes on the way: esp_lvgl_port now needs
  LVGL 9.3 (`LV_COLOR_FORMAT_RGB565_SWAPPED`), and three buffers the compiler
  proved could truncate. App image 1.3 MB, 78% of each OTA slot free.
  firmware/README.md covers build, menuconfig, flash and wiring.
- Next: hardware bring-up when the board arrives (verify pins, display
  offset, touch, encoder direction); then the Devices menu, BLE setup and
  HomePod (pairing, encryption, MRP, Digest auth on the chip).
- Process: Parker asked for commits as we go, robust commit messages, and this
  dev log. AGENTS.md now requires both.

### 16:15 · Parts lists

- **hardware/PARTS.md:** desk prototype (~$35 for one knob), wall mockup
  (3D-printed Decora strap and faces, laser-cut black acrylic, any Decora
  plate, an old-work box, USB-C power) and product reference (two-module PCB,
  certified ESP32-S3 module, certified AC-DC module needing UL/ETL, a
  rechargeable cell for the desktop version, since a 9 V battery would drain in
  hours).
- **hardware/BUY.md:** by store: Waveshare, Amazon, Mouser, DigiKey, Micro
  Center, Adafruit, SendCutSend/Ponoko. Exact MPN for the encoder; store
  searches elsewhere, since listings change.
- **3D parts:** Homebrew's OpenSCAD cask is disabled (fails Gatekeeper), so the
  models will be **CadQuery** (Python) → STL for printing and STEP for
  Fusion/Onshape/SolidWorks, plus a rotatable, explodable web viewer. CadQuery
  is installed in `.venv-cad/`. In progress.

### 15:55 – 16:12 · Multi-knob panels and device kinds

- **Up to three knobs, one screen** (2-, 3- and 4-gang plates drawn at real
  Decora widths: 114.3 / 160.3 / 206.4 mm, gangs 46.04 mm apart). Each knob
  controls its own device; the screen follows the knob being touched and says
  KNOB 1/2/3; clicking a knob on a setup code sets up that knob.
- **Not just speakers** (Parker: "sauna, outside light 1, outside light 2,
  speaker 1"). Drivers declare a kind: **level** (%), **temperature** (a °F
  target across a range) or **switch** (ON/OFF). Simulated sauna, grill,
  outside lights and dimmer are in setup so the demo can show a whole-house
  panel.
- **Parker's real devices:** a HUUM sauna, a Traeger grill and Matter plugs for
  the outside lights. Five Matter devices and a Homebridge are on the network.
  Plan: Matter plugs first (local; needs a Home app pairing code), then HUUM
  (cloud account) and Traeger (cloud account, read-mostly at first for safety).
- README: one-knob "switch devices" image strip and a three-knob image, all
  rendered from the prototype's CSS by `tools/render_images.py`.
- Instructions and the ESP32 log moved into show/hide sections.

### 15:29 – 15:56 · One panel, whole house; demo polish

- Screen fills the **whole Decora opening** (black glass, no insert frame).
  Hardware note: either a ~2.9" bar display, or black glass over a smaller one
  (how premium smart switches do it).
- Model changed twice in quick succession, as Parker refined it:
  1. one panel = one speaker, with **+ Add panel** (15:40), then
  2. **one panel controls everything**: triple-click the knob for a Devices
     menu (switch, or + Add device), panels in a home **sync** their device
     lists while each keeps its own default, and the **AirPlay password is
     asked once per home** (15:48).
- **docs/UX.md:** a tree of every control, screen state and setup step, with a
  state diagram.
- README images now rendered from the prototype; doing so caught two real
  bugs: the OFFLINE screen was blank (CSS class clash) and the menu's active
  dot wrapped.
- Demo size: 1.75× by default, − / + controls, and a credit-card outline for
  true physical size (CSS pixels differ by display). Safari was caching the old
  page, so pages are now served `no-store`.

### 14:44 – 14:59 · Web prototype becomes an installable demo

- **wallvol** package: Sonos, HomePod and Syng drivers behind one interface,
  a server that plays the ESP32's role, speaker discovery, and a browser panel
  drawn from the Model 01 mockups.
- Interaction decided by Parker while using it: push the knob or touch the
  screen to **wake**; **double-push** (or tap the mute circle) to mute;
  **hold** to lock (the red ring waits 3 s, then fills for 3 s); the volume bar
  is **touch-sensitive**.
- **Out-of-box setup simulated:** factory reset → SET UP code → a phone flow
  standing in for the App Clip (Wi-Fi simulated, real network scan, real
  HomePod pairing) → panel live. An ESP32-style chip log narrates it, with
  simulated steps marked (sim). Factory reset made a true wipe ("act as if I'm
  a brand new user").
- `pip install`-able with a `wallvol` command; `--lan` lets a real iPhone scan
  the setup code. README, AGENTS.md ("tell Claude to run this") and
  CONTRIBUTING.md (add a driver) written for an open-source release.
- The setup page is a web page, not an iOS app: Safari on iPhone has no Web
  Bluetooth, so the real version must be native (AccessorySetupKit + App Clip).

### 14:05 – 14:31 · Syng: from impossible to one JSON message

The requirement Parker set: control must work **no matter who starts the
music**.

1. **Through a HomePod** (14:05): when music is started on a HomePod (Siri),
   that HomePod leads the AirPlay group and its remote-control channel can set
   any member's volume, including the Syng pair. Confirmed by ear. But when the
   iPhone leads (normal AirPlay), the HomePod can't see the group, and a relay
   attempt failed. Not good enough on its own.
2. **Network survey:** the Cells advertise `_syng._tcp` (role primary /
   secondary, shared room ID, which is how a pair is identified). Open ports:
   SSH, rpcbind, Spotify Connect, TIDAL Connect (2019), AirPlay, and **8765**.
3. **Packet capture** of the Syng iPhone app via USB (`rvictl` + `tcpdump`):
   the app talks to the primary Cell on 8765, but the traffic is TLS.
4. **No Android app exists** (Syng lists it as TBD), so APK analysis was out.
5. **The iPhone app runs on Apple Silicon Macs.** Its binary is encrypted, but
   it writes a debug log to its container. Moving its slider logged the exact
   call: `source_set_volume` with `source_id: "airplay2"`, volume 0-1.
6. Sent it from the Mac: the Cells dropped and came back, confirmed by ear,
   and the Den slider in Apple Music's AirPlay pop-up followed. No login.

### 13:50 – 13:53 · Docs and the group test

- Product plan and engineering handoff from the Claude Desktop planning chat
  added to `docs/`; the product is the **two-gang Decora** knob + screen (the
  earlier touch-LED-bar idea is superseded).
- **Group test passed:** with three speakers AirPlaying from the iPhone, LR 1
  was halved and the other two didn't move.

### 13:05 – 13:40 · Proof on real speakers, then the repo

Before the repo existed, from the Mac on the home network:

- **Sonos P5:** volume read and set with SoCo while it played an AirPlay
  stream. No setup at all. Confirmed by ear, and the iPhone's slider followed.
- **HomePod LR 1:** blocked at first. Speaker & TV Access had to be "Anyone on
  the Same Network". With the AirPlay password off, pyatv worked. With it on,
  stock pyatv failed in every combination (four different passwords gave the
  same 470), which turned out to be the pairing mode, not the password.
- **Research** pointed at persistent pairing with the password as the PIN
  (lead from the airplaydroid project). A one-off script paired, then
  **falsely reported success**: pyatv was answering volume from its own local
  state and nothing reached the speaker. Parker caught it ("I didn't see or
  hear it"). Lesson recorded: confirm by ear.
- The real fix: force pyatv's remote-control tunnel, then answer the HomePod's
  **Digest** challenge (user "AirPlay") on the tunnel's RTSP SETUP, keeping the
  same CSeq. Confirmed by ear with the password on.
- **13:39:** repo initialised (MIT, README, FINDINGS, the scripts), now in
  `spike/`.

### Before 13:00 · The idea (Claude Desktop chat)

- Problem: with music on several HomePods, a HomePod's own buttons change the
  whole group; the only per-room control is the iPhone's AirPlay sliders.
- Product: a wall control per room, no hub, keep AirPlaying from the phone,
  an iOS app for setup only, OTA updates from day one, per-brand drivers.
- Design canvas and product plan made there (now in `docs/`).
