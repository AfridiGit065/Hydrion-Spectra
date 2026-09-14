"""Tests for the Phase 2 UART transport and Esp32ThrusterProvider.

Run from the project root:

    python -m unittest tests.test_uart_transport -v
"""

import os
import struct
import sys
import unittest
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.controller.controller import MotionState
from modules.thrusters.thruster_manager import (
    DEFAULT_GPIO,
    Esp32ThrusterProvider,
    ThrusterId,
    ThrusterManager,
    mix,
)
from modules.thrusters.uart_transport import (
    FLAG_ESTOP,
    HEADER,
    MSG_ACK,
    MSG_HEARTBEAT,
    MSG_MOTOR_COMMAND,
    MSG_STATUS,
    MOTOR_SCALE,
    Packet,
    IncompleteFrame,
    UartTransport,
    build_frame,
    build_motor_command,
    crc16_ccitt,
    motor_values_to_int16,
    parse_frame,
)

M1 = ThrusterId.M1_FRONT_VERTICAL
M2 = ThrusterId.M2_MIDDLE_RIGHT_HORIZONTAL
M3 = ThrusterId.M3_MIDDLE_LEFT_HORIZONTAL
M4 = ThrusterId.M4_BACK_RIGHT_VERTICAL
M5 = ThrusterId.M5_BACK_LEFT_VERTICAL
ALL = (M1, M2, M3, M4, M5)

ESP32_CONFIG = {
    "serial_port": "/dev/ttyUSB0",
    "baudrate": 460800,
    "timeout_ms": 100,
    "command_rate_hz": 10000,
    "heartbeat_timeout_ms": 250,
}
PROVIDER_CONFIG = {
    "provider": "esp32",
    "esp32": ESP32_CONFIG,
    "motors": {
        t.name: {"gpio": DEFAULT_GPIO[t], "direction": 1} for t in ALL
    },
}


class FakeSerial:
    """In-memory stand-in for ``serial.Serial``."""

    def __init__(self, port, baudrate, timeout, write_timeout, **kwargs):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.write_timeout = write_timeout
        self.is_open = True
        self.out = bytearray()
        self.inbuf = bytearray()
        self.fail_on_write = False

    def write(self, data):
        if self.fail_on_write:
            raise OSError("device gone")
        self.out.extend(data)
        return len(data)

    def read(self, size):
        take = self.inbuf[:size]
        del self.inbuf[:size]
        return bytes(take)

    @property
    def in_waiting(self):
        return len(self.inbuf)

    def flush(self):
        pass

    def close(self):
        self.is_open = False

    def open(self):
        self.is_open = True


class FailingSerial(FakeSerial):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.is_open = False
        raise OSError("no such device")


class PacketBuildingTest(unittest.TestCase):
    def test_motor_command_frame_layout(self):
        frame = build_motor_command(7, [1.0, -0.5, 0.25, 0.0, -1.0])
        self.assertEqual(frame[:2], HEADER)
        self.assertEqual(frame[2], 0x01)  # version
        self.assertEqual(frame[3], MSG_MOTOR_COMMAND)
        self.assertEqual(frame[4], 10)  # payload length
        self.assertEqual(frame[5], 7)  # sequence
        self.assertEqual(frame[6], 0)  # flags
        values = struct.unpack("<5h", frame[7:17])
        self.assertEqual(values, (1000, -500, 250, 0, -1000))

    def test_crc_covers_body_and_matches(self):
        frame = build_motor_command(1, [0.1, 0.2, 0.3, 0.4, 0.5])
        body = frame[2 : len(frame) - 2]
        self.assertEqual(crc16_ccitt(body), struct.unpack("<H", frame[-2:])[0])

    def test_values_are_clamped_before_transmission(self):
        frame = build_motor_command(1, [5.0, -9.0, 0.0, 1.0, -1.0])
        values = struct.unpack("<5h", frame[7:17])
        self.assertEqual(values, (1000, -1000, 0, 1000, -1000))

    def test_parse_roundtrip(self):
        frame = build_motor_command(42, [0.1, -0.9, 0.5, 0.0, 1.0])
        packet, consumed = parse_frame(frame)
        self.assertIsInstance(packet, Packet)
        self.assertEqual(consumed, len(frame))
        self.assertEqual(packet.mtype, MSG_MOTOR_COMMAND)
        self.assertEqual(packet.sequence, 42)
        self.assertEqual(struct.unpack("<5h", packet.payload), (100, -900, 500, 0, 1000))

    def test_parse_rejects_bad_crc(self):
        frame = bytearray(build_motor_command(1, [0, 0, 0, 0, 0]))
        frame[-1] ^= 0xFF
        with self.assertRaises(ValueError) as ctx:
            parse_frame(bytes(frame))
        self.assertEqual(str(ctx.exception), "crc")

    def test_parse_short_frame_raises_incomplete(self):
        frame = build_motor_command(1, [0, 0, 0, 0, 0])
        with self.assertRaises(IncompleteFrame):
            parse_frame(frame[:7])

    def test_motor_values_to_int16_scale(self):
        payload = motor_values_to_int16([1.0, -1.0, 0.5, -0.5, 0.0])
        self.assertEqual(struct.unpack("<5h", payload), (1000, -1000, 500, -500, 0))


