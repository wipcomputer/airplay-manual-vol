# Parts list

Shopping links by store (Amazon, Mouser, DigiKey, Micro Center...): [BUY.md](BUY.md).

Three stages: a desk prototype to develop the firmware on, a wall mockup
that fits a real electrical box, and the product. Prices are approximate (USD,
late 2026) and only meant for budgeting.

## A. Desk prototype (firmware development)

Everything the firmware in `firmware/` targets. No soldering if you buy an
encoder module with pins.

| Qty | Part | Notes | ~Price |
|---|---|---|---|
| 1 | **Waveshare ESP32-S3-Touch-LCD-1.9** (the *touch* version) | ESP32-S3R8, Wi-Fi + Bluetooth 5, 16 MB flash, 8 MB PSRAM, 1.9" 170×320 IPS screen (ST7789V2) with capacitive touch (CST816), USB-C. [Product docs](https://docs.waveshare.com/ESP32-S3-LCD-1.9) | $20 |
| 1-3 | **Rotary encoder with push switch and detents**, EC11 type, 20-30 detents per turn | Alps EC11E or Bourns PEC11R series, or an "EC11 encoder module" breakout with pull-ups (easiest). One per knob; get 3 to try the 3-knob panel. | $2-5 each |
| 1-3 | Knob cap for a 6 mm shaft | Any aluminium knob for now. The product uses a premium knurled knob. | $2-10 each |
| 1 | Jumper wires (female-female) and a small breadboard | Encoder: A, B, push switch and ground, per knob. | $5 |
| 1 | *(Optional)* NTAG215 NFC stickers | To try the "tap your iPhone to unlock" flow: the tag holds the panel's unlock link; the ESP32 needs no NFC hardware. | $5 for 10 |
| 1 | USB-C data cable | Power, flashing and logs. | — |

**Total: about $35 for one knob.**

Before wiring: check the board's GPIO pins against Waveshare's schematic or
demo code (Resources page) and set them with `idf.py menuconfig` → *Wall
Volume Panel → Pins*. The defaults in the firmware are unverified.

## B. Wall mockup (fits a real box)

To see and use it on a wall. Made by 3D printing the parts a Decora device has.

| Qty | Part | Notes | ~Price |
|---|---|---|---|
| — | **3D-printed Decora parts** (PETG or PLA) | Per gang: a mounting strap that screws into the box (Decora device screw holes are 3.28" / 83.3 mm apart) and a face that fills the Decora opening (about 33 × 67 mm). Screen gang: the face has a window and clamps the board behind it. Knob gang: the face has a hole for the encoder's threaded bushing (7 mm, nut on the front). Models to come in `hardware/`. | filament |
| 1 | Black acrylic, 1-2 mm, laser cut to the face | Covers the screen window for the black-glass look. Any laser-cutting service. | $10 |
| 1 | Decora screwless wall plate, 2-gang (3- or 4-gang for more knobs) | Any brand: Lutron Claro, Leviton, Buster + Punch. Snaps over the printed faces. | $5-60 |
| 1 | Old-work electrical box, 2-gang (for a test wall or a bench stand) | | $5 |
| — | M3 screws, short USB-C cable | Power over USB-C for the mockup; no mains wiring. | $5 |

## C. Product (Model 01): for reference, not yet designed

| Part | Notes |
|---|---|
| Custom PCB in two modules | Module A (encoder gang, no mains) and Module B (screen gang: ESP32-S3 module, display, power), per docs/PRODUCT_PLAN.md. |
| ESP32-S3 module | e.g. ESP32-S3-WROOM-1 (N16R8), certified radio module so the product doesn't need its own radio certification. |
| Display | 1.9" 170×320 IPS behind a black glass face that fills the Decora opening, or a taller bar display if one fits. |
| Mains power (wired version) | A certified, enclosed AC-DC module (e.g. Hi-Link HLK-PM01, 5 V). Line + neutral. Needs electrical safety certification (UL / ETL) before sale. |
| Battery (desktop version) | A rechargeable Li-ion cell with USB-C charging, not a 9 V battery: a 9 V holds about 500 mAh, and Wi-Fi plus a screen would drain it in hours. |
| Knob | Premium knurled aluminium on a 6 mm shaft (standard, so customers can swap in plate-maker knobs). |
