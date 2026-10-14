"""Web prototype of the panels, including their out-of-box setup.

Runs on a computer on the same network as the devices and plays the part of
each panel's ESP32: every simulated panel keeps a connection to each device it
knows and sets the level of each knob's device (picked from the MENU →
Devices). The browser draws the panels (/) and the
phone setup flow (/setup?panel=ID, standing in for the iOS App Clip).

Each panel has a chip log (/api/panels/ID/log) narrating what its firmware would
do. Lines marked (sim) are steps the prototype can only pretend to do, such as
Bluetooth and Wi-Fi provisioning. Everything else (speaker scan, pairing,
connection, level commands, cloud sign-ins) is real.
"""

import asyncio
import hashlib
import hmac
import logging
import os
import ipaddress
import re
import secrets
import shutil
import socket
import time
from pathlib import Path
from typing import Optional

import aiohttp
from aiohttp import web

from . import discover
from .drivers import driver_class
from .drivers.matter import bridge_headers as matter_headers
from .pairing import PairingError, pair_homepod

log = logging.getLogger("wallvol")
WEB = Path(__file__).parent / "web"
TOKEN_HEADER = "X-Wallvol-Token"


def error_text(ex: Exception) -> str:
    """An error for the panel and its log. Device-supplied text (e.g. a Sonos
    HTTP 500 body) is untrusted: control characters stripped, length capped."""
    text = re.sub(r"[\x00-\x1f\x7f]+", " ", f"{type(ex).__name__}: {ex}").strip()
    return text if len(text) <= 160 else text[:157] + "..."


# ---- Who may use the API ----
# The demo controls real devices (speakers, a sauna, plugs), so the API is not
# open to whatever else is running in the browser or on the network:
# - Host allowlist: only the names this server is reached by (stops DNS rebinding);
# - state changes must be JSON with a matching Origin (forces a CORS preflight,
#   so another website can't post blind);
# - a per-launch token on every /api call. Pages get it injected when they're
#   loaded from this computer, or by a phone that opened the setup QR link (?t=).
def allowed_hosts(port: int, own: set) -> set:
    """Loopback names plus this computer's own addresses in use (--lan, --host)."""
    names = {"127.0.0.1", "localhost", "[::1]"} | {f"[{a}]" if ":" in a else a for a in own}
    return {f"{n}:{port}" for n in names}


def is_local(request: web.Request, own: set) -> bool:
    """The request comes from this computer (loopback, or one of its own addresses)."""
    try:
        ip = ipaddress.ip_address(request.remote or "")
    except ValueError:
        return False
    return ip.is_loopback or str(ip) in own


def security_middleware(hosts: set, token: str):
    origins = {f"http://{h}" for h in hosts}

    @web.middleware
    async def check(request: web.Request, handler):
        if (request.host or "").lower() not in hosts:
            return web.json_response({"ok": False, "error": "unknown host"}, status=421)
        if request.path.startswith("/api/"):
            if request.method not in ("GET", "HEAD"):
                if request.content_type != "application/json":
                    return web.json_response({"ok": False, "error": "send JSON"}, status=415)
                # A missing Origin is let through on purpose: browsers always send one
                # on cross-origin POSTs, and the token below is still required
                origin = request.headers.get("Origin")
                if origin is not None and origin not in origins:
                    return web.json_response({"ok": False, "error": "wrong origin"}, status=403)
            if not hmac.compare_digest(request.headers.get(TOKEN_HEADER, ""), token):
                return web.json_response({"ok": False, "error": "missing or wrong token"}, status=403)
        return await handler(request)
    return check
FIRMWARE = "Wall Volume Panel, firmware 0.1.0 (prototype)"


class ChipLog:
    """ESP-IDF style log lines: 'I (1234) wifi: connected'."""

    def __init__(self, name: str, size: int = 400) -> None:
        self.name = name
        self.boot = time.monotonic()
        self.lines: list = []
        self.next = 0
        self.size = size

    def __call__(self, tag: str, msg: str, level: str = "I", sim: bool = False) -> None:
        ms = int((time.monotonic() - self.boot) * 1000)
        text = f"{level} ({ms}) {tag}: {msg}{' (sim)' if sim else ''}"
        self.lines = (self.lines + [{"n": self.next, "level": level, "text": text}])[-self.size:]
        self.next += 1
        log.info("[%s] %s: %s%s", self.name, tag, msg, " (sim)" if sim else "")

    def reboot(self) -> None:
        self.boot = time.monotonic()

    def since(self, n: int) -> list:
        return [line for line in self.lines if line["n"] >= n]


