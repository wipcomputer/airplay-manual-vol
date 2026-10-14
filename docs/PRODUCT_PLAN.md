# Wall Volume Control — Product Plan

Oct 13, 2026 · @Parker Todd Brooks

## Summary

A wall control that sets one speaker's volume without touching the rest of the house: a knob, a small screen and a mute button, installed like a dimmer under any two-gang Decora plate. It has since grown into a panel for the whole house: up to three knobs and one screen, each knob on its own device (a speaker, all speakers together, a Matter plug or dimmer, a HUUM sauna, a Traeger grill). The go/no-go was a one-evening test on a Mac (passed 2026-10-13: Sonos, HomePod with and without a password, Syng); everything after it is execution.

- **Problem:** with music playing to several HomePods, the + and – on any HomePod change the whole group. The only per-room control today is the individual sliders in the iPhone's AirPlay menu.
- **Fix:** a fixed control in each room that changes only that room's speaker, works without a phone, and can be locked. The same panel can switch to any other device in the home.
- **Buyer:** Apple households with HomePods in several rooms who already spend on premium switches and plates (Buster + Punch, Lutron, Leviton designer lines). Shared spaces such as restaurants are a later market.

## Product

The product is two standard Decora modules, so the customer can use any two-gang Decora plate they like; we never make plates or finishes.

| Module | Gang | What it is | Wiring |
| --- | --- | --- | --- |
| A — Encoder | Left | Endless rotary encoder with detents (about 2% per click) and push switch; standard 6 mm shaft so premium knobs fit; ships with our own knob | Short cable to Module B, no mains |
| B — Screen + brain | Right | 1.9" display under glass with touch for mute; ESP32-S3 board; power supply | Line + neutral, like a smart switch |

**Interaction**

- **Turn:** volume up or down from wherever the speaker is.
- **Push the knob or touch the screen:** wakes the screen.
- **Tap or slide on the screen's volume bar:** sets the level directly (2% steps).
- **Double-push the knob, or tap the mute circle:** mute (remember the level, set it to 0, restore it on the next mute).
- **Triple-push the knob:** the MENU, from anywhere: Devices (switch this knob's device, Master Volume with 2+ speakers, or + Add device to show a setup code) and Settings (Brightness, Dim Brightness, °F / °C, Name, Auto Update, Lock panel). In menus one push picks, two go back a level, three return to the top. Each knob remembers its device.
- **A sauna:** the knob sets the target; holding the knob or the round timer on the screen starts or stops it; the ring empties over the session with the time left under it.
- **Unlock with an iPhone (simulated end to end in the demo):** a passive NFC tag (NTAG215) behind the black glass. Tapping an iPhone on a locked panel opens the panel's App Clip/app, which asks for Face ID and sends an unlock command signed with a key exchanged at setup, so a copied tag is useless. The ESP32 needs no NFC hardware. (The panel can't read the iPhone itself: Apple only exposes iPhone card emulation through Wallet keys.) Bluetooth proximity after Face ID is the no-tag alternative.
- **Hold the knob:** after 3 s a red ring starts filling; when it's full (about 6 s in all) the panel locks.
- **Unlock:** enter the panel's 4-digit code (chosen on the panel at the first lock: SET CODE, CONFIRM CODE) with the knob or touch, or tap a paired iPhone. 5 wrong codes = 30 s wait. The screen shows a lock while it ignores input.
- **Idle:** the screen dims to 5 % (Settings → Dim Brightness); turning or touching wakes it.
- **Setup:** the screen shows a code that opens the iOS setup flow.

**Configurations**

- One-gang: Module B alone, touch the glass to change volume.
- Two-gang: A + B, the main product.
- Three-gang: A + A + B, two devices from one screen.
- Four-gang: A + A + A + B, three devices from one screen.
- Each knob controls its own device (speaker, light, sauna, grill...); the screen follows the knob being touched. Triple-push a knob for the menu: Devices (change its device) and Settings (Brightness, Dim Brightness, °F / °C, lock). The screen sleeps at a dim 5 % rather than going black.

