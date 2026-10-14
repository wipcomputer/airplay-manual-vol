# Where to buy

Shopping lists for the desk prototype and the wall mockup (see
[PARTS.md](PARTS.md) for what each part is for). Exact manufacturer part numbers
(MPN) are given where they matter; otherwise the links are searches, because
marketplace listings change. Check stock and the exact variant (especially
**touch** vs non-touch) before ordering.

## Which store for what

| Store | Best for | Notes |
|---|---|---|
| **Waveshare** (waveshare.com) | The ESP32-S3 screen board | The maker. Ships from China (about 1-2 weeks) unless you pick a US warehouse item. |
| **Amazon** | The board (Waveshare's own store), encoder modules, knobs, jumpers, filament | Fastest for hobby parts. Quality of no-name encoders varies. |
| **Mouser** / **DigiKey** | Brand-name encoders (Bourns, Alps), connectors, anything going toward the product | Exact parts, datasheets, ships in 1-2 days. Same parts you'd use in production. |
| **Micro Center** | Same-day pickup: jumpers, breadboards, USB-C cables, filament, sometimes Waveshare/ESP32 boards | Good if one is near you. Check the store's stock online first. |
| **Adafruit** | Encoder breakout boards and knobs that just work | Well documented, US stock. |
| **SendCutSend** / **Ponoko** | Laser-cut black acrylic face | Upload the DXF from `hardware/` (coming with the CAD files). |

## Desk prototype

| Part | Qty | Amazon | Mouser / DigiKey | Other |
|---|---|---|---|---|
| Waveshare ESP32-S3-Touch-LCD-1.9 (**touch** version) | 1 | [search](https://www.amazon.com/s?k=Waveshare+ESP32-S3+Touch+LCD+1.9) | [DigiKey search](https://www.digikey.com/en/products/result?keywords=ESP32-S3-Touch-LCD-1.9) | [Waveshare](https://www.waveshare.com/product/esp32-related/boards-kits/esp32-s3/esp32-s3-lcd-1.9.htm) (pick the Touch option) |
| Rotary encoder with push switch, 24 detents, 6 mm D shaft: **Bourns PEC11R-4220F-S0024** | 1-3 | — | [Mouser](https://www.mouser.com/c/?q=PEC11R-4220F-S0024) · [DigiKey](https://www.digikey.com/en/products/result?keywords=PEC11R-4220F-S0024) | Equivalent: Alps EC11E series with switch |
| *or* EC11 encoder module (encoder already on a small board with pins) | 1-3 | [search](https://www.amazon.com/s?k=EC11+rotary+encoder+module+push+button) | — | [Adafruit rotary encoder + breakout](https://www.adafruit.com/search?q=rotary+encoder) |
| Knob cap, 6 mm D shaft, aluminium | 1-3 | [search](https://www.amazon.com/s?k=6mm+D+shaft+aluminum+knob) | [Mouser knobs](https://www.mouser.com/c/electromechanical/knobs-dials/) | |
| Female-female jumper wires | 1 pack | [search](https://www.amazon.com/s?k=dupont+jumper+wires+female+female) | | Micro Center |
| Half-size breadboard (only for the bare encoder) | 1 | [search](https://www.amazon.com/s?k=half+size+breadboard) | | Micro Center |
| USB-C data cable | 1 | | | Micro Center |

## Wall mockup

| Part | Qty | Where |
|---|---|---|
| PETG filament (black or white) | 1 spool | Amazon, Micro Center (or print at a library / makerspace) |
| Black cast acrylic, 1.5 mm, cut to the screen face | 1 | SendCutSend or Ponoko (DXF in `hardware/`) |
| Decora screwless wall plate, 2-gang (3- or 4-gang for more knobs) | 1 | Home Depot / Lowe's / Amazon: e.g. Lutron Claro or Leviton Decora. Premium: Buster + Punch |
| Old-work electrical box, 2-gang | 1 | Home Depot / Lowe's |
| #6-32 × 1" device screws (box) and plate screws | a few | Comes with most plates and boxes |
| M3 screws and nuts | a few | Amazon, Micro Center |

## Not yet

Production parts (custom PCB, certified power module, display behind glass)
are in [PARTS.md](PARTS.md) section C. Those come from Mouser / DigiKey or a
contract manufacturer once the board is designed.