class Link:
    """A connection from a panel to one of its speakers, kept alive."""

    def __init__(self, panel: "Panel", entry: dict) -> None:
        self.panel = panel
        self.entry = entry
        self.driver = driver_class(entry["driver"])(entry["host"], **panel.store.driver_options(entry))
        self.connected = False
        self.error: Optional[str] = None
        self.lock = asyncio.Lock()
        self.task = asyncio.create_task(self._keep_connected())

    async def _keep_connected(self) -> None:
        delay = 2
        chip, kind, e = self.panel.chip, self.entry["driver"], self.entry
        while True:
            if not self.connected:
                chip(kind, f"connecting to {e['name']} at {e['host']}")
                try:
                    await self.driver.connect()
                    self.connected, self.error, delay = True, None, 2
                    volume = await self.driver.get_volume()
                    chip(kind, f"{e['room']}: connected" + (f", volume {volume:.0f}" if volume is not None
                                                            else ", volume unknown until first change"))
                except Exception as ex:
                    self.error = error_text(ex)
                    chip(kind, f"{e['room']}: connect failed: {self.error}; retry in {delay} s", level="W")
                    delay = min(delay * 2, 30)
            await asyncio.sleep(delay if not self.connected else 5)

    def failed(self, ex: Exception) -> None:
        self.connected = False
        self.error = error_text(ex)
        self.panel.chip(self.entry["driver"], f"{self.entry['room']}: lost connection: {self.error}", level="E")

    async def close(self) -> None:
        self.task.cancel()
        await self.driver.close()


# ---- Master Volume ----
#
# With two or more speakers in the home, every knob's Devices menu offers
# "Master Volume": the knob then moves all speakers together and keeps their
# balance, like the iPhone's volume. Each speaker is still set individually
# (the panel isn't the AirPlay sender), scaled by the same factor.

MASTER_ID = "master"
MASTER_ENTRY = {"id": MASTER_ID, "name": "Master Volume", "room": "Master Volume", "driver": "master"}


class MasterDriver:
    def __init__(self, panel: "Panel") -> None:
        self.panel = panel
        self.ratios: dict = {}     # each speaker's level relative to the loudest, kept through 0

    def members(self) -> list:
        return [l for l in self.panel.audio_links() if l.connected]

    async def _levels(self, members: list) -> list:
        async def one(link):
            try:
                return await link.driver.get_volume()
            except Exception:
                return None
        return await asyncio.gather(*(one(l) for l in members))

    async def connect(self) -> None:
        pass

    async def get_volume(self) -> Optional[float]:
        known = [v for v in await self._levels(self.members()) if v is not None]
        return max(known) if known else None   # like iOS: the loudest speaker

    async def set_volume(self, level: float) -> None:
        members = self.members()
        levels = await self._levels(members)
        known = {l.entry["id"]: v for l, v in zip(members, levels) if v is not None}
        loudest = max(known.values(), default=0)
        if loudest > 0:
            self.ratios = {i: v / loudest for i, v in known.items()}

        async def set_one(link):
            target = max(0.0, min(100.0, level * self.ratios.get(link.entry["id"], 1.0)))
            async with link.lock:
                await link.driver.set_volume(target)
        await asyncio.gather(*(set_one(l) for l in members))

    async def get_reading(self) -> Optional[dict]:
        n = len(self.members())
        return {"text": f"{n} SPEAKERS"}

    async def close(self) -> None:
        pass


class MasterLink:
    """Looks like a Link to the rest of the server."""

    def __init__(self, panel: "Panel") -> None:
        self.panel = panel
        self.entry = MASTER_ENTRY
        self.driver = MasterDriver(panel)
        self.error: Optional[str] = None
        self.lock = asyncio.Lock()

    @property
    def connected(self) -> bool:
        return bool(self.driver.members())

    def failed(self, ex: Exception) -> None:
        self.error = f"{type(ex).__name__}: {ex}"
        self.panel.chip("master", f"failed: {self.error}", level="E")

    async def close(self) -> None:
        pass


