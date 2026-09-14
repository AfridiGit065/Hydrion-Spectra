"""UART transport for the ESP32 ESC controller (Phase 2 — Raspberry Pi side).

Moves binary packets between the Raspberry Pi and the ESP32 over a serial
port (pyserial). Covers:

  * open / close / safe-exit semantics
  * sending packets with per-command write timeouts
  * a non-blocking read pump with partial-frame resync
  * receive-side validation: header sync, version, length, CRC-16
  * transport-level liveness stats + graceful reconnect

This module is *transport only*: it knows nothing about motion or motors.
The ``Esp32ThrusterProvider`` owns message types, sequence numbers, flags and
the ESTOP logic on top of this transport.
"""

import struct
import time

try:  # optional dependency — degrades gracefully when pyserial is absent
    import serial
except ImportError:  # pragma: no cover - environment-specific
    serial = None

HEADER = b"\xaa\x55"
PROTOCOL_VERSION = 0x01

# Message types
MSG_MOTOR_COMMAND = 0x01  # Pi -> ESP32: 5 motor setpoints (M1..M5)
MSG_ACK = 0x02            # ESP32 -> Pi: acknowledgement of a command
MSG_NACK = 0x03           # ESP32 -> Pi: command rejected (re-parse / retransmit)
MSG_STATUS = 0x04         # ESP32 -> Pi: status / diagnostics frame
MSG_HEARTBEAT = 0x05      # ESP32 -> Pi: periodic liveness frame

# FLAGS byte
FLAG_ESTOP = 0x01         # emergency stop asserted — ESP32 must halt all ESCs now
FLAG_HEARTBEAT_REQ = 0x02 # Pi asks the ESP32 for an immediate heartbeat

# Motor int16 scale: normalized [-1.0, +1.0] <-> [-1000, +1000].
MOTOR_SCALE = 1000

_MAX_RX_CHUNK = 1024


class IncompleteFrame(Exception):
    """Not enough bytes are buffered to finish the current frame yet."""


class Packet:
    """Decoded frame."""

    __slots__ = ("version", "mtype", "length", "sequence", "flags", "payload", "crc")

    def __init__(self, version, mtype, length, sequence, flags, payload, crc):
        self.version = version
        self.mtype = mtype
        self.length = length
        self.sequence = sequence
        self.flags = flags
        self.payload = payload
        self.crc = crc

    def __repr__(self):
        return (
            "Packet(version=%d mtype=0x%02x seq=%d flags=0x%02x len=%d)"
            % (self.version, self.mtype, self.sequence, self.flags, self.length)
        )


class UartTransport:
    """Low-level serial packet transport.

    Polled (no background threads): call :meth:`pump` each tick to absorb
    incoming bytes and enqueue parsed packets, then :meth:`read_packets` to
    drain them. Frames are written through :meth:`send`.
    """

    def __init__(self, config=None, logger=None, serial_factory=None):
        self.config = config or {}
        self.logger = logger
        self.port = self.config.get("serial_port")
        self.baudrate = int(self.config.get("baudrate", 460800))
        self.timeout_ms = float(self.config.get("timeout_ms", 100))
        self.read_timeout = self.timeout_ms / 1000.0
        self.write_timeout = self.timeout_ms / 1000.0
        self.reconnect_interval_s = float(
            self.config.get("reconnect_interval_s", 1.0)
        )
        self.version = int(self.config.get("version", PROTOCOL_VERSION))
        self._serial_factory = serial_factory or serial.Serial
        self._ser = None
        self._rx = bytearray()
        self._pending = []
        self._last_open_attempt = 0.0
        self.stats = dict(
            tx_frames=0,
            rx_frames=0,
            crc_errors=0,
            invalid_packets=0,
            resyncs=0,
            reconnect_attempts=0,
            open_failures=0,
            dropped_frames=0,
            last_error=None,
            last_rx_at=None,
        )

    # -- public helpers ---------------------------------------------------

    def is_open(self):
        return self._ser is not None and self._ser.is_open

    def open(self):
        """Open the serial port once; never raises, records failures instead."""
        now = time.monotonic()
        if self.is_open():
            return True
        if now - self._last_open_attempt < self.reconnect_interval_s:
            return False
        self._last_open_attempt = now
        self._close_ser()
        if serial is None:
            self.stats["last_error"] = "pyserial is not installed"
            self.stats["open_failures"] += 1
            return False
        if not self.port:
            self.stats["last_error"] = (
                "no serial port configured (thrusters.esp32.serial_port)"
            )
            self.stats["open_failures"] += 1
            return False
        try:
            self._ser = self._serial_factory(
                port=self.port,
                baudrate=self.baudrate,
                timeout=self.read_timeout,
                write_timeout=self.write_timeout,
            )
            self.stats["last_error"] = None
            return True
        except (OSError, ValueError) as exc:  # missing device, bad params, ...
            self.stats["last_error"] = str(exc)
            self.stats["open_failures"] += 1
            self._ser = None
            return False

    def close(self):
        """Close the port safely (idempotent, never raises)."""
        self._close_ser()
        self._rx = bytearray()

    def _close_ser(self):
        if self._ser is not None:
            try:
                if self.is_open():
                    self._ser.close()
            except (OSError, ValueError):  # pragma: no cover - rare
                pass
            self._ser = None

    def send(self, frame):
        """Write one raw frame. Returns True on success; reconnects on failure."""
        if not self.is_open() and not self.open():
            self.stats["dropped_frames"] += 1
            return False
        try:
            count = self._ser.write(frame)
            if count != len(frame):
                raise OSError("short write: %d/%d bytes" % (count, len(frame)))
            self._flush()
            self.stats["tx_frames"] += 1
            return True
        except Exception as exc:  # SerialException / OSError / Timeout ...
            self.stats["last_error"] = str(exc)
            self.stats["dropped_frames"] += 1
            self.stats["reconnect_attempts"] += 1
            self._close_ser()
            return False

    def _flush(self):
        try:
            self._ser.flush()
        except (OSError, ValueError, AttributeError):  # pragma: no cover
            pass

    def pump(self):
        """Read whatever bytes are available and parse any complete frames."""
        if not self.is_open():
            return
        try:
            waiting = self._ser.in_waiting
        except (OSError, ValueError):  # pragma: no cover
            self._close_ser()
            return
        if waiting:
            try:
                chunk = self._ser.read(min(waiting, _MAX_RX_CHUNK))
            except (OSError, ValueError):  # pragma: no cover
                self._close_ser()
                return
            if chunk:
                self._rx.extend(chunk)
        packets = self._parse_available()
        if packets:
            self._pending.extend(packets)
            if self.stats["last_rx_at"] is None:
                self.stats["last_rx_at"] = time.time()

    def read_packets(self):
        packets = list(self._pending)
        self._pending = []
        return packets

    def reconnect(self):
        """Force a reconnect attempt (close stale handle, reopen)."""
        self.stats["reconnect_attempts"] += 1
        self._close_ser()
        return self.open()

    # -- RX parsing -------------------------------------------------------

    def _parse_available(self):
        """Parse as many frames as possible from the RX buffer, resync as needed."""
        packets = []
        data = self._rx
        while data:
            if len(data) < len(HEADER) or data[: len(HEADER)] != HEADER:
                idx = bytes(data).find(HEADER)
                if idx < 0:
                    self._rx = bytearray()
                    break
                del data[:idx]
                self.stats["resyncs"] += 1
            try:
                packet, consumed = parse_frame(bytes(data), version=self.version)
            except IncompleteFrame:
                break
            except ValueError as exc:
                if str(exc) == "crc":
                    self.stats["crc_errors"] += 1
                else:
                    self.stats["invalid_packets"] += 1
                del data[0]
                self.stats["resyncs"] += 1
                continue
            del data[:consumed]
            packets.append(packet)
        self._rx = bytearray(data)
        if packets:
            self.stats["rx_frames"] += len(packets)
        return packets


