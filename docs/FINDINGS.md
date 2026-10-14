# Findings

Tested on 2026-10-13 from a Mac on the same home network as the speakers, with an
iPhone actively AirPlaying to each speaker under test. Every result marked
"confirmed" was checked by ear, not only by a readout (see the pitfall below).

## Summary

| Speaker | Model | Volume control from a third device | How |
|---|---|---|---|
| P5 | Sonos Play:5 | ✅ Confirmed | Local UPnP (SoCo), no setup |
| HP - LR 1, no password | HomePod, tvOS 27.0 | ✅ Confirmed | pyatv, transient pairing |
| HP - LR 1, password on | HomePod, tvOS 27.0 | ✅ Confirmed | One-time pairing + forced tunnel + Digest |
| Den 05 Cells | Syng Cell Alpha (stereo pair) | ✅ Confirmed, any sender | Local JSON-RPC over wss:8765, no login (also via a HomePod group leader) |

In every confirmed case the AirPlay stream from the phone kept playing, and the
phone's own volume slider followed the change (observed on the iPhone). A wall panel can sit alongside
normal AirPlay use, not replace it.

## Sonos

- Volume is set over plain, unencrypted HTTP/UPnP on port 1400.
- It works while the speaker is playing an AirPlay stream (the transport URI
  shows `x-sonos-vli:...airplay:...`).
- No Sonos app, account or pairing is involved. This is easy to implement on a
  microcontroller.

## HomePod

The HomePod's **Home app → Home Settings → Speakers & TV → Allow Speaker & TV
Access** setting decides everything. All tests used **Anyone on the Same
Network**. **Only People Sharing This Home** has not been tested and probably
blocks third-party devices entirely.

### Password off

- `atvremote` works out of the box: pyatv uses transient pairing (fixed PIN
  3939) and opens the remote-control (MRP) tunnel over AirPlay.
- Reading the volume reflects changes made elsewhere (by the phone or by hand),
  so a panel can show the real level when it wakes.

### Password on

Stock pyatv fails in two places:

1. **Remote control:** `Failed to set up remote control channel`.
2. **`atvremote pair`:** `470 Connection Authorization Required`, because it
   starts with `/pair-pin-start`, which a password-protected HomePod rejects.

The steps that work (`spike/homepod_pair.py` and `spike/homepod_volume.py`):

1. **One-time persistent pairing.** HAP pair-setup M1–M6 with
   `X-Apple-HKP: 3`, no transient flag, no `/pair-pin-start`, and **the AirPlay
   password as the SRP PIN**. The resulting long-term keys are saved.
2. **Pair-verify with those keys.** Accepted (200).
3. **Force the MRP tunnel.** pyatv only opens it for HomePods with transient
   credentials (`is_remote_control_supported`), so it has to be forced
   (`MrpTunnel.Force`).
4. **Digest login on the tunnel's RTSP SETUP.** The HomePod answers `401` with
   `WWW-Authenticate: Digest realm="airplay"`. Retry with RFC 2617 Digest,
   username `AirPlay`, password = the AirPlay password, **keeping the same
   CSeq**, and it returns `200`. Volume get and set then work.

Product implication: setup becomes "enter your AirPlay password in the app
once." The panel stores the pairing keys and the password (Digest needs the
password every session). Users keep their speakers protected.

### Pitfall: false successes

If pyatv connects RAOP without the MRP tunnel, `volume` and `set_volume` are
answered from RAOP's **local** state, which only applies when pyatv itself is
streaming. Reads and writes report success while nothing reaches the speaker.
This happened during testing. `homepod_volume.py` connects with AirPlay only to
avoid it. Always confirm by ear.

### Other notes

- Repeated failed pair-setups trigger HomeKit's growing anti-brute-force
  backoff (TLV `Error` / `BackOff`). Test pairing deliberately, not in a loop.
- The pairing may add an entry (named "Panel test" by the script) to the
  speaker's access list in the Home app. Not yet checked.
- Not yet checked: whether the pairing survives a HomePod reboot.

## Syng

### Through a HomePod group leader (works)

