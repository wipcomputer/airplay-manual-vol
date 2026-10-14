# Contributing

The most useful contribution is a **driver for a device we don't support
yet**: speakers (Bluesound, Denon/Marantz HEOS, Yamaha MusicCast, Google Cast,
Bose), lights and plugs (Matter, Hue, Lutron), saunas, grills, fans, anything
with a level and a local control channel. Fixes, tests and hardware notes
are welcome too.

## Adding a driver

A driver is one small class. The panel only ever calls these methods
(`wallvol/drivers/base.py`), with the level on a 0-100 scale:

| Method | Must |
|---|---|
| `connect()` | Open or reopen the connection. Safe to call again after a failure. |
| `get_volume()` | Return the speaker's real current level, including changes made from elsewhere, or `None` if the speaker can't report it. |
| `set_volume(level)` | Change **this speaker only**, never the whole group, and work while any device is AirPlaying (or casting) to it. |
| `get_reading()` | Optional. A live reading shown under the level when the level is a target: `{"now": 165}`, `{"probe": 140}`, `{"text": "DOOR OPEN"}`. |
| `close()` | Optional cleanup. |

Class attributes tell the panel how to show the device:

| Attribute | Meaning |
|---|---|
| `kind` | the `"driver"` name in config.json |
| `brand` | shown under the device name in menus and setup |
| `control` | `"level"` (percentage), `"temperature"` (a target from `display_min` to `display_max`, shown with `unit`), or `"switch"` (0 = off, above = on) |
| `unit`, `display_min`, `display_max` | for temperature devices, e.g. `"°F"`, 110, 195 (drivers report °F; the panel converts when the home is set to °C) |
| `audio` | `True` for speakers: they take part in Master Volume |
| `startable` | `True` for things the panel starts and stops with a long press (a sauna): level 0 = off, and turning the knob while it's off only sets the target. Leave `False` for anything that mustn't be started remotely (a grill) |

So a sauna driver maps 0-100 to its temperature range, and a plug driver maps
0 to off and 100 to on. `wallvol/drivers/sim.py` has simple examples of each.

Steps:

1. Add `wallvol/drivers/<brand>.py` with a `Driver` subclass and a `kind`.
   Look at `sonos.py` (simplest) and `syng.py` (WebSocket) for the shape.
2. Register it in `wallvol/drivers/__init__.py`.
3. If the speaker can be found on the network, add it to
   `wallvol/discover.py`.
4. Test it with the web prototype (`./run.sh`) on a real device (a speaker:
   while another device is streaming to it). Run `tests/e2e_test.py` too.
5. Add a section to `docs/FINDINGS.md`: how control works, what you tested,
   what didn't work, and anything a firmware port needs to know.

### What makes a good driver

- **Local first.** The panel has to respond instantly and work when the
  internet is down, so use the device's local control when it has one. A cloud
  API is acceptable only when the maker offers nothing local (HUUM and Traeger
  are cloud-only); say so in your FINDINGS section.
- **No phone in daily use.** One-time setup (like pairing) is fine.
- **Tested by ear.** Confirm the speaker actually got louder or quieter. A
  command that returns "OK" isn't proof (see "false successes" in
  docs/FINDINGS.md).
- **Small enough for an ESP32-S3.** Plain HTTP, WebSockets and TLS are easy. Note
  anything heavier (unusual crypto, big libraries) in your FINDINGS section.

## Pull requests

- Keep them focused: one driver or one fix per PR.
- Never commit `config.json`, anything in `credentials/` or `matter/`,
  passwords, pairing codes, or device serials and IDs from your home.
- Say which device model and firmware version you tested on.

By contributing you agree your work is released under the MIT license.