class Panel:
    """What one ESP32 does: knows the household's speakers (synced between
    panels), and has its own active one for the knob."""

    def __init__(self, conf: dict, store) -> None:
        self.id = conf["id"]
        self.conf = conf          # this panel's own settings (its active speaker)
        self.store = store
        self.chip = ChipLog(self.id)
        self.links: dict = {}
        self.master = MasterLink(self)

    def audio_links(self) -> list:
        return [l for l in self.links.values() if driver_class(l.entry["driver"]).audio]

    def has_master(self) -> bool:
        return sum(1 for s in self.speakers if driver_class(s["driver"]).audio) >= 2

    @property
    def speakers(self) -> list:
        return self.store.household["speakers"]

    @property
    def configured(self) -> bool:
        return any(k["active"] for k in self.conf["knobs"])

    def link_for(self, knob: int) -> Optional[Link]:
        knobs = self.conf["knobs"]
        if not 0 <= knob < len(knobs):
            return None
        if knobs[knob]["active"] == MASTER_ID:
            return self.master if self.has_master() else None
        return self.links.get(knobs[knob]["active"] or "")

    async def connect_all(self) -> None:
        await self.release()
        if not self.configured:
            return  # a factory-fresh panel isn't on Wi-Fi yet
        for entry in self.speakers:
            self.links[entry["id"]] = Link(self, entry)

    async def add(self, entry: dict) -> None:
        old = self.links.pop(entry["id"], None)
        if old:
            await old.close()
        self.links[entry["id"]] = Link(self, entry)

    async def release(self) -> None:
        for link in self.links.values():
            await link.close()
        self.links = {}


    def boot_log(self) -> None:
        self.chip("boot", FIRMWARE)
        if self.configured:
            knobs = ", ".join(f"knob {i + 1}: {(self.store.household_speaker(k['active'] or '') or {}).get('room', 'not set')}"
                              for i, k in enumerate(self.conf["knobs"]))
            rooms = ", ".join(s["room"] for s in self.speakers)
            self.chip("nvs", f"settings: {knobs}; home devices: {rooms}")
            self.chip("wifi", f"connected, IP {lan_ip()}", sim=True)
        else:
            self.chip("nvs", "no settings: factory fresh")
            self.chip("ble", "advertising as \"Wall Volume Panel\", waiting for setup", sim=True)
            self.chip("display", "screen 05 SETUP: showing setup code")

    async def state(self) -> dict:
        knobs = []
        for i in range(len(self.conf["knobs"])):
            link = self.link_for(i)
            volume = None
            if link and link.connected:
                try:
                    volume = await link.driver.get_volume()
                except Exception as ex:
                    link.failed(ex)
            reading = None
            if link and link.connected:
                try:
                    reading = await link.driver.get_reading()
                except Exception:
                    reading = None
            knobs.append({"speaker": describe(link.entry) if link else None,
                          "connected": bool(link and link.connected), "volume": volume,
                          "reading": reading, "error": link.error if link else None})
        devices = []
        entries = self.speakers if self.configured else []
        audio = [e for e in entries if driver_class(e["driver"]).audio]
        others = [e for e in entries if not driver_class(e["driver"]).audio]
        for entry in audio:
            l = self.links.get(entry["id"])
            devices.append({**describe(entry), "connected": bool(l and l.connected)})
        if self.has_master():   # right after the speakers
            devices.append({**describe(MASTER_ENTRY), "connected": self.master.connected})
        for entry in others:
            l = self.links.get(entry["id"])
            devices.append({**describe(entry), "connected": bool(l and l.connected)})
        first = knobs[0] if knobs else {}
        return {
            "id": self.id,
            "configured": self.configured,
            "locked": bool(self.conf.get("locked")),
            "has_passcode": bool(self.conf.get("passcode")),
            "screen": {"brightness": 100, "dim": 5, **self.conf.get("screen", {})},
            "auto_update": self.conf.get("auto_update", True),
            "knobs": knobs,
            "devices": devices,
            # knob 1, for older clients and the tab label
            "speaker": first.get("speaker"), "connected": first.get("connected", False),
            "volume": first.get("volume"), "error": first.get("error"),
        }


def describe(entry: dict) -> dict:
    """What the panel needs to show a device: name, room and how to display it."""
    base = {"id": entry["id"], "name": entry["name"], "room": entry["room"], "driver": entry["driver"]}
    if entry["driver"] == "master":
        return {**base, "control": "level", "unit": "%", "min": 0, "max": 100, "brand": "All speakers", "startable": False}
    return {**base, **driver_class(entry["driver"]).display()}


def lan_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("192.0.2.1", 9))  # no packet is sent; just picks the outgoing interface
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


# ---- helpers ----

def get_panel(request: web.Request) -> Panel:
    panel = request.app["panels"].get(request.match_info["pid"])
    if panel is None:
        raise web.HTTPNotFound(text="no such panel")
    return panel


async def add_live_panel(app: web.Application, panel_conf: dict) -> Panel:
    panel = Panel(panel_conf, app["store"])
    app["panels"][panel.id] = panel
    panel.boot_log()
    await panel.connect_all()
    return panel


# ---- panels ----

async def list_panels(request: web.Request) -> web.Response:
    app = request.app
    panels = [await p.state() for p in app["panels"].values()]
    return web.json_response({"panels": panels, "setup_url": app["setup_url"], "units": app["store"].units})


async def set_units(request: web.Request) -> web.Response:
    """°C / °F for the whole home (the panel's units screen)."""
    store = request.app["store"]
    store.set_units(str((await request.json()).get("units", "F")))
    for p in request.app["panels"].values():
        p.chip("nvs", f"temperatures in °{store.units}")
    return web.json_response({"ok": True, "units": store.units})


async def rename_device(request: web.Request) -> web.Response:
    """Rename a device for the whole home (e.g. "Sauna" → "Crane Sauna")."""
    name = str((await request.json()).get("name", "")).strip()[:24]
    if not name:
        return web.json_response({"ok": False, "error": "Enter a name"}, status=400)
    entry = request.app["store"].rename(request.match_info["did"], name)
    if not entry:
        raise web.HTTPNotFound(text="no such device")
    for p in request.app["panels"].values():
        link = p.links.get(entry["id"])
        if link:
            link.entry = entry
        p.chip("nvs", f"renamed a device to \"{name}\"")
    return web.json_response({"ok": True})


async def create_panel(request: web.Request) -> web.Response:
    app = request.app
    panel = await add_live_panel(app, app["store"].add_panel())
    return web.json_response(await panel.state())


