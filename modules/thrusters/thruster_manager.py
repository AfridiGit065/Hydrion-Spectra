import time

from core.base_module import BaseModule
from modules.controller.controller import MotionState


MIXING_MATRIX = {
    "FL": {"surge": 1.0, "sway": 1.0, "yaw": 1.0},
    "FR": {"surge": 1.0, "sway": -1.0, "yaw": -1.0},
    "BL": {"surge": -1.0, "sway": 1.0, "yaw": -1.0},
    "BR": {"surge": -1.0, "sway": -1.0, "yaw": 1.0},
    "VT1": {"heave": 1.0, "pitch": 1.0, "roll": 1.0},
    "VT2": {"heave": 1.0, "pitch": -1.0, "roll": -1.0},
}


class SimulatedThrusterProvider:
    """Converts motion setpoints into thruster commands and applies them to the simulated state."""

    def __init__(self, config=None, sensors=None):
        self.config = config or {}
        self.sensors = sensors
        self.speed_mps = self.config.get("speed_mps", 0.8)
        self.turn_rate_degps = self.config.get("turn_rate_degps", 60.0)

    def setpoints(self, motion):
        values = {}
        for name, weights in MIXING_MATRIX.items():
            value = sum(getattr(motion, axis) * weight for axis, weight in weights.items())
            values[name] = max(-1.0, min(1.0, value))
        return values

    def apply(self, motion, dt):
        if self.sensors is None:
            return
        speed = self.speed_mps * (2.0 if motion.boost else 1.0)
        self.sensors.apply_motion(
            surge=motion.surge * speed,
            sway=motion.sway * speed,
            heave=motion.heave * speed,
            yaw_rate=motion.yaw * self.turn_rate_degps,
            dt=dt,
        )


class ThrusterManager(BaseModule):
    """Splits a motion target across the thruster layout via a swappable provider."""

    def __init__(self, config=None, sensors=None):
        super().__init__("Thrusters")
        self.config = config or {}
        self.sensors = sensors
        self.provider = None
        self._motion = MotionState()
        self._last = None

    def initialize(self):
        super().initialize()
        name = self.config.get("provider", "simulated")
        providers = {"simulated": SimulatedThrusterProvider}
        provider_cls = providers.get(name)
        if provider_cls is None:
            self.logger.warning("Unknown thruster provider '%s'; using simulated", name)
            provider_cls = SimulatedThrusterProvider
        self.provider = provider_cls(self.config, sensors=self.sensors)
        self.logger.info("Thruster provider: %s", name)
        return True

    def set_motion(self, motion):
        self._motion = motion

    def update(self):
        if not self.running or self.provider is None:
            return
        now = time.monotonic()
        if self._last is None:
            self._last = now
            return
        dt = min(now - self._last, 0.25)
        self._last = now
        setpoints = self.provider.setpoints(self._motion)
        if any(abs(v) > 0.01 for v in setpoints.values()):
            self.logger.debug("Setpoints: %s", setpoints)
        self.provider.apply(self._motion, dt)

    def health_check(self):
        return self.provider is not None
