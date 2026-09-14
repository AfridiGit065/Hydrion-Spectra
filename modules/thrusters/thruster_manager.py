"""5-thruster thrust model for the Hydrion-Spectra ROV (Phase 1 + Phase 2).

Actual hardware layout (ESP32 GPIO refer to the future low-level ESC
controller; the Raspberry Pi never drives these pins — metadata only):

    M1  Front Vertical            -> ESP32 GPIO 25
    M2  Middle Right Horizontal   -> ESP32 GPIO 33
    M3  Middle Left Horizontal    -> ESP32 GPIO 32
    M4  Back Right Vertical       -> ESP32 GPIO 27
    M5  Back Left Vertical        -> ESP32 GPIO 26

Supported motion (Phase 1): surge, yaw, heave.
Sway, pitch and roll are NOT mixed into the motor output (no sway thruster;
pitch/roll stabilization is future work).

Phase 2 adds the Esp32ThrusterProvider + UART transport: the already-mixed
M1..M5 setpoints are pushed to an ESP32 ESC controller over serial (never
surge/yaw/heave). The provider stays behind the ThrusterProvider abstraction;
``configs/thrusters.yaml`` keeps ``provider: simulated`` as the default.
"""

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import IntEnum, auto

from core.base_module import BaseModule
from modules.controller.controller import MotionState
from modules.thrusters.uart_transport import (
    FLAG_ESTOP,
    MSG_ACK,
    MSG_HEARTBEAT,
    MSG_STATUS,
    UartTransport,
    build_motor_command,
)


class ThrusterId(IntEnum):
    """Stable identifiers for the five physical thrusters."""
    M1_FRONT_VERTICAL = auto()
    M2_MIDDLE_RIGHT_HORIZONTAL = auto()
    M3_MIDDLE_LEFT_HORIZONTAL = auto()
    M4_BACK_RIGHT_VERTICAL = auto()
    M5_BACK_LEFT_VERTICAL = auto()


DEFAULT_GPIO = {
    ThrusterId.M1_FRONT_VERTICAL: 25,
    ThrusterId.M2_MIDDLE_RIGHT_HORIZONTAL: 33,
    ThrusterId.M3_MIDDLE_LEFT_HORIZONTAL: 32,
    ThrusterId.M4_BACK_RIGHT_VERTICAL: 27,
    ThrusterId.M5_BACK_LEFT_VERTICAL: 26,
}

SUPPORTED_AXES = ("surge", "yaw", "heave")


def mix(motion=None, surge=0.0, yaw=0.0, heave=0.0, directions=None):
    """Pure 5-thruster mixer.

    Returns exactly five motor outputs keyed by ``ThrusterId``, each clamped
    to [-1.0, 1.0]. Only the supported axes (surge/yaw/heave) are consumed;
    sway/pitch/roll inputs can never produce a motor command.

    The optional ``directions`` mapping flips the physical sign of a motor
    (configurable per-motor, default +1) so reversed mounts are corrected at
    config time, not by guessing in code.
    """
    if motion is not None:
        surge = float(getattr(motion, "surge", surge))
        yaw = float(getattr(motion, "yaw", yaw))
        heave = float(getattr(motion, "heave", heave))
    raw = (
        (ThrusterId.M1_FRONT_VERTICAL, heave),
        (ThrusterId.M2_MIDDLE_RIGHT_HORIZONTAL, surge + yaw),
        (ThrusterId.M3_MIDDLE_LEFT_HORIZONTAL, surge - yaw),
        (ThrusterId.M4_BACK_RIGHT_VERTICAL, heave),
        (ThrusterId.M5_BACK_LEFT_VERTICAL, heave),
    )
    output = {}
    for thruster, value in raw:
        direction = (directions or {}).get(thruster, 1)
        output[thruster] = max(-1.0, min(1.0, value * direction))
    return output