async def panel_state(request: web.Request) -> web.Response:
    return web.json_response(await get_panel(request).state())


async def delete_panel(request: web.Request) -> web.Response:
    app = request.app
    panel = get_panel(request)
    await panel.release()
    app["store"].remove_panel(panel.id)
    del app["panels"][panel.id]
    if not app["panels"]:
        await add_live_panel(app, app["store"].add_panel())
    return web.json_response({"ok": True})


async def set_volume(request: web.Request) -> web.Response:
    panel = get_panel(request)
    body = await request.json()
    level = max(0.0, min(float(body["level"]), 100.0))
    knob = int(body.get("knob", 0))
    link = panel.link_for(knob)
    if not link or not link.connected:
        return web.json_response({"ok": False, "error": (link and link.error) or "not connected"}, status=503)
    async with link.lock:  # one command at a time per speaker
        start = time.monotonic()
        try:
            await link.driver.set_volume(level)
        except Exception as e:
            link.failed(e)
            return web.json_response({"ok": False, "error": link.error}, status=502)
        ms = round((time.monotonic() - start) * 1000)
    panel.chip(link.entry["driver"], f"knob {knob + 1} → {link.entry['room']}: set_level({level:.0f}) ok in {ms} ms")
    return web.json_response({"ok": True, "level": level, "ms": ms})


async def panel_event(request: web.Request) -> web.Response:
    """Input events from the panel page, logged the way the firmware would."""
    get_panel(request).chip("input", (await request.json()).get("event", "?"))
    return web.json_response({"ok": True})


async def select_speaker(request: web.Request) -> web.Response:
    """The knob's device menu: make one of the panel's speakers the active one."""
    panel = get_panel(request)
    body = await request.json()
    speaker_id, knob = body["speaker"], int(body.get("knob", 0))
    link = (panel.master if panel.has_master() else None) if speaker_id == MASTER_ID else panel.links.get(speaker_id)
    if link is None or not 0 <= knob < len(panel.conf["knobs"]):
        raise web.HTTPNotFound(text="no such device or knob on this panel")
    request.app["store"].set_active(panel.id, speaker_id, knob)
    panel.chip("nvs", f"knob {knob + 1} now controls \"{link.entry['room']}\" ({link.entry['driver']})")
    return web.json_response({"ok": True})


async def set_knobs(request: web.Request) -> web.Response:
    """Hardware configuration of the simulated panel: 1-3 knobs plus one screen."""
    panel = get_panel(request)
    count = int((await request.json())["count"])
    request.app["store"].set_knob_count(panel.id, count)
    n = len(panel.conf["knobs"])
    panel.chip("hw", f"{n} knob(s) + screen ({n + 1}-gang plate)")
    return web.json_response({"ok": True, "knobs": n})


# ---- Lock, and unlocking with an iPhone (NFC tap + Face ID) ----
#
# At setup the panel gives the iPhone a secret key (over Bluetooth in the
# product; in the setup response here). A locked panel unlocks when the
# phone sends HMAC-SHA256(key, "<panel>|<ts>|<nonce>") with a fresh
# timestamp and a nonce it hasn't used, so a copied NFC tag or a replayed
# message does nothing. The tag itself only holds a URL that opens the app.

UNLOCK_WINDOW_S = 60
_used_nonces: dict = {}


def take_passcode(app: web.Application, panel: "Panel", body: dict) -> None:
    """Setup may include the panel's 4-digit unlock code."""
    code = str(body.get("passcode") or "")
    if len(code) == 4 and code.isdigit():
        app["store"].set_passcode(panel.id, code)
        panel.chip("nvs", "saved the panel's unlock code (hashed)")


CODE_TRIES, CODE_LOCKOUT_S = 5, 30
_code_failures: dict = {}   # panel id -> (failures, locked out until)


async def set_code(request: web.Request) -> web.Response:
    """The panel's own SET CODE screen (first lock). Allowed only while the
    panel is unlocked, so a locked panel's code can't be replaced."""
    panel = get_panel(request)
    code = str((await request.json()).get("code", ""))
    if panel.conf.get("locked"):
        return web.json_response({"ok": False, "error": "unlock first"}, status=403)
    if len(code) != 4 or not code.isdigit():
        return web.json_response({"ok": False, "error": "4 digits"}, status=400)
    request.app["store"].set_passcode(panel.id, code)
    panel.chip("nvs", "unlock code set on the panel (hashed)")
    return web.json_response({"ok": True})


async def unlock_code(request: web.Request) -> web.Response:
    """Unlock with the 4-digit code entered on the panel (knob or touch)."""
    panel = get_panel(request)
    store = request.app["store"]
    code = str((await request.json()).get("code", ""))
    fails, until = _code_failures.get(panel.id, (0, 0.0))
    if time.time() < until:
        wait = int(until - time.time()) + 1
        return web.json_response({"ok": False, "error": "locked out", "wait": wait}, status=429)
    if not panel.conf.get("passcode"):
        return web.json_response({"ok": False, "error": "no code set"}, status=403)
    if store.check_passcode(panel.id, code):
        _code_failures.pop(panel.id, None)
        store.set_locked(panel.id, False)
        panel.chip("lock", "unlock code accepted: unlocked")
        return web.json_response({"ok": True})
    fails += 1
    until = time.time() + CODE_LOCKOUT_S if fails >= CODE_TRIES else 0.0
    _code_failures[panel.id] = (0 if until else fails, until)
    panel.chip("lock", f"wrong unlock code ({fails} of {CODE_TRIES})" + (f"; locked out for {CODE_LOCKOUT_S} s" if until else ""), level="W")
    return web.json_response({"ok": False, "error": "wrong code", "wait": CODE_LOCKOUT_S if until else 0}, status=403)


