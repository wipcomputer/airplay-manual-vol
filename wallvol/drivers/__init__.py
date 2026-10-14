"""Speaker drivers, one per brand. To add a brand, see CONTRIBUTING.md."""

from .base import Driver


def driver_class(kind: str) -> type[Driver]:
    # Imported lazily so a missing optional dependency only breaks its own brand
    if kind == "sonos":
        from .sonos import SonosDriver
        return SonosDriver
    if kind == "homepod":
        from .homepod import HomePodDriver
        return HomePodDriver
    if kind == "syng":
        from .syng import SyngDriver
        return SyngDriver
    if kind == "huum":
        from .huum import HuumDriver
        return HuumDriver
    if kind == "traeger":
        from .traeger import TraegerDriver
        return TraegerDriver
    if kind in ("matter-switch", "matter-dimmer"):
        from .matter import MatterDimmerDriver, MatterSwitchDriver
        return MatterSwitchDriver if kind == "matter-switch" else MatterDimmerDriver
    if kind.startswith("sim-"):
        from . import sim
        for cls in (sim.SimLightDriver, sim.SimDimmerDriver, sim.SimSaunaDriver, sim.SimGrillDriver, sim.SimSpeakerDriver):
            if cls.kind == kind:
                return cls
    raise ValueError(f"unknown driver {kind!r}")
