"""wallvol command line.

  wallvol                 start the panel prototype (same as `wallvol serve`)
  wallvol serve [--lan]   --lan also serves it to phones on your network
  wallvol discover        scan for speakers and save them
  wallvol reset           start over as a new user: forget panels, speakers, passwords, keys
"""

import argparse
import logging

from . import discover
from .server import serve
from .store import Store, find_home


def main() -> None:
    parser = argparse.ArgumentParser(prog="wallvol", description="Wall volume panel prototype",
                                     formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    parser.add_argument("command", nargs="?", default="serve", choices=["serve", "discover", "reset"])
    parser.add_argument("--home", help="settings folder (default: ./ if it has config.json, else ~/.wallvol)")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--lan", action="store_true", help="listen on your network so a phone can open the setup page")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")

    store = Store(find_home(args.home))
    if args.command == "discover":
        discover.main(store)
    elif args.command == "reset":
        erased = store.start_over()
        print(f"Start over: forgot all panels, speakers and passwords, erased {erased} pairing key(s).")
        print("Start it with `wallvol` to set it up like new.")
    else:
        serve(store, args.host, args.port, args.lan)


if __name__ == "__main__":
    main()
