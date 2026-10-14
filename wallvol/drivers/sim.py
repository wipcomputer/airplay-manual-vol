"""Simulated devices, so the demo can show one panel running a whole house
(lights, a sauna, a grill) without the real hardware.

Each simulated device keeps its level in memory, shared by every panel, so a
change from one knob shows up on any other panel controlling it. Nothing is
sent anywhere. Real drivers for these kinds of devices (Matter plugs, HUUM,
Traeger) are planned; see docs/STATUS.md.
"""

from typing import Any, Optional

from .base import Driver

import time

_LEVELS: dict = {}
_TEMPS: dict = {}     # simulated current temperature per device, for get_reading
_ENDS: dict = {}      # simulated sauna session end (epoch seconds)


class _SimDriver(Driver):
    start: float = 0

    def __init__(self, host: str, **options: Any) -> None:
        super().__init__(host, **options)
        _LEVELS.setdefault(host, self.start)

    async def connect(self) -> None:
        pass

    async def get_volume(self) -> Optional[float]:
        return _LEVELS[self.host]

    async def set_volume(self, level: float) -> None:
        _LEVELS[self.host] = level


class SimLightDriver(_SimDriver):
    kind = "sim-light"
    brand = "Simulated light"
    control = "switch"
    unit = ""


class SimSpeakerDriver(_SimDriver):
    kind = "sim-speaker"
    brand = "Simulated speaker"
    audio = True
    start = 30


class SimDimmerDriver(_SimDriver):
    kind = "sim-dimmer"
    brand = "Simulated dimmer"
    start = 60


class _SimHeater(_SimDriver):
    """Heats toward the target about 1 degree per second; cools when off."""
    ambient = 70.0

    async def get_reading(self):
        now = time.monotonic()
        temp, last = _TEMPS.get(self.host, (self.ambient, now))
        level = _LEVELS[self.host]
        goal = self.display_min + level / 100 * (self.display_max - self.display_min) if level > 0 else self.ambient
        step = min(abs(goal - temp), now - last)
        temp += step if goal > temp else -step
        _TEMPS[self.host] = (temp, now)
        return {"now": round(temp)}


class SimSaunaDriver(_SimHeater):
    kind = "sim-sauna"
    brand = "Simulated sauna"
    control = "temperature"
    unit = "°F"
    display_min, display_max = 110, 195   # HUUM-style target range
    startable = True
    session_s = 3 * 3600   # like HUUM's default session

    async def set_volume(self, level: float) -> None:
        was_on = _LEVELS[self.host] > 0
        await super().set_volume(level)
        if level > 0 and not was_on:
            _ENDS[self.host] = int(time.time()) + self.session_s
        elif level <= 0:
            _ENDS.pop(self.host, None)

    async def get_reading(self):
        reading = await super().get_reading()
        if _LEVELS[self.host] > 0 and self.host in _ENDS:
            reading["ends"] = _ENDS[self.host]
            reading["starts"] = _ENDS[self.host] - self.session_s
        return reading


class SimGrillDriver(_SimHeater):
    kind = "sim-grill"
    brand = "Simulated grill"
    control = "temperature"
    unit = "°F"
    display_min, display_max = 165, 500   # Traeger-style target range


# What setup offers when "show simulated devices" is on (host doubles as id)
# Names say "(demo)" so they can't be mistaken for the real sauna, grill or lights
DEVICES = [
    ("Sauna (demo)", "sim-sauna", "sim:sauna"),
    ("Grill (demo)", "sim-grill", "sim:grill"),
    ("Outside Light 1 (demo)", "sim-light", "sim:outside-light-1"),
    ("Outside Light 2 (demo)", "sim-light", "sim:outside-light-2"),
    ("Kitchen Dimmer (demo)", "sim-dimmer", "sim:kitchen-dimmer"),
    ("Kitchen Speaker (demo)", "sim-speaker", "sim:kitchen-speaker"),
    ("Patio Speaker (demo)", "sim-speaker", "sim:patio-speaker"),
]
