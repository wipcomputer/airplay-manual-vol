# Firmware

ESP-IDF firmware for the panel, targeting the desk prototype in
[hardware/PARTS.md](../hardware/PARTS.md): a **Waveshare
ESP32-S3-Touch-LCD-1.9** with one to three EC11-type push encoders.

It's a port of an earlier version of the web prototype's behaviour
([docs/UX.md](../docs/UX.md)): turn to change the level, push to wake,
double-push or tap the circle to mute, hold to lock (unlock with a signed
iPhone tap), the touch level bar, idle after 6 s, a screen that follows the
knob in focus, and devices shown as a level, a temperature or ON/OFF.

The demo has moved on since (MENU and Settings, the code keypad, Master
Volume, sauna start / stop with the timer ring, °F / °C, brightness, Auto
Update and more). Porting is deferred on purpose: the list is "Firmware to-do"
in [docs/STATUS.md](../docs/STATUS.md), and the plan is one C core built for
the ESP32 and as a WebAssembly simulator for the demo.

## Status

| Part | State |
|---|---|
| Builds (ESP-IDF v5.5.5, ESP32-S3) | ✅ |
| Display (ST7789V2 via esp_lcd), touch (CST816), LVGL 9.3 screens | Written, not run on hardware |
| Encoders (interrupt quadrature, push switch) | Written, not run on hardware |
| Wi-Fi (credentials from menuconfig) | Written, not run on hardware |
| Sonos driver (SOAP over HTTP) | Written, not run on hardware |
| Syng driver (JSON-RPC over wss) | Written, not run on hardware |
| HUUM sauna driver (HTTPS cloud API) | Written, not run on hardware; no start / stop or session timer yet |
| Lock in NVS + signed iPhone unlock (HMAC over HTTP) | Written, not run on hardware; no code keypad yet |
| HomePod driver (pairing, encryption, MRP, Digest) | Not started |
| MENU / Devices / Settings, Bluetooth setup from the iPhone, multi-panel sync | Not started (menuconfig sets each knob's device for now) |
| OTA updates and the Auto Update setting | Partition table ready; updater not started |
| Matter, Traeger, Master Volume, readings (NOW / PROBE) | Not started |

**Pins are unverified.** Waveshare doesn't publish this board's GPIO map in its
docs. Before wiring, check the schematic or demo code on Waveshare's Resources
page and set every pin in menuconfig.

## Build

Needs ESP-IDF v5.5 ([install guide](https://docs.espressif.com/projects/esp-idf/en/v5.5.5/esp32s3/get-started/)).
On this project's dev Mac it's in `~/esp/esp-idf`.

```sh
. ~/esp/esp-idf/export.sh
cd firmware
idf.py set-target esp32s3        # first time only
idf.py menuconfig                # Wall Volume Panel → Wi-Fi, Knobs and devices, Pins
idf.py build
```

The first build downloads LVGL and the other components listed in
`main/idf_component.yml`.

## Flash and watch the log

Plug the board in with USB-C, then:

```sh
idf.py -p /dev/cu.usbmodem* flash monitor
```

`Ctrl+]` leaves the monitor. The log shows Wi-Fi, each knob's device
connecting, and every `set_level` with its time in milliseconds.

## Wiring the knob

Each encoder: **A**, **B** and the **push switch** to the GPIOs set in
menuconfig, and **C** (common) plus the switch's other leg to **GND**. The
firmware turns on internal pull-ups, so no resistors are needed. EC11 and
PEC11R encoders give 4 quadrature steps per detent (adjustable in menuconfig).

## Layout

```
main/
  main.c        boot: NVS, board, encoders, screen, Wi-Fi, devices, panel
  board.c       display (SPI ST7789), touch (I2C CST816), backlight, LVGL
  encoder.c     knobs: quadrature decoding and push switch, as input events
  ui.c          the screen (LVGL): name, KNOB n, level, bar, mute, lock
  panel.c       behaviour: clicks, hold-to-lock, idle, mute; a network task per knob
  lock.c        lock state in NVS, signed iPhone unlock endpoint
  wifi.c        station mode
  drivers/      device.h (the driver interface), sonos.c, syng.c, huum.c
partitions.csv  two OTA slots
```

Notes:

- The Syng driver connects without verifying the Cell's certificate
  (`CONFIG_ESP_TLS_SKIP_SERVER_CERT_VERIFY`): Cells use Syng's private CA. The
  fix is embedding that CA; the Syng Mac app ships it.
- The screen uses Montserrat (built into LVGL) until the product font is
  chosen.
