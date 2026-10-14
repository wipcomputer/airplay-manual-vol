"""Find supported speakers on the local network.

Finds Sonos players (SoCo), HomePods (pyatv) and Syng Cells (the _syng._tcp mDNS
service; only the primary of a stereo pair is listed, since it controls both).
"""

import asyncio
import re
import time

import pyatv
import soco
from zeroconf import ServiceBrowser, ServiceListener, Zeroconf


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _entry(name: str, driver: str, host: str, **extra) -> dict:
    return {"id": slug(name), "name": name, "room": name, "driver": driver, "host": host, **extra}


def find_sonos() -> list:
    return [_entry(z.player_name, "sonos", z.ip_address) for z in soco.discover(timeout=5) or []]


def find_syng(timeout: float = 4) -> list:
    names = set()

    class Listener(ServiceListener):
        # Only collect names here: zeroconf can't resolve from inside its callbacks
        def add_service(self, zc, type_, name):
            names.add(name)

        def update_service(self, zc, type_, name):
            names.add(name)

        def remove_service(self, zc, type_, name):
            pass

    zc = Zeroconf()
    try:
        ServiceBrowser(zc, "_syng._tcp.local.", Listener())
        time.sleep(timeout)
        found = []
        for name in sorted(names):
            info = zc.get_service_info("_syng._tcp.local.", name, timeout=3000)
            if not info or not info.parsed_addresses():
                continue
            props = {k.decode(): (v or b"").decode() for k, v in info.properties.items()}
            if props.get("role", "primary") != "primary":
                continue  # the secondary of a pair follows the primary
            found.append(_entry(name.split(".")[0], "syng", info.parsed_addresses()[0]))
        return found
    finally:
        zc.close()


async def scan(include_simulated: bool = True) -> list:
    """Return every supported device found, as config entries. Simulated
    devices (lights, sauna, grill) are listed last so the demo can show a
    whole-house panel without that hardware."""
    sonos, syng, airplay = await asyncio.gather(
        asyncio.to_thread(find_sonos),
        asyncio.to_thread(find_syng),
        pyatv.scan(asyncio.get_running_loop(), timeout=5),
    )
    homepods = []
    names = {}
    for conf in airplay:
        names[str(conf.address)] = conf.name
        if "HomePod" not in str(conf.device_info.model):
            continue
        service = conf.get_service(pyatv.const.Protocol.AirPlay)
        homepods.append(_entry(conf.name, "homepod", str(conf.address),
                               needs_password=bool(service and service.requires_password)))
    # Syng Cells only advertise a serial; use the AirPlay name of the same address
    for e in syng:
        if e["host"] in names:
            e.update(_entry(names[e["host"]], "syng", e["host"]))
    real = sorted(homepods + sonos + syng, key=lambda e: e["name"].lower())
    if not include_simulated:
        return real
    from .drivers.sim import DEVICES
    return real + [_entry(name, kind, host, simulated=True) for name, kind, host in DEVICES]


def main(store) -> None:
    print("Scanning for Sonos, HomePod and Syng speakers (about 10 seconds)...")
    found = asyncio.run(scan())
    store.remember_scan(found)
    for s in found:
        note = "  (AirPlay password set)" if s.get("needs_password") else ""
        print(f"  {s['driver']:8} {s['host']:16} {s['name']}{note}")
    print(f"Saved to {store.config_path}. Set panels up from the web page.")
