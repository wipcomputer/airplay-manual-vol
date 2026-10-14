"""Read or set a Sonos speaker's volume over local UPnP (works mid-AirPlay).

Usage: sonos_volume.py [HOST] [get | set N | half]
With no HOST, lists the Sonos speakers found on the network.
"""

import sys

import soco


def main(argv):
    if not argv:
        for zone in soco.discover(timeout=5) or []:
            print(zone.player_name, zone.ip_address, "vol", zone.volume)
        return

    zone = soco.SoCo(argv[0])
    action = argv[1] if len(argv) > 1 else "get"
    print("volume", zone.volume)
    if action == "set":
        zone.volume = int(argv[2])
    elif action == "half":
        zone.volume = zone.volume // 2
    if action in ("set", "half"):
        print("now", zone.volume)


if __name__ == "__main__":
    main(sys.argv[1:])
