import math
from dataclasses import dataclass

from core.base_module import BaseModule


@dataclass
class HudState:
    x: float = 0.0
    y: float = 0.0
    depth: float = 0.0
    alt: float = 5.2
    yaw_deg: float = 0.0


class SimulatedSensorProvider:
    """Reports the vehicle state; motion is applied by the simulated thrusters."""

    def __init__(self, config):
        sim = config.get("sim", {})
        self._seabed = sim.get("seabed_depth_m", 5.2)
        self.state = HudState(
            yaw_deg=sim.get("start_yaw_deg", 45.0),
            alt=self._seabed,
        )

    def get_state(self):
        return self.state

    def apply_motion(self, surge, sway, heave, yaw_rate, dt):
        rad = math.radians(self.state.yaw_deg)
        self.state.x += (surge * math.sin(rad) + sway * math.cos(rad)) * dt
        self.state.y += (surge * math.cos(rad) - sway * math.sin(rad)) * dt
        self.state.depth -= heave * dt
        self.state.alt = max(0.0, self._seabed - self.state.depth)
        self.state.yaw_deg = (self.state.yaw_deg + yaw_rate * dt) % 360.0


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

    def apply_motion(self, surge=0.0, sway=0.0, heave=0.0, yaw_rate=0.0, dt=0.1):
        if self.provider is not None:
            self.provider.apply_motion(surge, sway, heave, yaw_rate, dt)

    def health_check(self):
        return self.provider is not None