**Screen face:** the screen fills the whole Decora opening (about 33 × 67 mm),
with no frame around it. Either a tall bar display of about 2.9–3" diagonal,
or a full black glass face over a smaller display (the glass hides the
display's border, as on most premium smart switches). Decide when choosing the
display for Module B.

Faces in white, black and a stainless look cover almost every plate system. The design reference is the stainless two-gang canvas (front view, screen states, three-quarter view).

## How it works

The panel talks to its HomePod directly over Wi-Fi, with no hub, using the same control protocol the open-source pyatv library uses to set a HomePod's volume.

- **Per-speaker volume:** the panel sets one speaker's level inside a playing group, the way the iPhone's individual AirPlay sliders do, not the way the HomePod's own buttons do. If you're streaming from a phone, the phone's slider follows the knob.
- **No phone in daily use:** after setup the panel works alone, so a dead phone or a guest without the app changes nothing.
- **iOS app = setup and management only:** Bluetooth setup through AccessorySetupKit (the AirPods-style card), Wi-Fi handoff, speaker picker, rename and reassign, max-volume cap, lock rules, and over-the-air firmware updates. An App Clip lets someone set up from the on-screen code without installing the app.
- **Speaker scope:** plain AirPlay lets only the device that is streaming set volume, so the panel uses each brand's own control protocol through a driver. v1: HomePod and Apple TV (Apple protocol, via pyatv), Sonos (local network control, via SoCo; no Sonos app or account needed) and Syng (local JSON-RPC, found in the Syng app). Others (Bluesound, HEOS, MusicCast, Cast) come later.
- **Other devices:** Matter plugs and dimmers (local, as an extra controller beside Apple Home), HUUM saunas and Traeger grills (their clouds; a grill is never started or stopped from the panel).

## Build plan

Five phases, about three to four months to a panel in every room of the house; phase 2 is the real go/no-go. Firmware comes before the app because the app's main job is talking to the panel, and early firmware can hard-code Wi-Fi.

&#91;embedded content: build roadmap · 5 phases, 1 gate\]

1. **Prove it on the Mac** (one evening)
   - `pip3 install pyatv`, then `atvremote scan`.
   - Play to HP - BR 1, Den 05 Cells and HP - LR 1 from the phone, then run `atvremote -n "HP - BR 1" set_volume=20`.
   - Sonos: pip3 install soco, then set P5's volume with SoCo (exact command in the handoff). Done when: BR 1 and P5 each drop alone while the other speakers stay put in the phone's AirPlay sliders.
2. **Hardware and firmware prototype** (2–4 weeks)
   - M5Stack Dial for speed, or an ESP32-S3 board with a separate encoder and 1.9" display for the real layout.
   - Firmware in order: Wi-Fi (hard-coded), find speakers, port the one volume call, wire it to the knob, add volume, mute and lock screens.
   - Done when: the bedroom knob moves BR 1 only, instantly, through a week of real use.
3. **iOS app prototype** (2–3 weeks, overlapping phase 2)
   - AccessorySetupKit Bluetooth setup, Wi-Fi handoff, speaker picker, panel list, OTA firmware updates. App Clip later.
   - Done when: a factory-fresh panel goes from power-on to controlling a speaker in under a minute.
4. **Decora modules** (after phase 2 passes)
   - Custom board split across Module A and B, faces, power supply, box-depth fit check.
   - Done when: it installs in a standard two-gang box under a stock Decora plate.
5. **Live with it** (one month)
   - A panel in every room, through HomePod software updates, power cuts and Wi-Fi drops.
   - Done when: a month passes with no phone needed for room volume, and a list of what the product actually needs.

## Official vs unofficial

The core function, setting a HomePod's volume from a third-party device, has no official Apple path today; everything around it can be official. HomeKit doesn't expose HomePods as controllable accessories, and Matter doesn't cover them.

| Piece | Status | Route |
| --- | --- | --- |
| HomePod volume control | Unofficial | The pyatv-style protocol; works, but Apple can change it |
| Native Wi-Fi setup sheet, Apple documentation and contacts | Official | Apple MFi program (free to apply, months to approve, per-unit fees and certification) |
| Panel in the Home app, triggers scenes | Official | Matter accessory; "Works with Apple Home" badge covers this part only |
| Setup, management, firmware updates | Official | App Store app |

**Path to fully official**

- **Apple opens the door:** a public API or Matter support for HomePod volume. Pitch it through MFi partner relations, with a shipping product as the argument and existing Apple contacts as the way in.
- **Own the speaker:** a licensed AirPlay 2 in-wall or ceiling speaker controlled by the panel. Fully official, but no longer a HomePod product.

**Plan:** ship with unofficial HomePod control plus official MFi setup, Matter and the app; carry the protocol risk with OTA updates; use the product to make the case to Apple. Current MFi and "Works with Apple Home" requirements and fees need checking before applying.

## Risks

The biggest risk is Apple changing the protocol; the rest are engineering.

| Risk | Impact | Mitigation |
| --- | --- | --- |
| HomePod update changes or blocks the control protocol | Every installed panel stops changing volume | OTA firmware from day one; track pyatv releases; MFi relationship; AirPlay 2 speaker as fallback product |
| Porting the protocol's encrypted pairing to the ESP32-S3 is harder than expected | Phase 2 slips | Linux-class chip as a fallback brain; same app and modules |
| "Allow Speaker & TV Access" set to home members only | Panel refused by the speaker | App checks the setting and walks the user through it; test in phase 1 |
| Some speaker brands have no control path | Those rooms can't get a panel | Per-brand drivers: HomePod, Sonos and Syng done (Syng's command was found in its app's log); add brands as demand shows |
| Module B electronics don't fit box depth | Won't install in common boxes | Depth budget set early; benchmark against smart dimmers |
| Battery version feels slow (reconnect and handshake on each wake) | Poor first impression | Lead with wired; battery version later |

## Next actions

- [x] Run the pyatv test (done on HP - LR 1, with and without a password)
- [x] Identify what "Den 05 Cells" is: a Syng Cell Alpha pair, with local control
- [ ] Order prototype hardware: M5Stack Dial, ESP32-S3 board, encoder, 1.9" display
- [ ] Order a stock two-gang Decora plate and one premium plate to size the module faces
- [ ] Check current MFi and "Works with Apple Home" requirements and fees

**Open questions**

- Product name and brand (can't use "HomePod").
- Price point and whether the knob ships in finishes or one standard.
- ~~Lock unlock method beyond the knob hold~~: decided, a 4-digit code set on the panel, or a paired iPhone tap (NFC + Face ID).
- When to take the restaurant version seriously.

**Related:** [Claude Code handoff](https://claude.ai/code/artifact/24106f2a-7b0e-4976-965c-6aca11f8b282) · [Design canvas](https://claude.ai/artifact/GGbEpd3kfqMMmVWjbdVgYj)
