"""Where wallvol keeps its settings: config.json and HomePod pairing keys.

Settings are split the way a home with several panels needs them:

- household: shared by every panel and synced between them. The devices that
  have been set up (name, address, and a HomePod's pairing key or a cloud
  login), the home's AirPlay password (one setting for the whole Apple Home, so
  asked for only once) and °F / °C.
- panels: each panel's own settings: its knobs (1 to 3, for a 2-, 3- or
  4-gang plate with one screen), each with its own active device. A knob's
  device starts as the one it was set up with and changes when someone picks
  another from that knob's device menu. Adding a device on one panel never
  changes another panel's knobs. Also its lock, code, brightness and Auto
  Update.
- speakers: the last network scan (no secrets).

The home folder is, in order: --home, $WALLVOL_HOME, the current folder if it
has a config.json (running from a clone of the repo), or ~/.wallvol.
"""

import hashlib
import json
import os
import secrets
from pathlib import Path
from typing import Optional


def find_home(explicit: Optional[str] = None) -> Path:
    if explicit:
        return Path(explicit).expanduser()
    if os.environ.get("WALLVOL_HOME"):
        return Path(os.environ["WALLVOL_HOME"]).expanduser()
    if Path("config.json").exists():
        return Path.cwd()
    return Path.home() / ".wallvol"