When music is started **on a HomePod** (e.g. "Hey Siri, play ... in the Living
Room, Bedroom and Den"), that HomePod becomes the AirPlay group leader. Its MRP
channel then lists every speaker in the group (`groupedDevices` in
DeviceInfo) with its own volume, and accepts `SetVolume` with that speaker's
`outputDeviceUID`. Setting `Den 05 Cells` via HP - LR 1
moved both Cells of the stereo pair together, down and back up, confirmed by
ear, while BR 1 and LR 1 stayed put. `spike/homepod_group_volume.py` does
this.

When the **iPhone** is the leader (music started from the phone and AirPlayed
out), the HomePod reports `isGroupLeader: false` and lists no group members, so
the Syng can't be reached this way. This route works for any AirPlay speaker in
a HomePod-led group, not just Syng.

Quirk: in the group list the leader's own entry read volume 0.0 while its real
volume was 13.4. Read the leader's own volume from `audio.volume`.

### Identification

- Each Cell advertises `_syng._tcp` (SRV port 22) with TXT `homeID`, `roomID`
  and `role=primary|secondary`. A stereo pair shares `homeID` and `roomID`.
  Instance names are `syng<serial>`; the primary answers on port 8765.
- AirPlay/RAOP name is the room name (`Den 05 Cells`), no password.
- Also advertises Spotify Connect (`_spotify-connect._tcp`, port 1988) and
  TIDAL Connect (`_tidalconnect._tcp`).

### Direct control (not found)

Open ports on the primary: 22 (OpenSSH 8.0), 111 (rpcbind), 1988 (Spotify
Connect), 2019 (TIDAL Connect, TLS WebSocket, cert issued by TIDAL), 7000
(AirPlay), 8765 (Syng control, see below), 55093 (unknown). No public API or
open-source integration found.

**Port 8765 is the Syng app's control channel.** A capture of the iPhone's
traffic (USB + `rvictl` + `tcpdump -i rvi0`) while moving the volume in the Syng
app showed the app talking to the primary Cell (.120) on 8765, and nothing to the
secondary. That route works while the iPhone itself is AirPlaying to the Cells,
so it covers the case the HomePod route can't.

- It's a **secure WebSocket (wss)** served by Python `websockets`. The server
  cert is self-signed: subject `O=Syng, OU=Syng Device, CN=<device serial>`,
  issuer `O=Syng, OU=Syng Secure Server, CN=syng.la`.
- **No client certificate is required.** A plain client (verification off)
  connects fine.
- The server sends nothing on connect. Sending `{}` makes it close with 1011,
  so it expects a specific message format, which is still unknown.
- The app's traffic is TLS-encrypted, so the capture shows timing and size only,
  not the messages.

### Direct control (works, any sender)

There is no Android app (Syng lists it as "TBD"). The iOS app runs on Apple
Silicon Macs from the Mac App Store, and it writes a debug log to its container
(`~/Library/Containers/<uuid>/Data/Documents/app.log`) that records every
JSON-RPC call. Moving its volume slider logged:

```
method = source_set_volume, params = VolumeParams(sourceID: "airplay2", volume: 0.187) -> "Ok"
```

The wire format (JSON key `source_id`, from the app's strings) is:

```json
{"jsonrpc":"2.0","id":1,"method":"source_set_volume","params":{"source_id":"airplay2","volume":0.09}}
```

The Cell answers `{"jsonrpc":"2.0","id":1,"timestamp":0,"result":"Ok"}`.

- Sent from the Mac to the primary Cell (`wss://192.168.1.120:8765/`, cert
  verification off) while the **iPhone was AirPlaying to the Cells only**:
  0.19 -> 0.03, then 0.02 for 5 s and back to 0.19. Both Cells of the pair
  dropped and came back. Confirmed by ear, and the iPhone's AirPlay
  slider for the Den (in Apple Music's AirPlay pop-up) followed the change.
- **No authentication.** The app gets cloud tokens (api.prod.syng.space, MQTT)
  for account features, but the local WebSocket accepted the call with none.
- Volume is per audio source (`airplay2`; other source ids not yet listed) on a
  0.0-1.0 scale. The stereo pair follows its primary.
- Not yet found: a call that **reads** the current volume. The app only logged
  `subscribe_viz` (it asks the Cell to stream visualizer data to the app's IP
  and port) besides `source_set_volume`. The app's strings also include
  `room_state_version`, `cell_state_version`, `source_transport`,
  `room_set_tone_control`; the state is probably pushed over MQTT or a
  subscription. Reading volume matters so the panel can show the real level.
- `spike/syng_volume.py` sends the call.

## HUUM sauna (cloud API)

Tested 2026-10-13 with Parker's HUUM UKU sauna ("Crane Sauna").

- `https://api.huum.eu/action/home/{status,start,stop}` with the HUUM app
  login as HTTP Basic auth. A wrong login gets a 403 JSON error; the older
  `sauna.huum.eu` host answers it with an empty 200.
- Numbers arrive as strings: `"temperature": "90"`, `"targetTemperature": "90"`
  (°C). `startDate` / `endDate` are epoch seconds; `duration` is minutes.
  Status 231 = heating, 230 = offline.
- `start` with only `targetTemperature` begins a **new session** (a fresh 3 h),
  so changing the target that way resets the timer in the panel and the HUUM
  app. The driver now sends the running session's `startDate` / `endDate`
  along with the new target (covered by tests/test_huum.py; to be confirmed
  in the HUUM app on the real sauna).
- No sauna name, ID or list: 16 guessed paths (saunas, info, user, profile,
  v1/v2...) all return 404. HUUM's new app names saunas and adds one with the
  Sauna ID + CODE from the module's sticker, through an API that isn't public.
  See README → Help wanted.
- Cloud only: needs internet. The panel's sauna control is the one device that
  can't work offline.

## Implications for the ESP32 panel

- **Sonos:** a simple HTTP request.
- **Syng:** a JSON-RPC message over a TLS WebSocket, no auth. Easy on an
  ESP32-S3 (esp_websocket_client with TLS, cert check skipped or Syng CA pinned).
- **Other AirPlay speakers:** reachable through a HomePod that leads the group,
  using the same HomePod connection plus one extra message.
- **HomePod:** needs SRP-3072/SHA-512 pair-setup, Ed25519/X25519 pair-verify,
  ChaCha20-Poly1305 session encryption, Digest auth, and the MRP protobuf
  messages for volume. All feasible on an ESP32-S3, but this is the bulk of the
  firmware work.
- Apple can change any of this in a software update, so over-the-air firmware
  updates are required from day one.

## References

- [pyatv](https://pyatv.dev)
- [AvianJay/airplaydroid](https://github.com/AvianJay/airplaydroid): source of
  the "persistent pairing + Digest for password receivers" lead
- [SoCo](https://github.com/SoCo/SoCo)
