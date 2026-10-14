# What we need from Apple

The web prototype simulates the iPhone parts. The real product needs a native
iOS app (and an App Clip for scan-to-set-up). This page lists what Apple
requires for each feature, and how logins and passwords can be shared.

**Status:** WIP Computer is already enrolled in the Apple Developer Program
and has wip.computer, so items 1-2 below are covered. The real iOS app, App
Clip, NFC tag reading and the watch app on a real watch can go straight to
TestFlight when they're built. Only the optional items (MFi, Matter
certification) remain.

## To get (in order)

| # | What | Cost | Needed for |
|---|---|---|---|
| 1 | ✅ **Done.** **Apple Developer Program**, organization membership | $99 / year | Everything below: TestFlight, App Store, App Clip, NFC tag reading, Keychain sharing, Associated Domains, push notifications, running the watch app on a real watch |
| 2 | ✅ **Have it** (wip.computer; the `apple-app-site-association` file is still to publish). A domain for the App Clip and NFC links (e.g. a subdomain of wip.computer) with an `apple-app-site-association` file | Existing domain | The NFC tag and the setup code open the app / App Clip; also lets iOS offer our own saved logins |
| 3 | *(Optional, later)* **MFi Program** | Free to apply; per-unit fees and certification | Apple's native accessory setup sheet and Apple contacts. Not needed to ship |
| 4 | *(Optional, later)* **Matter certification** through the CSA | CSA membership + testing fees | "Works with Apple Home" badge for the panel itself. Not needed to ship |

Nothing on this list blocks the prototype or the firmware. Items 1-2, what
the real iOS app needs before TestFlight, are in place.

## Feature by feature

| Feature | Apple pieces | Program needed |
|---|---|---|
| Set up a new panel from the iPhone | **AccessorySetupKit** (the AirPods-style pop-up, iOS 18+) over Bluetooth, Wi-Fi handoff, App Clip from the code on the screen | Developer Program |
| Unlock by tapping the iPhone | **Core NFC** reading the tag behind the glass (an NDEF URL), **Face ID** (LocalAuthentication), the panel's key in the **Keychain** | Developer Program (the NFC tag-reading entitlement) |
| 4-digit code on the panel (set on the panel at the first lock) | Nothing from Apple (it's on the panel) | none |
| Rename a device (Settings → Name on the panel) | Typed in the app; nothing extra | none |
| Keep logins safe on the phone | **Keychain** | none extra |
| Watch app (sauna) | watchOS app, Keychain, WatchConnectivity to get the login from the iPhone | Developer Program to install on a real watch |
| Unlock with Apple Wallet (a "Home Key" in Wallet) | Only for HomeKit locks through MFi | MFi; not planned |

## Sharing passwords (HUUM, Traeger, AirPlay)

**Yes, mostly, and without extra programs.**

- **Password AutoFill.** In the iOS app, the HUUM and Traeger sign-in fields
  are marked as username/password fields. iOS then offers the logins already
  saved in the **Passwords app / iCloud Keychain** (after Face ID). One tap
  instead of typing. The web prototype's sign-in fields are marked the same
  way, so Safari and other password managers can fill them today.
- **Shared with family.** If a login is in a shared group in the Passwords
  app, everyone in that group gets the same AutoFill on their own iPhone.
- **From the iPhone to the panel.** After AutoFill, the app sends the login
  to the panel over the encrypted Bluetooth setup connection; the panel keeps
  it (the sauna and grill are reached through those companies' clouds). The
  app itself never stores it except in the Keychain.
- **What isn't possible:** an app can't read passwords from the Keychain on
  its own, or read another app's saved logins. The user picks the login in the
  AutoFill prompt; that consent is Apple's design.
- **The AirPlay password** isn't usually saved in the Passwords app (it's set
  in the Home app). The panel asks for it once per home and remembers it
  (already built).
