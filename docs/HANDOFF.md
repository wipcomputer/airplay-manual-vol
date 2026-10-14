# Wall Volume Control — Claude Code Handoff

Oct 13, 2026 · @Parker Todd Brooks

## Brief

We're building a wall-mounted volume control for one speaker per room: a knob plus a small screen, installed like a dimmer under any two-gang Decora plate, sold as a product. The first job is a one-evening proof on a Mac that a third-party device can change one speaker's volume inside a playing AirPlay group without moving the others.

- **Problem:** with music AirPlayed to several speakers, a HomePod's own + and – change the whole group. Today the only per-room control is the per-speaker sliders in the iPhone's AirPlay menu.
- **Why AirPlay alone can't do it:** AirPlay only accepts volume changes from the device that is sending the audio. The panel isn't the sender, so it controls each speaker through that speaker's own network control protocol (a "side door") while the user keeps AirPlaying from their phone as usual.
- **Owner's test house:** HP - BR 1, HP - LR 1 and HomePod Mini (HomePods), P5 (Sonos Play:5), Den 05 Cells (Syng Cell).

## Decisions locked

These are settled; build on them rather than reopening them.

- It's a product to sell, not a home-only hack. Install bar: cut hole, attach power, link in about a minute.
- No hub and no Home Assistant. The panel talks to the speaker directly over Wi-Fi.
- Users keep playing music the way they do now (AirPlay from their phone). The panel only changes volume.
- Physical form: a knob on the left gang and a screen on the right gang, in a standard two-gang box under **any** two-gang Decora plate (e.g. Buster + Punch, Lutron, Leviton). We make the internals, not the plates.
- Knob = endless rotary encoder with detents. Screen = volume display + tap-to-mute. Hold knob 3 s = lock.
- There is an iOS app, but only for setup and management. Daily use needs no phone.
- Wired (line + neutral) is the lead version; battery comes later.
- Speaker support works through per-brand drivers, starting with HomePod and Sonos.
- Look: stainless, Bauhaus, minimal. Futura-style type, one white bar, red is the only color (mute).

## Architecture

Three parts: panel firmware with a driver per speaker brand, the speakers' own control protocols, and an iOS app used only for setup.