# -- packet building / parsing ---------------------------------------------


def crc16_ccitt(data):
    """CRC-16/CCITT-FALSE over ``bytes``."""
    crc = 0xFFFF
    for byte in data:
        crc ^= (byte << 8) & 0xFFFF
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def clamp(value, lo=-1.0, hi=1.0):
    return max(lo, min(hi, float(value)))


def build_frame(sequence, mtype, payload, flags=0, version=PROTOCOL_VERSION):
    """Frame layout (little-endian):

        HEADER | VERSION | TYPE | LENGTH | SEQUENCE | FLAGS | PAYLOAD | CRC16

    CRC covers VERSION .. PAYLOAD (everything after the 2-byte header).
    """
    length = len(payload)
    head = struct.pack("<BBBBB", version, mtype, length, sequence & 0xFF, flags)
    crc = crc16_ccitt(head + payload)
    return HEADER + head + payload + struct.pack("<H", crc)


def motor_values_to_int16(motors):
    """Pack five normalized [-1,1] floats into a 10-byte int16 payload (M1..M5)."""
    values = []
    for value in motors:
        value = clamp(value, -1.0, 1.0)
        values.append(int(round(value * MOTOR_SCALE)))
    return struct.pack("<5h", *values)


def build_motor_command(sequence, motors, flags=0, version=PROTOCOL_VERSION):
    """Build the Pi -> ESP32 MOTOR_COMMAND frame.

    ``motors`` must be the five already-mixed, clamped setpoints in
    M1..M5 (ThrusterId) order. Values are re-clamped here as a hard
    guarantee before transmission.
    """
    return build_frame(
        sequence, MSG_MOTOR_COMMAND, motor_values_to_int16(motors), flags, version
    )


def parse_frame(data, version=PROTOCOL_VERSION):
    """Parse exactly one frame starting at ``data[0]``.

    Returns ``(Packet, consumed)``. Raises ``IncompleteFrame`` when more bytes
    are needed, and ``ValueError`` when the frame is present but invalid
    (wrong version, bad length, or CRC mismatch).
    """
    if len(data) < len(HEADER) or data[: len(HEADER)] != HEADER:
        raise ValueError("missing header")
    # minimum fixed fields before the payload length is known:
    # header(2) + version,type,length,sequence,flags(5) + crc(2)
    if len(data) < len(HEADER) + 5 + 2:
        raise IncompleteFrame()
    length = data[4]
    total = len(HEADER) + 5 + length + 2  # header + fixed + payload + crc
    if len(data) < total:
        raise IncompleteFrame()
    ver = data[2]
    mtype = data[3]
    sequence = data[5]
    flags = data[6]
    payload = data[7 : 7 + length]
    crc = struct.unpack_from("<H", data, 7 + length)[0]
    body = data[2 : 7 + length]  # version .. payload (excludes header and crc)
    if ver != version:
        raise ValueError("version mismatch")
    if crc16_ccitt(body) != crc:
        raise ValueError("crc")
    packet = Packet(
        version=ver,
        mtype=mtype,
        length=length,
        sequence=sequence,
        flags=flags,
        payload=bytes(payload),
        crc=crc,
    )
    return packet, total