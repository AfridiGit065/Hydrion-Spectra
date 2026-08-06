import math
import time
from dataclasses import dataclass

from core.base_module import BaseModule


@dataclass
class HudState:
    x: float = 0.0
    y: float = 0.0
    depth: float = 0.0
    yaw_deg: float = 0.0


class SimulatedSensorProvider:
    """Scripted IMU/depth/compass values; swap for a real driver later."""

    def __init__(self, config):
        sim = config.get("sim", {})
        self.speed = sim.get("speed_mps", 0.6)
        self.turn_rate = sim.get("turn_rate_degps", 20.0)
        self.depth_rate = sim.get("depth_rate_mps", 0.05)
        self.state = HudState(yaw_deg=sim.get("start_yaw_deg", 45.0))
        self._last = None

    def get_state(self):
        now = time.monotonic()
        if self._last is None:
            self._last = now
            return self.state

        dt = min(now - self._last, 0.25)
        self._last = now

        self.state.yaw_deg += self.turn_rate * math.sin(now * 0.15) * dt
        self.state.yaw_deg %= 360.0
        rad = math.radians(self.state.yaw_deg)
        self.state.x += self.speed * math.sin(rad) * dt
        self.state.y += self.speed * math.cos(rad) * dt
        self.state.depth += self.depth_rate * math.sin(now * 0.1) * dt
        return self.state


class SensorManager(BaseModule):
    """Reads IMU/depth/compass through a swappable provider, exposes a HudState."""

    def __init__(self, config=None):
        super().__init__("Sensors")
        self.config = config or {}
        self.provider = None

    def initialize(self):
        super().initialize()
        name = self.config.get("provider", "simulated")
        providers = {"simulated": SimulatedSensorProvider}
        provider_cls = providers.get(name)
        if provider_cls is None:
            self.logger.warning("Unknown sensor provider '%s'; using simulated", name)
            provider_cls = SimulatedSensorProvider
        self.provider = provider_cls(self.config)
        self.logger.info("Sensor provider: %s", name)
        return True

    def get_state(self):
        if self.provider is None:
            return HudState()
        return self.provider.get_state()

    def health_check(self):
        return self.provider is not None