- **Panel firmware (ESP32-S3):** reads the encoder, drives the 1.9" display and touch, keeps a persistent connection to its one assigned speaker, and calls a driver interface: `discover()`, `connect(speaker)`, `get_volume()`, `set_volume(level)`, `subscribe(on_change)`. Mute = remember the level, set 0, restore. Lock = ignore input until the next 3 s hold.
- **Drivers:** one per brand behind that interface. HomePod/Apple TV via Apple's Companion/MRP protocol (port pyatv's volume path, including pairing and encryption). Sonos via local UPnP/SOAP (port SoCo's `RenderingControl` volume calls). Others later.
- **Per-speaker semantics:** set the volume of one device inside a group, the way the iPhone's AirPlay sliders do, never the group volume.
- **iOS app (Swift):** AccessorySetupKit Bluetooth setup, Wi-Fi handoff, speaker picker, rename and reassign, max-volume cap, lock rules, OTA firmware updates. App Clip later for scan-to-set-up from the on-screen code.
- **OTA updates are mandatory from day one**, as the hedge against Apple changing its protocol.
- **Fallback if a driver can't run on the ESP32:** a Linux-class chip with the same app and modules.

## Speaker support

HomePod and Sonos are v1; Syng has no known control path yet.

| Speaker | Control path | Reference library | Status |
| --- | --- | --- | --- |
| HomePod, HomePod mini, Apple TV | Apple Companion/MRP protocol | pyatv (Python) | Unofficial; very likely works; test in phase 1 |
| Sonos (e.g. Play:5) | Local UPnP/SOAP on the LAN; no Sonos app or account needed | SoCo (Python) | Stable for 10+ years; official cloud Control API as backup |
| Syng Cell | Unknown; no public API or community integration found | None | The Syng app controls volume over the LAN, so capture its traffic to find the command |
| Bluesound, Denon/Marantz HEOS, Yamaha MusicCast, Google Cast | Each has a local network API | Various | Later, as demand shows |

Plain AirPlay receivers with no side door can't be controlled by the panel. The only workaround is a house AirPlay sender (e.g. OwnTone on an always-on box) that the panel commands, which changes how users play music. It's out of scope for v1.

## Hardware and design

The product is two standard Decora modules in one two-gang box; the [design canvas](https://claude.ai/artifact/GGbEpd3kfqMMmVWjbdVgYj) shows the plate, the screen states and a three-quarter view.

| Module | Gang | Contents | Wiring |
| --- | --- | --- | --- |
| A — Encoder | Left | Endless encoder, detents (\~2% per click), push switch, 6 mm shaft for standard premium knobs | Short cable to B, no mains |
| B — Screen + brain | Right | 1.9" display (\~170×320) under glass with touch, ESP32-S3, AC-to-5V supply | Line + neutral |

- Decora face opening is about 33 × 67 mm; confirm against a real plate.
- Configurations: B alone in one gang (touch to change volume), A + B in two gang (main), A + A + B in three gang (two speakers, one screen).
- Depth is the hard constraint: B's board and supply must fit about the depth of a smart dimmer.
- **Screen states:** 01 Idle (dark glass) · 02 Volume (room name, number, vertical bar, mute circle) · 03 Muted (number and bar dimmed, solid red circle) · 04 Locked (dimmed, lock icon, "HOLD KNOB") · 05 Setup (code that opens the App Clip).
- **Prototype hardware:** M5Stack Dial (knob, round touchscreen and ESP32-S3 in one) for speed, or an ESP32-S3 board with a separate encoder and 1.9" display for the real layout.

## First tasks for Claude Code

Start with phase 1 on the owner's Mac; nothing else gets built until a speaker changes volume on its own.

**Suggested repo layout**

```
wall-volume/
  spike/        # phase 1 Python proofs (pyatv, SoCo)
  firmware/     # ESP32-S3, ESP-IDF or Arduino; drivers/homepod, drivers/sonos
  ios/          # Swift app: setup, management, OTA
  hardware/     # schematics, module drawings, enclosure
  docs/         # this handoff, plan, protocol notes
```

1. **Phase 1 — Mac proof** (spike/)
   - HomePod: `pip3 install pyatv`, `atvremote scan`, pair if asked, then with music AirPlayed to all speakers run `atvremote -n "HP - BR 1" set_volume=20`.
   - Sonos: `pip3 install soco`, then `python3 -c "import soco; s=soco.discovery.by_name('P5'); print(s.volume); s.volume=20"`.
   - Write `spike/knob.py`: a keyboard-driven "virtual knob" (up/down/m for mute) that targets one named speaker through either backend.
   - Pass: only the targeted speaker changes; the iPhone's AirPlay sliders confirm it. Record latency per step.
   - Also check the Home app's "Allow Speaker & TV Access" setting and note what it must be set to.
2. **Protocol notes** (docs/): write down exactly which pyatv and SoCo calls set per-device volume, including pairing, credentials and keep-alive, as the porting spec for firmware.
3. **Phase 2 — firmware** (firmware/): Wi-Fi hard-coded → mDNS discovery → Sonos driver first (simplest) → HomePod driver port → encoder input → display states. Go/no-go: the bedroom knob moves BR 1 only, instantly, for a week.
4. **Phase 3 — iOS app** (ios/, overlapping phase 2): AccessorySetupKit setup, Wi-Fi handoff over BLE, speaker picker, OTA. Done when a fresh panel controls a speaker within a minute of power-on.
5. **Syng spike** (optional): capture Syng app ↔ speaker traffic on the LAN to see whether the volume command is simple enough to add a driver.

## Open questions and links

- Product name and brand (can't use "HomePod").
- Volume display: vertical bar (current) or an arc that echoes the knob.
- Unlock beyond the knob hold: app only, or a staff code for shared spaces.
- Price point; whether our knob ships in finishes.
- Apple path: apply to MFi (native setup sheet) and Matter ("Works with Apple Home" for the panel itself). HomePod volume control stays unofficial unless Apple opens an API. Check current requirements and fees before applying.
- Later market: restaurant restrooms and other shared spaces (per-room volume plus a lock).

**Artifacts**

- [Product plan](https://claude.ai/code/artifact/8b7c2844-d7d8-4b37-b0c0-fdbd1c455b0e): phases, official vs unofficial, risks, next actions.
- [Design canvas](https://claude.ai/artifact/GGbEpd3kfqMMmVWjbdVgYj): stainless two-gang front view, five screen states, three-quarter view.
- This handoff: the brief for Claude Code; export it as Markdown into `docs/HANDOFF.md`.