# -- transport tests -------------------------------------------------------


class TransportTest(unittest.TestCase):
    def _transport(self, **kwargs):
        cfg = dict(ESP32_CONFIG)
        cfg.update(kwargs)
        return UartTransport(cfg, serial_factory=FakeSerial)

    def test_open_success(self):
        t = self._transport()
        self.assertTrue(t.open())
        self.assertTrue(t.is_open())

    def test_open_without_device_sets_error(self):
        t = UartTransport(dict(ESP32_CONFIG), serial_factory=FailingSerial)
        self.assertFalse(t.open())
        self.assertFalse(t.is_open())
        self.assertGreaterEqual(t.stats["open_failures"], 1)
        self.assertIsNotNone(t.stats["last_error"])

    def test_open_without_port_configured(self):
        t = UartTransport({"esp32": {"baudrate": 115200}}, serial_factory=FakeSerial)
        self.assertFalse(t.open())
        self.assertTrue("serial_port" in str(t.stats["last_error"]))

    def test_send_writes_frame_and_counters(self):
        t = self._transport()
        t.open()
        frame = build_motor_command(1, [1, 0, 0, 0, -1])
        self.assertTrue(t.send(frame))
        self.assertEqual(t.stats["tx_frames"], 1)
        self.assertEqual(bytes(t._ser.out), frame)

    def test_send_drops_when_not_open(self):
        t = UartTransport(dict(ESP32_CONFIG), serial_factory=FailingSerial)
        self.assertFalse(t.send(b"\x00"))
        self.assertEqual(t.stats["dropped_frames"], 1)

    def test_send_failure_reconnects_next_time(self):
        t = self._transport(reconnect_interval_s=0.0)
        t.open()
        frame = build_motor_command(1, [0, 0, 0, 0, 0])
        self.assertTrue(t.send(frame))
        self.assertEqual(t.stats["tx_frames"], 1)
        t._ser.close()  # device disappears
        self.assertFalse(t.is_open())
        # next send auto-reopens (reconnect_interval_s = 0) and succeeds
        self.assertTrue(t.send(frame))
        self.assertTrue(t.is_open())
        self.assertEqual(t.stats["tx_frames"], 2)

    def test_pump_reads_ack_frame(self):
        t = self._transport()
        t.open()
        ack = build_frame(3, MSG_ACK, b"")
        t._ser.inbuf.extend(ack)
        t.pump()
        packets = t.read_packets()
        self.assertEqual(len(packets), 1)
        self.assertEqual(packets[0].mtype, MSG_ACK)
        self.assertEqual(packets[0].sequence, 3)
        self.assertEqual(t.stats["rx_frames"], 1)

    def test_pump_resyncs_through_garbage(self):
        t = self._transport()
        t.open()
        status = build_frame(9, MSG_STATUS, b"abc")
        t._ser.inbuf.extend(b"\x00\x01\x02" + status)
        t.pump()
        packets = t.read_packets()
        self.assertEqual(len(packets), 1)
        self.assertEqual(packets[0].mtype, MSG_STATUS)
        self.assertGreaterEqual(t.stats["resyncs"], 1)

    def test_pump_handles_corrupted_then_valid(self):
        t = self._transport()
        t.open()
        bad = bytearray(build_frame(1, MSG_HEARTBEAT, b""))
        bad[-1] ^= 0xFF
        good = build_frame(2, MSG_HEARTBEAT, b"")
        t._ser.inbuf.extend(bytes(bad) + good)
        t.pump()
        packets = t.read_packets()
        self.assertEqual(len(packets), 1)
        self.assertEqual(packets[0].sequence, 2)
        self.assertGreaterEqual(t.stats["crc_errors"], 1)

    def test_pump_buffers_partial_frame_in_two_reads(self):
        t = self._transport()
        t.open()
        heartbeat = build_frame(5, MSG_HEARTBEAT, b"xx")
        half = len(heartbeat) // 2
        t._ser.inbuf.extend(heartbeat[:half])
        t.pump()
        self.assertEqual(t.read_packets(), [])
        t._ser.inbuf.extend(heartbeat[half:])
        t.pump()
        packets = t.read_packets()
        self.assertEqual(len(packets), 1)
        self.assertEqual(packets[0].sequence, 5)

    def test_close_is_safe_and_idempotent(self):
        t = self._transport()
        t.open()
        t.close()
        t.close()
        self.assertFalse(t.is_open())