def phone_key(app: web.Application, panel: "Panel") -> str:
    key = app["store"].unlock_key(panel.id)
    panel.chip("ble", "sent this panel's unlock key to the iPhone (kept in its Keychain)", sim=True)
    return key


async def set_lock(request: web.Request) -> web.Response:
    """The knob hold: lock or unlock at the panel itself."""
    panel = get_panel(request)
    locked = bool((await request.json())["locked"])
    request.app["store"].set_locked(panel.id, locked)
    panel.chip("lock", "locked (knob held)" if locked else "unlocked (knob held)")
    return web.json_response({"ok": True, "locked": locked})


async def set_screen(request: web.Request) -> web.Response:
    """Settings → Brightness / Dim Brightness on the panel (the backlight PWM on the chip)."""
    panel = get_panel(request)
    body = await request.json()
    screen = request.app["store"].set_screen(panel.id, body.get("brightness"), body.get("dim"))
    panel.chip("lcd", f"backlight {screen['brightness']} % awake, {screen['dim']} % dimmed")
    return web.json_response({"ok": True, "screen": screen})


async def set_auto_update(request: web.Request) -> web.Response:
    """Settings → Auto Update. The chip would check the firmware repo's signed
    releases daily and install over the air (esp_https_ota); simulated here."""
    panel = get_panel(request)
    on = bool((await request.json()).get("on"))
    request.app["store"].set_auto_update(panel.id, on)
    panel.chip("ota", "auto update on: checks the firmware releases daily, installs at night" if on
               else "auto update off: new firmware only when installed from the app", sim=True)
    return web.json_response({"ok": True, "auto_update": on})


async def unlock(request: web.Request) -> web.Response:
    panel = get_panel(request)
    store = request.app["store"]
    body = await request.json()
    panel.chip("nfc", "iPhone read the unlock tag; app opened, Face ID passed", sim=True)
    key = panel.conf.get("unlock_key")
    ts, nonce, sig = int(body.get("ts", 0)), str(body.get("nonce", "")), str(body.get("sig", ""))
    reason = None
    if not key:
        reason = "this panel has no paired iPhone (set it up again from the iPhone)"
    elif abs(time.time() - ts) > UNLOCK_WINDOW_S:
        reason = "the unlock message is too old"
    elif not nonce or nonce in _used_nonces:
        reason = "the unlock message was already used"
    else:
        expected = hmac.new(bytes.fromhex(key), f"{panel.id}|{ts}|{nonce}".encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, sig):
            reason = "the signature doesn't match (wrong iPhone or key)"
    if reason:
        panel.chip("lock", f"unlock refused: {reason}", level="W")
        return web.json_response({"ok": False, "error": reason[0].upper() + reason[1:] + "."}, status=403)
    now = time.time()
    for n, t in list(_used_nonces.items()):
        if now - t > UNLOCK_WINDOW_S * 2:
            del _used_nonces[n]
    _used_nonces[nonce] = now
    store.set_locked(panel.id, False)
    panel.chip("lock", "signed unlock verified (HMAC-SHA256, fresh, unused): unlocked")
    return web.json_response({"ok": True})


async def reset_panel(request: web.Request) -> web.Response:
    panel = get_panel(request)
    await panel.release()
    request.app["store"].reset_panel(panel.id)
    panel.chip("nvs", "factory reset: erased this panel's Wi-Fi and settings (the home's speakers stay on other panels)")
    panel.chip.reboot()
    panel.boot_log()
    return web.json_response({"ok": True})


async def panel_log(request: web.Request) -> web.Response:
    return web.json_response(get_panel(request).chip.since(int(request.query.get("since", 0))))


async def start_over(request: web.Request) -> web.Response:
    """Forget everything, like a brand-new user."""
    app = request.app
    for panel in app["panels"].values():
        await panel.release()
    app["store"].start_over()
    app["panels"] = {}
    await add_live_panel(app, app["store"].panels[0])
    return web.json_response({"ok": True})


# ---- setup (the phone flow) ----

async def setup_begin(request: web.Request) -> web.Response:
    chip = get_panel(request).chip
    chip("ble", "iPhone connected over Bluetooth (AccessorySetupKit)", sim=True)
    chip("prov", "received Wi-Fi network and password from the iPhone", sim=True)
    chip("wifi", f"connected, IP {lan_ip()}", sim=True)
    return web.json_response({"ok": True})