@dataclass
class ThrusterConfig:
    """Per-motor hardware configuration loaded from ``configs/thrusters.yaml``.

    ``directions``: physical motor sign (+1/-1) — verified on the real ROV.
    ``gpio``: ESP32 pin the future provider will use (metadata only).
    """

    directions: dict
    gpio: dict

    @classmethod
    def from_dict(cls, data):
        data = data or {}
        directions = {}
        gpio = {}
        for thruster in ThrusterId:
            entry = data.get(thruster.name) or {}
            directions[thruster] = int(entry.get("direction", 1))
            gpio[thruster] = int(entry.get("gpio", DEFAULT_GPIO.get(thruster, 0)))
        return cls(directions=directions, gpio=gpio)


class ThrusterProvider(ABC):
    """Interface every thruster provider must match.

    SimulatedThrusterProvider runs today; Esp32ThrusterProvider takes over in
    Phase 2. ControllerModule and the UI only ever talk to ThrusterManager,
    so swapping the provider never touches them.
    """

    @abstractmethod
    def setpoints(self, motion):
        """Return {ThrusterId: float} motor commands for a MotionState."""

    @abstractmethod
    def apply(self, motion, dt, setpoints=None):
        """Apply the motion to the vehicle (simulated now, hardware later).

        ``setpoints`` carries the already-mixed 5-motor commands computed by
        ``setpoints()`` so hardware providers can transmit them directly.
        """


class SimulatedThrusterProvider(ThrusterProvider):
    """Converts motion setpoints into 5-motor commands and applies the
    supported motion axes (surge/heave/yaw) to the simulated vehicle state."""

    def __init__(self, config=None, sensors=None):
        self.config = config or {}
        self.sensors = sensors
        self.speed_mps = self.config.get("speed_mps", 0.8)
        self.turn_rate_degps = self.config.get("turn_rate_degps", 60.0)
        self.thruster_config = ThrusterConfig.from_dict(self.config.get("motors"))

    def setpoints(self, motion):
        return mix(motion, directions=self.thruster_config.directions)

    def apply(self, motion, dt, setpoints=None):
        if self.sensors is None:
            return
        speed = self.speed_mps * (2.0 if motion.boost else 1.0)
        self.sensors.apply_motion(
            surge=motion.surge * speed,
            sway=0.0,
            heave=motion.heave * speed,
            yaw_rate=motion.yaw * self.turn_rate_degps,
            dt=dt,
        )


