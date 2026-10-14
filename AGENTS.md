# Instructions for AI assistants

This repo is a Decora wall panel (1-3 knobs plus a screen) that controls
devices around the house: per-speaker volume for AirPlay speakers (Sonos,
HomePod, Syng) while someone else is AirPlaying, plus Matter plugs and
dimmers, a HUUM sauna and a Traeger grill. If the user asks you to run the
demo or the panel prototype, follow these steps. Start in the repo root.

## Run the panel prototype

1. **Check the network.** The computer must be on the same local network as the
   speakers and Matter devices (HUUM and Traeger go through their clouds).
   Python 3.11+ is required. Matter needs Node.js (the bridge in `wallvol/matter/`).
2. **Install and start** (from the repo root):
   ```sh
   ./run.sh            # first run creates .venv and installs; settings live in ./
   ```
   Run it in the background and open http://127.0.0.1:8080/ (on macOS:
   `open http://127.0.0.1:8080/`). Add `--lan` if the user wants to do setup
   from their real iPhone by scanning the code on the panel's screen.
   If `wallvol` is installed instead (`pipx install .`), run `wallvol`; its
   settings live in `~/.wallvol/`.
3. **Setup.** A new panel shows SET UP and a code. Tell the user to click the
   code: a phone frame opens with the setup flow (Wi-Fi, then a device from a
   live scan, a Matter pairing code, or a HUUM / Traeger sign-in; demo devices
   are behind "Show demo devices"). Logins and pairing codes are typed there,
   never into the chat. Triple-clicking the knob opens the MENU: Devices (switch
   or add) and Settings. "+ Add panel" simulates another panel; devices set up
   on any panel sync to all panels, and each knob keeps its own device. The
   AirPlay password is saved for the whole home after the first HomePod. "Factory reset this panel" resets only
   that panel; "Start over as a new user" (or `wallvol reset`) erases
   everything, including pairing keys and the saved password.
4. **HomePods with an AirPlay password** ask for it in setup. The password is
   used once to pair for real. Wrong passwords make the HomePod refuse pairing
   for longer each time, so ask the user to double-check it, and never retry
   in a loop. Speaker & TV Access must be "Anyone on the Same Network" (Home
   app → Home Settings → Speakers & TV).
5. **Check it.** The API needs the per-launch token the server writes to
   `credentials/api-token` (in `~/.wallvol/` when installed with pipx):
   ```sh
   T="X-Wallvol-Token: $(cat credentials/api-token)"
   curl -s -H "$T" localhost:8080/api/panels              # each panel's knobs and devices
   curl -s -H "$T" localhost:8080/api/panels/panel-1/log  # that panel's chip log
   ```
   `/api/panels` lists each panel with its `knobs` (each: device, `connected`,
   `volume`, `error`) and its `devices`. Report anything that didn't connect,
   with the error. Never print the token into the chat or a commit.

Other commands: `wallvol discover` (scan and save speakers), `wallvol reset`
(start over: erases all panels and pairing keys), `--port` to use a port other than 8080.

## Rules

- `config.json`, `credentials/` and `matter/` (the Matter fabric keys) in the repo folder or `~/.wallvol/` are private and gitignored; never `git add` them (an earlier `git add -A` committed `matter/`). Never commit them,
  print a password back, or paste credential file contents.
- Changing a volume is audible in someone's home, and a sauna or grill is a
  heater. Before sending any change to a real device yourself, tell the user,
  and prefer small or reversible changes. Never start or stop a grill.
- A volume command reporting success doesn't prove the speaker changed (see
  "false successes" in docs/FINDINGS.md). When it matters, ask the user to
  confirm by ear.

## Working on the code

- Drivers live in `wallvol/drivers/`, one per brand, all implementing
  `wallvol/drivers/base.py`. See CONTRIBUTING.md to add a brand.
- The panel's behaviour (detents, wake, mute, lock, menus, Settings, idle) is in
  `wallvol/web/index.html`, and the setup flow is `wallvol/web/setup.html`.
  Together they're the spec the ESP32 firmware and iOS app will follow.
- `wallvol/server.py` plays the chip's role. Its log lines are ESP-IDF style;
  mark anything the prototype can't really do with `sim=True`.
- **Firmware parity is deferred for now** (Parker, 2026-10-13: features are
  changing fast). Don't port each demo change to `firmware/main/`; instead add
  it to "Firmware to-do" in docs/STATUS.md. The plan is a later restructure:
  one C core (panel logic + LVGL screen) built for the ESP32 and as a
  WebAssembly simulator that replaces the HTML panel in the demo.
- After changing the panel or setup pages, run `.venv/bin/python tests/e2e_test.py`
  (Playwright; see README → Tests) and fix anything it reports before committing.
- Commit after each change, with a detailed message, and add an entry to
  docs/DEVLOG.md (newest first) for anything worth knowing next session.
- docs/UX.md is the map of every control, screen state and setup step. Update it
  whenever the panel's or setup's behaviour changes.
- Protocol details and test history: docs/FINDINGS.md. Plan and progress:
  docs/PRODUCT_PLAN.md and docs/STATUS.md.
- Notes folders: `ai/` (team notes) and `ai-private/` (anything sensitive)
  exist only in `airplay-manual-vol-private` and are never published. The
  public repo `airplay-manual-vol` is a copy of this one with both left out.
  Everything in `docs/` is public. A future `ai-public/` would be published.