async def setup_scan(request: web.Request) -> web.Response:
    app = request.app
    panel = get_panel(request)
    chip = panel.chip
    chip("mdns", "browsing for _sonos._tcp, _airplay._tcp, _syng._tcp")
    found = await discover.scan()
    app["store"].remember_scan(found)
    on_this = {s["id"] for s in app["store"].household["speakers"]}
    result = []
    for f in found:
        chip("mdns", f"found {f['driver']} \"{f['name']}\" at {f['host']}")
        known = app["store"].household_speaker(f["id"])
        result.append({**f, "room": known["room"] if known else f["room"],
                       "brand": driver_class(f["driver"]).display()["brand"],
                       "set_up": f["id"] in on_this,   # already in the home, synced from another panel
                       "needs_password": f.get("needs_password", False) and not (known and known.get("credentials")),
                       "password_saved": bool(f.get("needs_password") and app["store"].airplay_password)})
    chip("mdns", f"{len(found)} devices found")
    return web.json_response(result)


async def setup_matter(request: web.Request) -> web.Response:
    """Add a Matter device with a pairing code from the Home app. Each outlet or
    light on it becomes its own device (a Tapo P400M gives two)."""
    app = request.app
    store, panel = app["store"], get_panel(request)
    chip = panel.chip
    body = await request.json()
    code = re.sub(r"[^0-9]", "", str(body.get("code", "")))
    name = (body.get("name") or "Matter device").strip()[:20]
    if len(code) not in (11, 21):
        return web.json_response({"ok": False, "error": "Enter the 11-digit pairing code from the Home app."}, status=400)
    if app.get("matter") is None:
        return web.json_response({"ok": False, "error": "The Matter bridge isn't running. Install it with: cd wallvol/matter && npm install"}, status=503)
    chip("matter", f"commissioning \"{name}\" with a pairing code (multi-admin, Apple Home keeps it)")
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=120), headers=matter_headers()) as s:
            async with s.post(f"{app['matter']}/commission", json={"code": code}) as r:
                data = await r.json()
                if r.status != 200:
                    raise RuntimeError(data.get("error", f"HTTP {r.status}"))
    except Exception as e:
        chip("matter", f"commissioning failed: {e}", level="E")
        msg = str(e)
        if "timeout" in msg.lower() or "discover" in msg.lower():
            msg = "Couldn't find the device. Turn on pairing mode again in the Home app (codes expire after about 15 minutes) and retry."
        return web.json_response({"ok": False, "error": msg}, status=400)
    endpoints = data["endpoints"] or [{"number": 1, "onOff": True, "level": False}]
    chip("matter", f"node {data['nodeId']} ({data.get('productName') or 'unknown'}): {len(endpoints)} controllable endpoint(s)")
    knob = max(0, min(int(body.get("knob", 0)), len(panel.conf["knobs"]) - 1))
    first = not panel.configured
    added = []
    for i, ep in enumerate(endpoints):
        label = name if len(endpoints) == 1 else f"{name} {i + 1}"
        entry = {"id": re.sub(r"[^a-z0-9]+", "-", f"{label}-{data['nodeId']}".lower()).strip("-"),
                 "name": label, "room": label, "driver": "matter-dimmer" if ep["level"] else "matter-switch",
                 "host": f"matter:{data['nodeId']}/{ep['number']}"}
        store.add_household_speaker(entry)
        added.append(entry)
        chip("matter", f"added \"{label}\" ({entry['driver']}, endpoint {ep['number']})")
    store.set_active(panel.id, added[0]["id"], knob)
    if first:
        await panel.connect_all()
    for other in app["panels"].values():
        if other is panel and first:
            continue
        if other.configured:
            for entry in added:
                await other.add(entry)
            if other is not panel:
                other.chip("sync", f"added {', '.join(e['room'] for e in added)} from {panel.id}; knobs unchanged")
    take_passcode(app, panel, body)
    return web.json_response({"ok": True, "devices": [e["room"] for e in added], "unlock_key": phone_key(app, panel)})


# Cloud accounts: devices that are reached through a company's service with
# the owner's login (HUUM sauna; Traeger grill next). The login is checked
# once here and stored only in the local settings (config.json, mode 600).
ACCOUNT_SERVICES = {"huum": ("HUUM sauna", "huum"), "traeger": ("Traeger grill", "traeger")}