class Esp32ProviderTest(unittest.TestCase):
    def _provider(self, transport=None):
        p = Esp32ThrusterProvider(
            PROVIDER_CONFIG, sensors=None, transport=transport
        )
        return p

    def _open_provider(self):
        transport = UartTransport(
            dict(ESP32_CONFIG), serial_factory=FakeSerial
        )
        provider = self._provider(transport=transport)
        provider._command_interval = 0.0  # disable rate limiting for these tests
        transport.open()
        return provider, transport

    def test_command_rate_limits_sends(self):
        transport = UartTransport(
            dict(ESP32_CONFIG), serial_factory=FakeSerial
        )
        provider = self._provider(transport=transport)
        provider._command_interval = 1.0  # at most one frame per second
        transport.open()
        provider.apply(MotionState(), 0.1, setpoints={t: 0.0 for t in ALL})
        self.assertEqual(transport.stats["tx_frames"], 1)
        provider._last_send = time.monotonic()  # force "just sent"
        provider.apply(MotionState(), 0.1, setpoints={t: 0.0 for t in ALL})
        self.assertEqual(transport.stats["tx_frames"], 1)  # throttled
        provider._last_send = 0.0  # let it through again
        provider.apply(MotionState(), 0.1, setpoints={t: 0.0 for t in ALL})
        self.assertEqual(transport.stats["tx_frames"], 2)

    def _last_frame(self, transport):
        out = bytes(transport._ser.out)
        return out[-19:]  # the most recently written MOTOR_COMMAND frame

    def test_setpoints_identical_to_mix(self):
        provider = self._provider()
        motion = MotionState(surge=0.5, yaw=-0.3, heave=0.2)
        self.assertEqual(provider.setpoints(motion), mix(motion))

    def test_apply_sends_m1_to_m5_never_axes(self):
        provider, transport = self._open_provider()
        provider.apply(MotionState(surge=1.0, heave=1.0), 0.1, setpoints={t: 1.0 for t in ALL})
        frame = self._last_frame(transport)
        packet, _ = parse_frame(frame)
        self.assertEqual(packet.mtype, MSG_MOTOR_COMMAND)
        # payload is exactly 5 motors, never surge/yaw/heave
        self.assertEqual(len(struct.unpack("<5h", packet.payload)), 5)
        self.assertEqual(packet.flags, 0)

    def test_apply_sends_the_mixed_values_passed_in(self):
        provider, transport = self._open_provider()
        setpoints = {M1: 1.0, M2: -1.0, M3: 0.5, M4: -0.5, M5: 0.0}
        provider.apply(MotionState(), 0.1, setpoints=setpoints)
        frame = self._last_frame(transport)
        packet, _ = parse_frame(frame)
        values = struct.unpack("<5h", packet.payload)
        self.assertEqual(
            values,
            tuple(int(round(setpoints[t] * MOTOR_SCALE)) for t in ALL),
        )

    def test_apply_reclamps_out_of_range_setpoints(self):
        provider, transport = self._open_provider()
        setpoints = {t: 9.0 if i % 2 == 0 else -9.0 for i, t in enumerate(ALL)}
        provider.apply(MotionState(), 0.1, setpoints=setpoints)
        frame = self._last_frame(transport)
        packet, _ = parse_frame(frame)
        values = struct.unpack("<5h", packet.payload)
        self.assertTrue(all(v == 1000 or v == -1000 for v in values))
        self.assertEqual(values[0], 1000)  # M1 was 9.0 -> clamped to +1000

    def test_sequence_increments_across_commands(self):
        provider, transport = self._open_provider()
        provider.apply(MotionState(), 0.1, setpoints={t: 0.5 for t in ALL})
        seq1 = parse_frame(self._last_frame(transport))[0].sequence
        provider.apply(MotionState(), 0.1, setpoints={t: -0.5 for t in ALL})
        seq2 = parse_frame(self._last_frame(transport))[0].sequence
        self.assertEqual((seq1, seq2), (0, 1))

    def test_estop_asserted_sends_zero_estop_frame(self):
        provider, transport = self._open_provider()
        provider.apply(MotionState(surge=1.0), 0.1, setpoints={t: 1.0 for t in ALL})
        provider.notify_estop(True)
        frame = self._last_frame(transport)
        packet, _ = parse_frame(frame)
        self.assertEqual(packet.flags & FLAG_ESTOP, FLAG_ESTOP)
        self.assertEqual(struct.unpack("<5h", packet.payload), (0, 0, 0, 0, 0))

    def test_apply_while_estop_never_sends_motion(self):
        provider, transport = self._open_provider()
        provider.notify_estop(True)
        provider.apply(MotionState(surge=1.0, heave=1.0), 0.1, setpoints={t: 1.0 for t in ALL})
        frame = self._last_frame(transport)
        packet, _ = parse_frame(frame)
        self.assertEqual(packet.flags & FLAG_ESTOP, FLAG_ESTOP)
        self.assertEqual(struct.unpack("<5h", packet.payload), (0, 0, 0, 0, 0))

    def test_clear_estop_resumes_motion(self):
        provider, transport = self._open_provider()
        provider.notify_estop(True)
        provider.notify_estop(False)
        setpoints = {t: 1.0 if t == M2 else 0.0 for t in ALL}
        provider.apply(MotionState(surge=1.0), 0.1, setpoints=setpoints)
        frame = self._last_frame(transport)
        packet, _ = parse_frame(frame)
        self.assertEqual(packet.flags & FLAG_ESTOP, 0)
        self.assertEqual(packet.payload, motor_values_to_int16([0, 1, 0, 0, 0]))

    def test_estop_keepalive_refreshes_zero_frames(self):
        provider, transport = self._open_provider()
        provider.notify_estop(True)
        provider.estop_keepalive(0.1, {t: 0.0 for t in ALL})
        frame = self._last_frame(transport)
        packet, _ = parse_frame(frame)
        self.assertTrue(packet.flags & FLAG_ESTOP)
        self.assertEqual(struct.unpack("<5h", packet.payload), (0, 0, 0, 0, 0))

    def test_ack_updates_status_and_latency(self):
        provider, transport = self._open_provider()
        provider.apply(MotionState(), 0.1, setpoints={t: 0.0 for t in ALL})
        ack = build_frame(0, MSG_ACK, b"")
        transport._ser.inbuf.extend(ack)
        provider._pump()
        status = provider.status()
        self.assertEqual(status["last_ack_seq"], 0)
        self.assertIsNotNone(status["last_ack_latency_s"])

    def test_ack_with_wrong_seq_counts_missing(self):
        provider, transport = self._open_provider()
        provider.apply(MotionState(), 0.1, setpoints={t: 0.0 for t in ALL})
        ack = build_frame(99, MSG_ACK, b"")
        transport._ser.inbuf.extend(ack)
        provider._pump()
        self.assertEqual(provider.status()["missing_acks"], 1)

    def test_status_exposes_link_and_packet_state(self):
        provider, transport = self._open_provider()
        status = provider.status()
        self.assertTrue(status["connected"])
        self.assertIn("tx_frames", status)
        self.assertIn("estop", status)

    def test_disconnected_provider_does_not_crash(self):
        transport = UartTransport(
            dict(ESP32_CONFIG), serial_factory=FailingSerial
        )
        provider = self._provider(transport=transport)
        provider.apply(MotionState(surge=1.0), 0.1, setpoints={t: 1.0 for t in ALL})
        status = provider.status()
        self.assertFalse(status["connected"])
        self.assertGreaterEqual(status["dropped_frames"], 1)

    def test_manager_accepts_esp32_provider_without_hardware(self):
        mgr = ThrusterManager(PROVIDER_CONFIG, sensors=None)
        self.assertTrue(mgr.initialize())
        mgr.start()
        mgr.set_motion(MotionState(surge=1.0))
        mgr.update()
        mgr.update()
        # app must survive with no ESP32 connected
        self.assertIsInstance(mgr.provider, Esp32ThrusterProvider)
        self.assertFalse(mgr.provider.is_connected())

    def test_manager_estop_reaches_provider(self):
        mgr = ThrusterManager(PROVIDER_CONFIG, sensors=None)
        mgr.initialize()
        mgr.emergency_stop()
        self.assertTrue(mgr.provider._estop)
        mgr.clear_emergency_stop()
        self.assertFalse(mgr.provider._estop)


if __name__ == "__main__":
    unittest.main(verbosity=2)