class Store:
    def __init__(self, home: Path) -> None:
        self.home = home
        self.config_path = home / "config.json"
        self.credentials_dir = home / "credentials"
        data = json.loads(self.config_path.read_text()) if self.config_path.exists() else {}
        self.speakers: list = data.get("speakers", [])
        self.household: dict = data.get("household", {})
        self.household.setdefault("speakers", [])
        self.panels: list = [self._upgrade(p) for p in data.get("panels") or [{"id": "panel-1"}]]
        self._migrate_old(data)

    def _upgrade(self, panel: dict) -> dict:
        # Older layouts kept speakers on each panel; move them to the household
        for entry in ([panel.pop("speaker")] if panel.get("speaker") else []) + panel.pop("speakers", []):
            if not self.household_speaker(entry["id"]):
                self.household["speakers"].append(entry)
            if entry.get("password"):
                self.household.setdefault("airplay_password", entry["password"])
            if not panel.get("active") and "knobs" not in panel:
                panel["active"] = entry["id"]
        panel.pop("speaker", None)
        # Panels had a single "active"; now one per knob
        if "knobs" not in panel:
            panel["knobs"] = [{"active": panel.pop("active", None)}]
        panel.pop("active", None)
        return panel

    def _migrate_old(self, data: dict) -> None:
        # The first layout had one "panel" pointing into "speakers"
        old = (data.get("panel") or {}).get("speaker")
        entry = next((dict(s) for s in self.speakers if s["id"] == old), None)
        if entry and not self.household_speaker(entry["id"]):
            self.household["speakers"].append(entry)
            self.panels[0]["knobs"][0]["active"] = entry["id"]
        for s in self.speakers:
            s.pop("password", None)
            s.pop("credentials", None)

    def save(self) -> None:
        self.home.mkdir(parents=True, exist_ok=True)
        tmp = self.config_path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"household": self.household, "panels": self.panels,
                                   "speakers": self.speakers}, indent=2) + "\n")
        os.chmod(tmp, 0o600)  # holds the AirPlay password
        tmp.replace(self.config_path)

    # ---- household (synced to every panel) ----

    def household_speaker(self, speaker_id: str) -> Optional[dict]:
        return next((s for s in self.household["speakers"] if s["id"] == speaker_id), None)

    def add_household_speaker(self, entry: dict) -> bool:
        """Add or update a set-up speaker. Returns True if it's new to the home."""
        new = self.household_speaker(entry["id"]) is None
        self.household["speakers"] = [s for s in self.household["speakers"] if s["id"] != entry["id"]] + [entry]
        self.save()
        return new

    @property
    def units(self) -> str:
        """°F or °C for every temperature shown on the panels in this home."""
        return self.household.get("units", "F")

    def set_units(self, units: str) -> None:
        self.household["units"] = "C" if units.upper().startswith("C") else "F"
        self.save()

    def rename(self, device_id: str, name: str) -> Optional[dict]:
        entry = self.household_speaker(device_id)
        if entry:
            entry["name"] = entry["room"] = name
            self.save()
        return entry

    @property
    def airplay_password(self) -> Optional[str]:
        return self.household.get("airplay_password")

    def remember_airplay_password(self, password: str) -> None:
        self.household["airplay_password"] = password
        self.save()

    # ---- panels (each one's own settings) ----

    def panel(self, panel_id: str) -> Optional[dict]:
        return next((p for p in self.panels if p["id"] == panel_id), None)

    def add_panel(self) -> dict:
        n = 1
        while self.panel(f"panel-{n}"):
            n += 1
        panel = {"id": f"panel-{n}", "knobs": [{"active": None}]}
        self.panels.append(panel)
        self.save()
        return panel

    def remove_panel(self, panel_id: str) -> None:
        self.panels = [p for p in self.panels if p["id"] != panel_id]
        self.save()

    def reset_panel(self, panel_id: str) -> None:
        """Factory reset one panel: it forgets its own settings and goes back to
        setup. The household's devices stay, since other panels still use them."""
        panel = self.panel(panel_id)
        for knob in panel["knobs"]:
            knob["active"] = None
        panel.pop("unlock_key", None)    # the iPhone has to be paired again
        panel.pop("passcode", None)
        panel.pop("locked", None)
        self.save()

    def unlock_key(self, panel_id: str) -> str:
        """The panel's secret for signed unlocks (NFC tap + Face ID on the
        iPhone). Created at setup and handed to the iPhone once."""
        panel = self.panel(panel_id)
        if not panel.get("unlock_key"):
            panel["unlock_key"] = secrets.token_hex(32)
            self.save()
        return panel["unlock_key"]

    def set_passcode(self, panel_id: str, code: str) -> None:
        """The panel's 4-digit unlock code, kept only as a salted hash."""
        salt = secrets.token_hex(8)
        self.panel(panel_id)["passcode"] = {"salt": salt, "hash": hashlib.sha256(f"{salt}:{code}".encode()).hexdigest()}
        self.save()

    def check_passcode(self, panel_id: str, code: str) -> bool:
        p = self.panel(panel_id).get("passcode")
        if not p:
            return False
        return secrets.compare_digest(p["hash"], hashlib.sha256(f"{p['salt']}:{code}".encode()).hexdigest())

    def set_locked(self, panel_id: str, locked: bool) -> None:
        self.panel(panel_id)["locked"] = locked
        self.save()

    def set_screen(self, panel_id: str, brightness: Optional[int] = None, dim: Optional[int] = None) -> dict:
        """Screen brightness while awake and while dimmed (asleep), in %, per panel."""
        screen = self.panel(panel_id).setdefault("screen", {"brightness": 100, "dim": 5})
        if brightness is not None:
            screen["brightness"] = max(10, min(100, int(brightness)))
        if dim is not None:
            screen["dim"] = max(0, min(100, int(dim)))
        self.save()
        return screen

    def set_auto_update(self, panel_id: str, on: bool) -> None:
        """Settings → Auto Update: install new firmware releases on their own."""
        self.panel(panel_id)["auto_update"] = bool(on)
        self.save()

    def set_active(self, panel_id: str, speaker_id: str, knob: int = 0) -> None:
        self.panel(panel_id)["knobs"][knob]["active"] = speaker_id
        self.save()

    def set_knob_count(self, panel_id: str, count: int) -> None:
        """Hardware configuration: 1-3 knobs plus one screen."""
        knobs = self.panel(panel_id)["knobs"]
        count = max(1, min(3, count))
        self.panel(panel_id)["knobs"] = (knobs + [{"active": None} for _ in range(count)])[:count]
        self.save()

    def start_over(self) -> int:
        """Forget everything, like a new install. Returns pairing keys erased."""
        erased = 0
        if self.credentials_dir.exists():
            for f in self.credentials_dir.glob("*.txt"):
                f.unlink()
                erased += 1
        self.speakers = []
        self.household = {"speakers": []}
        self.panels = [{"id": "panel-1", "knobs": [{"active": None}]}]
        self.save()
        return erased

    # ---- scan results ----

    def scanned(self, speaker_id: str) -> Optional[dict]:
        return next((s for s in self.speakers if s["id"] == speaker_id), None)

    def remember_scan(self, found: list) -> None:
        by_host = {s["host"]: s for s in self.speakers}
        for f in found:
            by_host[f["host"]] = f
        self.speakers = sorted(by_host.values(), key=lambda s: s["name"].lower())
        self.save()

    # ---- pairing keys ----

    def credentials_path(self, speaker_id: str) -> Path:
        return self.credentials_dir / f"{speaker_id}.txt"

    def save_credentials(self, speaker_id: str, credentials: str) -> str:
        self.credentials_dir.mkdir(parents=True, exist_ok=True)
        path = self.credentials_path(speaker_id)
        path.write_text(credentials)
        os.chmod(path, 0o600)
        return str(path.relative_to(self.home))

    def driver_options(self, entry: dict) -> dict:
        """Speaker entry -> driver keyword arguments (paths made absolute)."""
        opts = {k: v for k, v in entry.items()
                if k not in ("id", "name", "room", "driver", "host", "needs_password", "simulated")}
        # Cloud accounts keep their login on the entry; drivers that don't use it ignore it
        if opts.get("credentials"):
            opts["credentials"] = str(self.home / opts["credentials"])
        return opts
