"""List or set the volume of any speaker in a HomePod-led AirPlay group.

When a HomePod is the group leader (music started on the HomePod, e.g. by Siri),
its remote-control (MRP) channel lists every grouped speaker and accepts a volume
change for each one, including non-Apple AirPlay speakers such as a Syng Cell pair.
When an iPhone is the leader, the HomePod lists no group members.

Uses the same connection path as homepod_volume.py (pairing credentials, forced
MRP tunnel, Digest login for password-protected HomePods).

Usage: homepod_group_volume.py HOST CREDS_FILE [NAME LEVEL] [--password PW]
"""

import argparse
import asyncio

import pyatv
from pyatv.const import Protocol
from pyatv.settings import MrpTunnel
from pyatv.storage.memory_storage import MemoryStorage

import homepod_volume


async def main(args):
    loop = asyncio.get_running_loop()
    confs = await pyatv.scan(loop, hosts=[args.host], timeout=5)
    if not confs:
        raise SystemExit(f"no device found at {args.host}")
    conf = confs[0]
    creds = open(args.creds_file).read().strip()
    for proto in (Protocol.AirPlay, Protocol.RAOP):
        conf.set_credentials(proto, creds)
    storage = MemoryStorage()
    settings = await storage.get_settings(conf)
    settings.protocols.airplay.mrp_tunnel = MrpTunnel.Force
    atv = await pyatv.connect(conf, loop, protocol=Protocol.AirPlay, storage=storage)
    try:
        await asyncio.sleep(3)  # let the tunnel deliver device info and volumes
        devices = atv.audio.output_devices
        if not devices:
            print("no group members: this HomePod is not the group leader")
            return
        for d in devices:
            print(f"{d.name!r:24} volume {d.volume}")
        if args.name:
            dev = next(d for d in devices if args.name.lower() in d.name.lower())
            try:
                await atv.audio.set_volume(args.level, output_device=dev)
            except asyncio.TimeoutError:
                print("no volume confirmation within 5 s")
            await asyncio.sleep(1)
            print(f"{dev.name!r} now", next(d.volume for d in atv.audio.output_devices
                                            if d.identifier == dev.identifier))
    finally:
        atv.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("host")
    parser.add_argument("creds_file")
    parser.add_argument("name", nargs="?", help="part of the speaker name to set")
    parser.add_argument("level", nargs="?", type=float, help="volume 0-100")
    parser.add_argument("--password", help="AirPlay password, if the HomePod has one")
    args = parser.parse_args()
    if args.name and args.level is None:
        parser.error("a speaker name needs a level")
    homepod_volume.PASSWORD = args.password
    asyncio.run(main(args))