async def setup_account(request: web.Request) -> web.Response:
    app = request.app
    store, panel = app["store"], get_panel(request)
    chip = panel.chip
    body = await request.json()
    service = body.get("service")
    if service not in ACCOUNT_SERVICES:
        return web.json_response({"ok": False, "error": "Unknown service"}, status=400)
    label, kind = ACCOUNT_SERVICES[service]
    username, password = (body.get("username") or "").strip(), body.get("password") or ""
    name = (body.get("name") or label).strip()[:20]
    if not username or not password:
        return web.json_response({"ok": False, "error": "Enter the email and password you use in the app."}, status=400)
    entry = {"id": re.sub(r"[^a-z0-9]+", "-", f"{name}-{service}".lower()).strip("-"), "name": name, "room": name,
             "driver": kind, "host": f"{service}:account", "username": username, "password": password}
    driver = driver_class(kind)(entry["host"], **store.driver_options(entry))
    chip(service, f"signing in to {label} as {username}")
    try:
        await driver.connect()
    except Exception as e:
        chip(service, f"sign-in failed: {e}", level="E")
        return web.json_response({"ok": False, "error": str(e)[:200]}, status=400)
    finally:
        await driver.close()
    if getattr(driver, "thing", None):          # Traeger: remember which grill on the account
        entry["thing"] = driver.thing
    knob = max(0, min(int(body.get("knob", 0)), len(panel.conf["knobs"]) - 1))
    first = not panel.configured
    store.add_household_speaker(entry)
    store.set_active(panel.id, entry["id"], knob)
    chip(service, f"signed in; added \"{name}\" (login saved locally)")
    if first:
        await panel.connect_all()
    for other in app["panels"].values():
        if other.configured and not (other is panel and first):
            await other.add(entry)
            if other is not panel:
                other.chip("sync", f"added \"{name}\" from {panel.id}; knobs unchanged")
    take_passcode(app, panel, body)
    return web.json_response({"ok": True, "devices": [name], "unlock_key": phone_key(app, panel)})


async def setup_finish(request: web.Request) -> web.Response:
    app = request.app
    store = app["store"]
    panel = get_panel(request)
    chip = panel.chip
    body = await request.json()
    scanned = store.scanned(body["speaker"])
    if scanned is None:
        return web.json_response({"ok": False, "error": "Unknown speaker. Scan again."}, status=404)
    known = store.household_speaker(scanned["id"])
    entry = dict(known) if known else {k: v for k, v in scanned.items() if k != "needs_password"}
    entry["host"] = scanned["host"]
    typed = body.get("password") or None
    password = typed or store.airplay_password
    if scanned.get("needs_password") and not entry.get("credentials"):
        if not password:
            return web.json_response({"ok": False, "error": "Enter the AirPlay password.", "need_password": True}, status=400)
        source = "the password you entered" if typed else "the home's saved AirPlay password"
        chip("pair", f"pairing with {entry['name']} using {source} (HAP pair-setup M1-M6)")
        try:
            creds = await pair_homepod(entry["host"], password)
        except PairingError as e:
            chip("pair", str(e), level="E")
            # A saved password that no longer works: ask for it again
            return web.json_response({"ok": False, "error": str(e), "need_password": not typed}, status=400)
        except OSError as e:
            chip("pair", f"could not reach the HomePod: {e}", level="E")
            return web.json_response({"ok": False, "error": f"Could not reach the HomePod: {e}"}, status=502)
        entry["credentials"] = store.save_credentials(entry["id"], creds)
        entry["password"] = password
        if typed:
            store.remember_airplay_password(typed)
            chip("nvs", "saved the home's AirPlay password for other HomePods")
        chip("pair", "paired; long-term keys saved to flash")
    entry["room"] = (body.get("room") or entry["room"]).strip()[:24]
    is_new = store.add_household_speaker(entry)
    first = not panel.configured
    knob = max(0, min(int(body.get("knob", 0)), len(panel.conf["knobs"]) - 1))
    store.set_active(panel.id, entry["id"], knob)
    chip("nvs", f"knob {knob + 1} now controls \"{entry['room']}\" ({entry['driver']})")
    if first:
        await panel.connect_all()      # joined Wi-Fi: connect to every speaker in the home
    else:
        await panel.add(entry)
    # Sync: every other set-up panel learns about the new speaker; their own
    # active speaker doesn't change
    for other in app["panels"].values():
        if other is panel or not other.configured:
            continue
        await other.add(entry)
        other.chip("sync", f"{'added' if is_new else 'updated'} \"{entry['room']}\" from {panel.id}; knobs unchanged")
    take_passcode(app, panel, body)
    return web.json_response({"ok": True, "unlock_key": phone_key(app, panel)})


def page(name: str):
    async def handler(request: web.Request) -> web.Response:
        html = (WEB / name).read_text()
        app = request.app
        # The API token goes only into pages loaded from this computer, or by a
        # phone that came through the setup QR link (which carries ?t=)
        if is_local(request, app["own"]) or hmac.compare_digest(request.query.get("t", ""), app["token"]):
            html = html.replace("<head>", f'<head>\n<meta name="wallvol-token" content="{app["token"]}">', 1)
        # No caching: a reload must always show the latest demo
        return web.Response(text=html, content_type="text/html",
                            headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})
    return handler


async def api_js(request: web.Request) -> web.FileResponse:
    """The pages' shared fetch wrapper (adds the token; not under /api/, so no token needed)."""
    return web.FileResponse(WEB / "api.js", headers={"Cache-Control": "no-store"})