class Esp32ThrusterProvider(ThrusterProvider):
    """Phase 2: drives an ESP32 ESC controller over UART.

    Receives the five **already-mixed** motor setpoints from ThrusterManager
    and pushes them to the ESP32 as MOTOR_COMMAND frames (M1..M5, normalized
    to [-1,1] and re-clamped before transmission — never surge/yaw/heave).
    The ESP32 replies with ACK / STATUS / HEARTBEAT frames which the provider
    parses and exposes through :meth:`status` for later telemetry; the
    existing telemetry system is not touched here.

    Safety: the provider needs no hardware. If the serial port cannot be
    opened the provider keeps running in a *disconnected* state and retries
    reconnects, so the app never crashes without an ESP32. E-STOP is re-issued
    as a zeroed framed flag so the ESP32 can enforce its own ESC halt.
    """

    def __init__(self, config=None, sensors=None, transport=None):
        self.config = config or {}
        self.sensors = sensors
        self.logger = logging.getLogger("Thrusters.Esp32")
        self.thruster_config = ThrusterConfig.from_dict(self.config.get("motors"))
        self.esp32 = self.config.get("esp32") or {}
        if transport is None:
            transport = UartTransport(self.esp32, logger=self.logger)
        self.transport = transport
        self._seq = 0
        self._estop = False
        self._last_send = 0.0
        self._last_warn = 0.0
        self._command_interval = 1.0 / max(1, float(self.esp32.get("command_rate_hz", 50)))
        self._heartbeat_timeout = (
            float(self.esp32.get("heartbeat_timeout_ms", 250)) / 1000.0
        )
        # Link / ack state surfaced via status() for later diagnostics.
        self._last_rx_at = None
        self._last_rx_info = None
        self._last_tx_seq = None
        self._last_tx_at = None
        self._ack_pending = None  # (sequence, sent_monotonic)
        self._last_ack_seq = None
        self._last_ack_latency_s = None
        self._missing_acks = 0
        self._link_stale_logged = False

    def initialize(self):
        """Best-effort open; missing hardware is not an error."""
        if self.transport is not None:
            self.transport.open()
        return self.transport is not None

    def is_connected(self):
        return self.transport is not None and self.transport.is_open()

    def setpoints(self, motion):
        return mix(motion, directions=self.thruster_config.directions)

    def apply(self, motion, dt, setpoints=None):
        """Send the already-mixed 5-motor setpoints to the ESP32."""
        self._pump()
        if self._estop:
            self._send_rate_limited([0.0] * 5, FLAG_ESTOP)
            return
        if setpoints is None:
            setpoints = self.setpoints(motion)
        values = [setpoints[thruster] for thruster in ThrusterId]
        self._send_rate_limited(values, 0)

    def notify_estop(self, active):
        """Manager e-stop hook: latch state and push an immediate stop frame."""
        self._estop = bool(active)
        self.logger.warning("ESP32 provider: ESTOP %s", "ASSERTED" if active else "CLEARED")
        self._send_immediate([0.0] * 5, FLAG_ESTOP)

    def estop_keepalive(self, dt, setpoints):
        """Called every tick while e-stopped: keep refreshing a zeroed ESTOP
        frame so the ESP32 keeps its ESCs halted."""
        self._pump()
        self._send_rate_limited([0.0] * 5, FLAG_ESTOP)

    def stop(self):
        if self.transport is not None:
            self.transport.close()

    # -- sending ----------------------------------------------------------

    def _send_rate_limited(self, values, flags):
        now = time.monotonic()
        if now - self._last_send < self._command_interval:
            return
        self._last_send = now
        self._send_immediate(values, flags)

    def _send_immediate(self, values, flags):
        if self.transport is None:
            return
        if not self.transport.is_open():
            self.transport.open()
        if not self.transport.is_open():
            self.transport.stats["dropped_frames"] += 1
            self._log_drop()
            return
        frame = build_motor_command(self._seq, values, flags=flags)
        if self.transport.send(frame):
            self._last_tx_seq = self._seq
            self._last_tx_at = time.monotonic()
            self._ack_pending = (self._seq, self._last_tx_at)
            self._seq = (self._seq + 1) & 0xFF

    def _log_drop(self):
        now = time.monotonic()
        if now - self._last_warn < 5.0:
            return
        self._last_warn = now
        error = (
            self.transport.stats.get("last_error")
            if self.transport is not None
            else "transport unavailable"
        )
        self.logger.warning("ESP32 not connected (%s); motor frames dropped", error)

    # -- receiving --------------------------------------------------------

    def _pump(self):
        if self.transport is None or not self.transport.is_open():
            return
        self.transport.pump()
        now = time.time()
        for packet in self.transport.read_packets():
            self._last_rx_at = now
            if self._link_stale_logged:
                self._link_stale_logged = False
                self.logger.info("ESP32 UART link recovered")
            self._last_rx_info = {
                "mtype": packet.mtype,
                "sequence": packet.sequence,
                "flags": packet.flags,
                "ts": now,
            }
            if packet.mtype == MSG_ACK:
                if self._ack_pending and packet.sequence == self._ack_pending[0]:
                    self._last_ack_seq = packet.sequence
                    self._last_ack_latency_s = now - self._ack_pending[1]
                else:
                    self._missing_acks += 1
            elif packet.mtype in (MSG_STATUS, MSG_HEARTBEAT):
                self.logger.debug(
                    "ESP32 %s frame (seq=%d flags=0x%02x len=%d)",
                    "status" if packet.mtype == MSG_STATUS else "heartbeat",
                    packet.sequence,
                    packet.flags,
                    packet.length,
                )
        self._check_link_stale(now)

    def _check_link_stale(self, now):
        if not self.transport.is_open() or self._last_rx_at is None:
            return
        if now - self._last_rx_at > self._heartbeat_timeout:
            if not self._link_stale_logged:
                self._link_stale_logged = True
                self.logger.warning(
                    "ESP32 UART link stale: no frame for %.0f ms"
                    % (self._heartbeat_timeout * 1000)
                )

    # -- diagnostics ------------------------------------------------------

    def status(self):
        """Expose all provider state for the future telemetry/diagnostics UI."""
        transport = self.transport
        now = time.time()
        link_alive = (
            transport is not None
            and transport.is_open()
            and self._last_rx_at is not None
            and (now - self._last_rx_at) < self._heartbeat_timeout
        )
        stats = transport.stats if transport is not None else {}
        base = dict(stats)
        base.update(
            connected=self.is_connected(),
            link_alive=bool(link_alive),
            estop=self._estop,
            last_error=stats.get("last_error"),
            last_tx_seq=self._last_tx_seq,
            last_rx_at=self._last_rx_at,
            last_rx_info=self._last_rx_info,
            last_ack_seq=self._last_ack_seq,
            last_ack_latency_s=self._last_ack_latency_s,
            missing_acks=self._missing_acks,
        )
        return base


