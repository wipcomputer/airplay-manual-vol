"""The interface every device driver implements (speakers, lights, sauna...).

Each knob on a panel controls one device at a time. The panel (firmware, or
the web prototype) only ever talks to this interface, so supporting a new
brand means writing one new driver and nothing else. The ESP32 firmware mirrors this interface in C.

Levels are always 0-100 at this boundary. Drivers convert to whatever the
device uses (Sonos 0-100 ints, HomePod 0-100 floats, Syng 0.0-1.0, a
thermostat's degrees, a plug's on/off). The class attributes below tell the
panel how to show the level: as a percentage, a temperature, or on/off.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional


class Driver(ABC):
    #: Name used in config.json's "driver" field.
    kind: str = ""
    #: Brand shown on the panel and in setup
    brand: str = ""
    #: How the panel shows and steps this device's 0-100 level:
    #: "level"       a percentage (speakers, dimmers)
    #: "temperature" a target temperature from display_min to display_max (unit)
    #: "switch"      on/off only: 0 = off, anything above = on
    control: str = "level"
    #: True for speakers: they take part in the panel's Master Volume
    audio: bool = False
    #: True for things the panel may switch on and off with a long press on the
    #: screen's start/stop button (a sauna). Level 0 = off; the knob sets the
    #: target without starting it. False for a grill: the panel never starts it.
    startable: bool = False
    unit: str = "%"
    display_min: float = 0
    display_max: float = 100

    @classmethod
    def display(cls) -> dict:
        return {"control": cls.control, "unit": cls.unit, "min": cls.display_min,
                "max": cls.display_max, "brand": cls.brand or cls.kind.title(),
                "startable": cls.startable}

    def __init__(self, host: str, **options: Any) -> None:
        self.host = host
        self.options = options

    @abstractmethod
    async def connect(self) -> None:
        """Open (or reopen) the connection to the speaker.

        Called once at startup and again after a failure. Should be safe to call
        when already connected.
        """

    @abstractmethod
    async def get_volume(self) -> Optional[float]:
        """Return the speaker's current volume (0-100), or None if unknown.

        This must be the real level on the speaker, including changes made
        elsewhere (the phone's AirPlay slider, the speaker's own buttons), so the
        panel can show the true level when it wakes.
        """

    @abstractmethod
    async def set_volume(self, level: float) -> None:
        """Set the speaker's own volume (0-100).

        Must change only this speaker, never the whole AirPlay group, and must
        work while any device is AirPlaying to it.
        """

    async def get_reading(self) -> Optional[dict]:
        """Optional live reading shown under the level, for devices whose level is
        a target: {"now": 165} (current temperature, in the display unit), plus
        {"probe": 140} for a food probe, or {"text": "OFFLINE"}. None = nothing."""
        return None

    async def close(self) -> None:
        """Release the connection. Optional."""