async def start_matter_bridge(app: web.Application) -> None:
    """Start the local Matter controller (Node + matter.js) if it's installed."""
    folder = Path(__file__).parent / "matter"
    node = shutil.which("node")
    app["matter"] = None
    if not node or not (folder / "node_modules").is_dir():
        log.info("Matter bridge not installed (cd wallvol/matter && npm install); Matter devices unavailable")
        return
    port = os.environ.get("WALLVOL_MATTER_PORT", "5541")
    # A fresh secret per launch: the bridge only answers requests that carry it
    os.environ["WALLVOL_MATTER_SECRET"] = secrets.token_urlsafe(24)
    env = {**os.environ, "WALLVOL_MATTER_STORAGE": str(app["store"].home / "matter"), "WALLVOL_MATTER_PORT": port}
    app["matter_proc"] = await asyncio.create_subprocess_exec(
        node, str(folder / "bridge.mjs"), env=env,
        stdin=asyncio.subprocess.PIPE,   # the bridge exits when this closes, even if we're killed
        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
    app["matter"] = f"http://127.0.0.1:{port}"
    for _ in range(150):   # wait until it answers (first start creates the fabric)
        try:
            async with aiohttp.ClientSession(headers=matter_headers()) as s, s.get(f"{app['matter']}/nodes") as r:
                if r.status == 200:
                    log.info("Matter bridge running on %s", app["matter"])
                    return
        except aiohttp.ClientError:
            pass
        await asyncio.sleep(0.2)
    log.warning("Matter bridge didn't start")


async def on_startup(app: web.Application) -> None:
    await start_matter_bridge(app)
    for panel_conf in app["store"].panels:
        await add_live_panel(app, panel_conf)


async def on_cleanup(app: web.Application) -> None:
    for panel in app["panels"].values():
        await panel.release()
    proc = app.get("matter_proc")
    if proc and proc.returncode is None:
        proc.terminate()


def make_app(store, setup_url: str, port: int = 8080, lan: Optional[str] = None,
             token: Optional[str] = None, host: Optional[str] = None) -> web.Application:
    """lan: this computer's network address with --lan; host: the --host it's
    reached by, if that's a specific address (both are allowed host names)."""
    token = token or secrets.token_urlsafe(24)
    own = {a for a in (lan, host) if a and a not in ("0.0.0.0", "::", "127.0.0.1", "localhost", "::1")}
    app = web.Application(middlewares=[security_middleware(allowed_hosts(port, own), token)])
    app["store"] = store
    app["panels"] = {}
    app["setup_url"] = setup_url
    app["token"], app["own"] = token, own
    # For curl and scripts on this computer (credentials/ is private and gitignored)
    folder = store.home / "credentials"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "api-token").write_text(token + "\n")
    os.chmod(folder / "api-token", 0o600)
    r = app.router
    r.add_get("/", page("index.html"))
    r.add_get("/setup", page("setup.html"))
    r.add_get("/unlock", page("unlock.html"))
    r.add_get("/api.js", api_js)
    r.add_get("/api/panels", list_panels)
    r.add_post("/api/panels", create_panel)
    r.add_post("/api/start-over", start_over)
    r.add_post("/api/units", set_units)
    r.add_post("/api/devices/{did}/rename", rename_device)
    r.add_get("/api/panels/{pid}", panel_state)
    r.add_delete("/api/panels/{pid}", delete_panel)
    r.add_post("/api/panels/{pid}/volume", set_volume)
    r.add_post("/api/panels/{pid}/event", panel_event)
    r.add_post("/api/panels/{pid}/reset", reset_panel)
    r.add_post("/api/panels/{pid}/select", select_speaker)
    r.add_post("/api/panels/{pid}/knobs", set_knobs)
    r.add_post("/api/panels/{pid}/lock", set_lock)
    r.add_post("/api/panels/{pid}/screen", set_screen)
    r.add_post("/api/panels/{pid}/auto-update", set_auto_update)
    r.add_post("/api/panels/{pid}/unlock", unlock)
    r.add_post("/api/panels/{pid}/unlock-code", unlock_code)
    r.add_post("/api/panels/{pid}/set-code", set_code)
    r.add_get("/api/panels/{pid}/log", panel_log)
    r.add_post("/api/panels/{pid}/setup/begin", setup_begin)
    r.add_get("/api/panels/{pid}/setup/scan", setup_scan)
    r.add_post("/api/panels/{pid}/setup/finish", setup_finish)
    r.add_post("/api/panels/{pid}/setup/matter", setup_matter)
    r.add_post("/api/panels/{pid}/setup/account", setup_account)
    # In a clone of the repo, also serve the hardware folder (3D viewer and models)
    hardware = WEB.parent.parent / "hardware"
    if hardware.is_dir():
        r.add_static("/hardware", hardware)
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)
    return app


def serve(store, host: str, port: int, lan: bool) -> None:
    bind = "0.0.0.0" if lan else host
    shown = lan_ip() if lan else host
    setup_url = f"http://{shown}:{port}/setup"
    logging.getLogger("aiohttp.access").setLevel(logging.WARNING)
    print(f"Panels: http://{shown}:{port}/")
    print(f"Setup:  {setup_url}" + ("" if lan else "   (add --lan to open it from your phone)"))
    web.run_app(make_app(store, setup_url, port, shown if lan else None, host=host),
                host=bind, port=port, print=None)