class ThrusterManager(BaseModule):
    """Splits a motion target across the 5-thruster layout via a provider."""

    def __init__(self, config=None, sensors=None):
        super().__init__("Thrusters")
        self.config = config or {}
        self.sensors = sensors
        self.provider = None
        self.thruster_config = ThrusterConfig.from_dict(self.config.get("motors"))
        self._motion = MotionState()
        self._last = None
        self._estop = False
        self.last_setpoints = {thruster: 0.0 for thruster in ThrusterId}

    def initialize(self):
        super().initialize()
        name = self.config.get("provider", "simulated")
        providers = {
            "simulated": SimulatedThrusterProvider,
            "esp32": Esp32ThrusterProvider,
        }
        provider_cls = providers.get(name)
        if provider_cls is None:
            self.logger.warning("Unknown thruster provider '%s'; using simulated", name)
            provider_cls = SimulatedThrusterProvider
        self.provider = provider_cls(self.config, sensors=self.sensors)
        self.logger.info("Thruster provider: %s (5-motor layout)", name)
        return True

    def set_motion(self, motion):
        self._motion = motion

    def emergency_stop(self):
        """Independent software e-stop; the ESP32 provider additionally
        re-issues a zeroed ESTOP frame so the ESC controller halts."""
        self._estop = True
        self.logger.warning("EMERGENCY STOP: all thrusters zeroed")
        notify = getattr(self.provider, "notify_estop", None)
        if callable(notify):
            notify(True)

    def clear_emergency_stop(self):
        self._estop = False
        notify = getattr(self.provider, "notify_estop", None)
        if callable(notify):
            notify(False)

    def update(self):
        if not self.running or self.provider is None:
            return
        now = time.monotonic()
        if self._last is None:
            self._last = now
            return
        dt = min(now - self._last, 0.25)
        self._last = now
        if self._estop:
            self.last_setpoints = {thruster: 0.0 for thruster in ThrusterId}
            keepalive = getattr(self.provider, "estop_keepalive", None)
            if callable(keepalive):
                keepalive(dt, self.last_setpoints)
            return
        self.last_setpoints = self.provider.setpoints(self._motion)
        if any(abs(v) > 0.01 for v in self.last_setpoints.values()):
            self.logger.debug("Setpoints: %s", self.last_setpoints)
        self.provider.apply(self._motion, dt, setpoints=self.last_setpoints)

    def stop(self):
        super().stop()
        provider_stop = getattr(self.provider, "stop", None)
        if callable(provider_stop):
            provider_stop()

    def health_check(self):
        if self.provider is None:
            return False
        connected = getattr(self.provider, "is_connected", None)
        if callable(connected):
            return connected()
        return True