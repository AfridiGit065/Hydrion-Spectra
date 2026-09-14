# Hydrion Spectra — ROV Controller (Raspberry Pi)

Underwater ROV (Remotely Operated Vehicle) control system for Raspberry Pi (Raspberry Pi OS),
designed as a modular, professional control station. This file is the session handover document:
reading it tells you exactly what exists, what runs, and what to do next.

---

## 1. Project Goal

Build a modular ROV software stack that:

- Auto-starts on Raspberry Pi boot (via systemd).
- Provides a professional GUI control station.
- Streams live camera video.
- Drives a real 5-thruster layout via ESP32 ESC controller over UART.
- Provides real-time telemetry, sensors (IMU/depth/compass), failsafe, logging, mission control.

**Current milestone:** Phase 2 Part B is **DONE** — the ESP32 firmware protocol is fully implemented
in Python (the Pi side), the GUI is upgraded with live thruster/motion panels, E-STOP/RE-ARM, ESP32
UART diagnostics, and the system is tested end-to-end (72 unit tests pass, GUI boots clean with
simulated provider, ESP32 thread lifecycle verified).

---

## 2. Project Structure

```
hydrion-spectra/
├── app/                 # Entry point
│   └── main.py          # RUNS THE APP (launches GUI)
├── core/                # Shared framework
│   ├── base_module.py   # BaseModule class (implemented)
│   ├── application.py   # Application (boots Config+Logger+ServiceManager+Qt)
│   └── service_manager.py  # ServiceManager (module lifecycle conductor)
├── modules/             # Feature modules
│   ├── camera/          # camera_manager.py — REAL (captures + reads frames)
│   ├── sensors/         # sensor_manager.py — REAL (state + apply_motion, simulated provider)
│   ├── telemetry/       # telemetry_manager.py — REAL (JSON frames + heartbeat over a Link)
│   ├── controller/      # controller.py — REAL (MotionState merge: pad/keyboard/link/gamepad)
│   ├── config/          # config_manager.py — loads all YAML configs centrally
│   ├── logger/          # logger_manager.py — console + file logging
│   └── thrusters/       # 5-thruster model + ESP32 UART transport
│       ├── thruster_manager.py   # ThrusterManager + Esp32ThrusterProvider + SimulatedProvider
│       └── uart_transport.py     # ESP32 firmware-matched binary frame protocol
├── ui/                  # GUI (Hydrion Spectra GCS "Dark Ocean" style)
│   ├── main_window.py   # MainWindow — app bar + nav + footer + dashboard + panels
│   ├── theme.py         # Design tokens (colors/fonts) + global QSS
│   ├── glass.py         # GlassPanel / StatusPill / NavButton / ValueRow widgets
│   ├── control_pad.py   # ControlPad3D — circular joystick + yaw ring
│   ├── sonar.py         # SonarPanel — top-right glass map
│   ├── hud.py           # HUD overlay — compass + crosshair + DEPTH/ALT + status chips
│   └── sections.py      # Nav pages — Sensors/Diagnostics/Logs/Settings/Operations
├── configs/             # YAML configs
│   ├── thrusters.yaml   # provider selection + ESP32 UART settings + motor map
│   ├── hud.yaml         # HUD settings (compass/crosshair/depth-alt/extra/status chips)
│   ├── gcs.yaml         # GCS shell (sonar + telemetry sim values)
│   ├── controller.yaml  # keymap + gamepad codemap
│   ├── camera.yaml      # camera device settings
│   ├── sensors.yaml     # sensor provider settings
│   └── network.yaml     # telemetry link settings
├── systemd/             # rov-controller.service — auto-start template (Step 6)
├── scripts/             # start.sh / stop.sh / restart.sh
├── tests/               # 72 unit tests (mixer + UART transport + provider)
├── logs/                # system.log / errors.log / mission.log (runtime)
└── .venv/               # Python 3.13 virtualenv with deps
```

---

## 3. Setup & Dependencies

Runs on **Raspberry Pi 5** (aarch64, Debian 13 trixie) or any Linux with a display.

Virtualenv: `.venv` (Python 3.13). Installed packages:

| Package        | Version |
|----------------|---------|
| opencv-python  | 5.0.0.93 |
| PySide6        | 6.11.2 |
| pillow         | 12.3.0 |
| PyYAML         | 6.0.3 |
| numpy          | 2.5.3 |
| pyserial       | 3.5    |

Activate / re-create:

```bash
cd /path/to/hydrion-spectra
python3 -m venv .venv
source .venv/bin/activate
pip install opencv-python PySide6 pillow PyYAML numpy pyserial
```

---

## 4. How to Run

```bash
source .venv/bin/activate
python app/main.py
```

Expected behavior:

1. A window **"HYDRION SPECTRA - ROV Controller"** opens (dark navy "Dark Ocean" theme):
   - **Top app bar:** brand, pills (ROV / ESP32 / MODE / DEPTH / BATT / E-STOP / LINK / UP).
   - **Left nav rail** (expands on hover): Dashboard, Operations, Sensors, Manipulator, Diagnostics,
     Planner, AI Vision, Logs, Settings, and a LAUNCH MISSION button.
   - **Dashboard:** camera feed with overlays — LIVE indicator, sonar map, system telemetry, thruster
     meters (M1-M5), motion bars (SURGE/YAW/HEAVE), control dock (ARMED/REC/SNAP/LIGHTS/E-STOP/RE-ARM),
     circular motion controller, mission-log flyout.
   - **Bottom footer:** FPS / CPU / RAM / STORAGE / DEPTH / LATENCY / ESP32 / THRUST.
2. Drive the simulated ROV:
   - **Pad:** drag the circular stick — vertical = surge, horizontal = yaw — spring-return on release.
   - **Keyboard:** `W/S` forward/back, `A/D` + `Q/E` turn (yaw), `R/F` up/down (heave), `I/K` pitch,
     `J/L` roll (future), `Shift` boost, `Backspace` kill / E-STOP.
3. **E-STOP:** click the E-STOP button in the dock or press `Backspace` — all thrusters halt immediately,
   ESP32 receives ESTOP message. Press **RE-ARM** to resume (requires ESP32 acknowledgment).
4. Thruster meters update in real-time (100ms refresh), showing M1-M5 percentages and direction.
5. Telemetry frames are appended to `logs/mission.log`.
6. Closing the window releases the camera and stops all threads cleanly.

---

## 5. Implemented vs Placeholders

### Implemented (real code)

- **core/base_module.py** — `BaseModule` with `initialize/start/update/stop/health_check`.
- **core/service_manager.py** — `ServiceManager`: the conductor. `register(module)`, then
  `initialize_all/start_all/update_all/stop_all`. Each step is try/except-guarded.
- **core/application.py** — `Application`: boots Config + Logger, builds modules from config
  (CameraManager, SensorManager, TelemetryManager, ControllerModule, ThrusterManager), creates
  QApplication + MainWindow, drives update_all on a 100ms timer.
- **modules/config/config_manager.py** — `ConfigManager`: loads every `configs/*.yaml` centrally.
- **modules/logger/logger_manager.py** — `LoggerManager`: console + file logging to logs/.
- **modules/camera/camera_manager.py** — `CameraManager`: opens cv2.VideoCapture, reads frames.
- **modules/sensors/sensor_manager.py** — `SensorManager` with `SimulatedSensorProvider`. Produces
  `HudState` (x, y, depth, yaw_deg). `apply_motion()` integrates commanded motion into position.
- **modules/telemetry/telemetry_manager.py** — `TelemetryManager`: packs state into JSON frames,
  sends over a `Link`, emits heartbeats, buffers incoming commands.
- **modules/controller/controller.py** — `ControllerModule` + `MotionState` dataclass. Merges input
  sources (pad/keyboard/link) per axis (strongest wins). Handles link commands (FORWARD, LEFT, UP,
  STOP, ...) and `kill()` emergency stop. `LEFT`/`RIGHT` = yaw (no sway thruster).
- **modules/thrusters/thruster_manager.py** — 5-thruster model with:
  - `ThrusterId` enum (M1-M5).
  - Pure `mix()` function: M1/M4/M5 = heave, M2 = surge+yaw, M3 = surge-yaw. Clamps [-1,1].
  - `ThrusterProvider` ABC → `SimulatedThrusterProvider` + `Esp32ThrusterProvider`.
  - `Esp32ThrusterProvider`: 50Hz background thread, ESTOP/RE-ARM, safety gate, sequence sync,
    failsafe, reconnect-in-zero. All state exposed via `status()` for UI/diagnostics.
  - `ThrusterManager`: failsafe clamp, `get_provider_status()`, `emergency_stop()`/`clear_emergency_stop()`.
- **modules/thrusters/uart_transport.py** — ESP32 firmware-matched binary frame protocol:
  - Frame layout, message types, CRC-16/CCITT-FALSE, uint16 sequence, ACK/STATUS payload formats.
  - `build_motor_command()`, `build_estop()`, `parse_frame()`, `decode_ack()`, `decode_status()`.
- **ui/main_window.py** — MainWindow with:
  - App bar: ROV / ESP32 / MODE / DEPTH / BATT / E-STOP / LINK / UP pills.
  - Dashboard: thruster meters (M1-M5), motion bars (SURGE/YAW/HEAVE), E-STOP + RE-ARM dock buttons.
  - Toast notifications for E-STOP / RE-ARM.
  - 100ms fast refresh for live panels.
- **ui/control_pad.py** — ControlPad3D (circular joystick + yaw ring + reset()).
- **ui/sonar.py** — SonarPanel (glass map with ship, umbilical, ROV, sonar ping).
- **ui/hud.py** — HUD overlay: compass, crosshair, DEPTH/ALT pillars, **status chips** (mode / ESP32
  link / E-STOP drawn into the video frame, optional via config).
- **ui/sections.py** — Nav pages:
  - **Sensors:** depth/heading/position/pitch/roll + health pills (including ESP32).
  - **Operations:** system status + THRUSTERS panel (M1-M5 live values) + E-STOP/RE-ARM buttons.
  - **Diagnostics:** SUBSYSTEM HEALTH + COMPUTE CORE LOAD + UMBILICAL + **ESP32 UART LINK panel**
    (state/provider/tx/rx/crc/resync/ack-latency/seq/motors/last-error + E-STOP/RE-ARM buttons).
  - Logs, Settings — real. Navigation/Manipulator/Planner/AI Vision — placeholders.
- **configs/** — All YAML configs filled in with defaults.
- **systemd/** + **scripts/** — Auto-start on boot (Step 6).

### Manual control

| Input | What it drives | Status |
|-------|---------------|--------|
| `ControlPad3D` (mouse) | surge / yaw (+ yaw ring indicator) | live |
| Keyboard (`configs/controller.yaml` `keymap`) | surge / yaw / heave + boost + kill/E-STOP | live |
| Link commands (`FORWARD`, `LEFT`, ...) | same motion target | live |

Heave (up/down) is on the keyboard (**R/F**); the circular pad drives surge/yaw.

### 5-thruster motion model — canonical reference

| ID | Role | ESP32 GPIO | Mixer equation | Direction |
|----|------|:----------:|----------------|:---------:|
| `M1_FRONT_VERTICAL` | Front vertical | 25 | `heave` | configurable ±1 |
| `M2_MIDDLE_RIGHT_HORIZONTAL` | Middle right | 33 | `surge + yaw` | configurable ±1 |
| `M3_MIDDLE_LEFT_HORIZONTAL` | Middle left | 32 | `surge − yaw` | configurable ±1 |
| `M4_BACK_RIGHT_VERTICAL` | Back right | 27 | `heave` | configurable ±1 |
| `M5_BACK_LEFT_VERTICAL` | Back left | 26 | `heave` | configurable ±1 |

Supported axes: **surge, yaw, heave**. No sway. Pitch/roll kept for future, produce zero motor.

---

## 6. HUD Overlays (ui/hud.py + ui/sonar.py)

### Frame overlays (ui/hud.py)
- **Compass** (top-center): heading ± 20°.
- **Crosshair + pitch ladder** (center).
- **DEPTH pillar** (left-middle), **ALT pillar** (right-middle).
- **Status chips** (top-left, optional): shows MODE, ESP32 link state, E-STOP state drawn into the
  video feed. Configurable via `configs/hud.yaml` → `extra.enabled`.
- All panels toggleable via `configs/hud.yaml`.

### Sonar map (ui/sonar.py)
- Glass panel: ship, dashed umbilical, ROV triangle, animated sonar ping.

### Config reference (`configs/hud.yaml`)

| Key | Default |
|-----|---------|
| `enabled` | `true` |
| `panel_alpha` | `0.55` |
| `compass.enabled` | `true` |
| `crosshair.enabled` | `true` |
| `depth_alt.enabled` | `true` |
| `extra.enabled` | `true` (status chips) |

---

## 7. Hardware Integration (Simulation-first)

Every module is written against a clean interface. Currently returns simulated values; real hardware
is attached later by swapping the provider — nothing else changes.

### ESP32 UART Protocol (firmware reference)

**The ESP32 firmware is the source of truth.** The Pi matches it exactly.

Frame layout (little-endian):

```
BYTE    FIELD        NOTES
0-1     HEADER       0xAA 0x55 (sync)
2       VERSION      0x01
3       TYPE         0x01 MOTOR_COMMAND (Pi->ESP32)
                     0x02 ESTOP        (Pi->ESP32)
                     0x81 ACK          (ESP32->Pi)
                     0x82 STATUS       (ESP32->Pi)
4       LENGTH       payload bytes
5-6     SEQUENCE     uint16 little-endian (monotonically increasing)
7..     PAYLOAD      type-specific (see below)
last-2  CRC16        CRC-16/CCITT-FALSE over ENTIRE frame INCLUDING the
                     0xAA 0x55 header (init=0xFFFF, poly=0x1021)
```

**Message types:**

| Type | Value | Direction | Payload |
|------|-------|-----------|---------|
| MOTOR_COMMAND | 0x01 | Pi→ESP32 | 5×int16 LE (M1..M5, -1000..+1000) + 1 FLAGS byte (must be ≤0x03) |
| ESTOP | 0x02 | Pi→ESP32 | empty (length=0); latches E-STOP on ESP32 |
| ACK | 0x81 | ESP32→Pi | STATUS(1) + ECHO_SEQ(2); total 5 bytes region but LENGTH=3 |
| STATUS | 0x82 | ESP32→Pi | FAILSAFE(1) + ESTOP(1) + M1..M5 int16(10); LENGTH=14, 12 meaningful |

**ACK status codes:**
0=OK, 1=CRC error, 2=invalid payload length, 3=invalid motor value, 4=invalid flags,
5=old sequence, 6=unknown packet type, 7=E-STOP active.

**Sequence rules:**
- ESP32 `isNewerSequence` is int16-wraparound; only accepts strictly newer within ±32768.
- Fresh ESP32 starts at `lastSequence=0`; Pi must start at seq ≥ 1.
- Pi seeds from first STATUS: `pi_seq = esp32_lastSeq + 1`.
- Resyncs if `((pi_seq - esp_seq) & 0xFFFF) > 0x8000` (ESP32 restarted).
- ESTOP does NOT advance ESP32 lastSequence.

**E-STOP:**
- Pi sends TYPE=0x02 (ESTOP message), ESP32 latches `estopActive=true` forever.
- NO protocol-level re-arm in firmware — recovery requires ESP32 reset.
- Pi holds a safety gate (zeros) until ACK status 0 or STATUS shows `failsafe=0 && estop=0`.

**50Hz command stream:**
- Background daemon thread sends MOTOR_COMMAND at `command_rate_hz` (default 50).
- ESP32 250ms watchdog: no accepted command → ESCs stop automatically (failsafe).
- Pi link timeout: `heartbeat_timeout_ms` (default 1500ms, STATUS cadence 500ms).

**To get real values:** set `thrusters.provider: esp32` and point `thrusters.esp32.serial_port`
at the USB-UART adapter. Nothing else changes — the app tolerates a missing device (reports
disconnected, retries reconnects, never crashes).

### ESP32 GPIO Mapping (wiring, must not change)

| Thruster | ESP32 GPIO | Role |
|----------|:----------:|------|
| M1 | 25 | Front vertical |
| M2 | 33 | Middle right horizontal |
| M3 | 32 | Middle left horizontal |
| M4 | 27 | Back right vertical |
| M5 | 26 | Back left vertical |

ESC PWM: 50Hz, 1000-2000μs, 3D mode off.

---

## 8. Raspberry Pi Auto-Start (systemd) — Step 6

The ROV controller auto-starts on boot and restarts if it crashes.

- **Service name:** `rov-controller.service`
- **Deployment path:** `/home/riazafridi/Downloads/Hydrion-Spectra-main`
- **Unit template:** `systemd/rov-controller.service` (rendered by `scripts/start.sh`)
- **GUI environment:** `/etc/rov-controller.env` (DISPLAY/XAUTHORITY/QT_QPA_PLATFORM=xcb)
- **Behaviour:** starts after `graphical.target`; `Restart=on-failure`, `RestartSec=5`

### Commands

| Action | Command |
|--------|---------|
| Install + start | `bash scripts/start.sh` |
| Start / Stop / Restart | `sudo systemctl start/stop/restart rov-controller.service` |
| Enable / Disable at boot | `sudo systemctl enable/disable rov-controller.service` |
| Status | `systemctl status rov-controller.service` |
| Live logs | `journalctl -u rov-controller.service -f` |

---

## 9. Progress Log

### Current state

> Everything runs with simulated/dummy data — real ESP32 hardware is not attached yet.
> **ESP32 UART protocol is fully implemented on the Pi side.** ESP32 firmware exists as a
> separate `.ino` sketch (Arduino-ESP32) — the Pi's `uart_transport.py` matches it exactly.

| # | Step | Status |
|---|------|--------|
| 0 | GUI + camera + HUD | done |
| 1 | Config + Logger | done |
| 2 | ServiceManager / Application | done |
| 3 | Sensors / telemetry pipeline | done |
| 4 | Network / telemetry link | done |
| 5 | Thrusters / motion control | done |
| P1 | 5-thruster hardware model | done |
| 6 | systemd auto-start | done |
| P2A | ESP32 link (Pi side) | done |
| P2B | ESP32 firmware (Pi-side protocol matched) | done |
| P2B+ | Real-time UI upgrade (thrusters/motion/E-STOP/diagnostics) | done |

### Change record (most recent first)

- **2026-09-14 — Phase 2 Part B+ (Step 4): Real-time 5-thruster control + UI upgrade**
  - **UART protocol rewrite:** `modules/thrusters/uart_transport.py` completely rewritten to match
    the ESP32 firmware byte-for-byte:
    - Message types: MOTOR_COMMAND=0x01, ESTOP=0x02, ACK=0x81, STATUS=0x82 (was: ACK=0x02,
      STATUS=0x04, HEARTBEAT=0x05, flag-bit ESTOP — all wrong).
    - Sequence is uint16 little-endian at bytes 5-6 (was: 1-byte at byte 5).
    - CRC covers the ENTIRE frame including the AA 55 header (was: body-only, header excluded).
    - ESTOP is a message TYPE (was: FLAGS bit0).
    - ACK: LENGTH=3 declared, 5-byte payload region (status + echo seq). STATUS: LENGTH=14,
      12 meaningful bytes (failsafe, estop, M1..M5 int16).
    - Motor command payload = 5×int16 + FLAGS byte (11 bytes).
    - `build_estop()`, `decode_ack()`, `decode_status()` added. MAX_FRAME_SIZE = 64.
    - CRC-16/CCITT-FALSE validated against standard check value (0x29B1 for "123456789").
  - **Esp32ThrusterProvider rewrite:** `modules/thrusters/thruster_manager.py`:
    - 50Hz background daemon thread (non-blocking pump + rate-limited send).
    - threading.RLock for shared state.
    - Safety gate: zeros until ESP32 ACKs a zero command (ACK status 0) or STATUS shows clear.
    - Latched E-STOP: sends ESTOP frames at 50Hz while active; RE-ARM sends zeros until accepted.
    - Sequence: starts at 1 (fresh ESP32 at 0 rejects equal), seeds from STATUS
      (`pi_seq = esp_seq + 1`), resyncs when gap > 0x8000.
    - Link alive timeout: 1500ms (STATUS cadence 500ms).
    - Reconnect-in-zero: never restores previous non-zero thrust.
    - `stop()` sends final zeroed command, then closes transport.
    - `status()` dict: all stats for UI (tx/rx/crc/resync/dropped/ack-latency/esp32-seq/motors/etc).
  - **ThrusterManager:** failsafe zero-clamp (esp32 provider + not link_alive → zero), get_provider_status(),
    stop() → provider.stop().
  - **configs/thrusters.yaml:** esp32 block with baudrate 460800, command_rate_hz 50,
    heartbeat_timeout_ms 1500, reconnect_interval_s 1.0. Provider selection documented.
  - **GUI upgrade (ui/main_window.py):**
    - App bar: ROV / ESP32 / MODE / DEPTH / BATT / E-STOP / LINK / UP pills.
    - Dashboard: thruster meters (M1-M5 bipolar bars with %), motion bars (SURGE/YAW/HEAVE).
    - Dock: E-STOP + RE-ARM buttons (alongside ARMED/REC/SNAP/LIGHTS).
    - Toast notifications for E-STOP / RE-ARM.
    - 100ms fast refresh timer for live panels.
    - Kill key (Backspace) now triggers E-STOP.
    - E-STOP blocks ARM toggle until RE-ARM.
  - **UI diagnostics (ui/sections.py):**
    - OperationsPage: THRUSTERS panel with M1-M5 live %, E-STOP/FAILSAFE state, controls.
    - DiagnosticsPage: ESP32 UART LINK panel with STATE/PROVIDER/TX/RX/CRC/RESYNC/MISSING ACK/
      ACK LATENCY/ESP32 SEQ/ESP32 MOTORS/LAST ERROR + E-STOP/RE-ARM buttons.
    - SensorsPage: ESP32 added to health pills.
  - **HUD (ui/hud.py):** optional status chips (mode/ESP32/E-STOP) drawn into the video frame.
    Configurable via `hud.extra.enabled`.
  - **core/application.py:** thrusters passed to MainWindow and wired into UI context.
  - **ui/control_pad.py:** added `reset()` method for E-STOP.
  - **Tests:** `tests/test_uart_transport.py` rewritten (72 tests total, all passing):
    - Protocol framing: header CRC-including, uint16 seq, motor command layout.
    - ACK/STATUS parsing: firmware-style payloads, statuses 0-7, STATUS 14-byte region.
    - Transport: open/send/pump/resync/partial-frame/close.
    - Provider: gate/rearm/estop/sequence-sync/stale-link/disconnect/stop-zeroes.
    - Manager: estop-reach/failsafe-zero/esp32-without-hardware.
  - **GUI smoke test:** Full Application boots clean offscreen with simulated provider.
  - **ESP32 provider lifecycle:** FailingSerial test: thread starts, sends frames, counts drops,
    status reports correctly, clean shutdown.

- **2026-09-13 — Phase 2 Part A: ESP32 UART link (Pi side)**
  - Initial implementation of `uart_transport.py` + `Esp32ThrusterProvider` (later rewritten in
    Step 4 above to match the actual firmware protocol).

- **2026-09-13 — Step 6: systemd auto-start**
  - Unit template + scripts for auto-start on boot. Verified lifecycle on the Pi.

- **2026-08-07 — Phase 1: 5-thruster hardware model**
  - ThrusterId enum, pure mix() function, ThrusterProvider ABC, SimulatedThrusterProvider.

- **2026-08-06 — UI redesign + Steps 2-5**
  - Dark Ocean glassmorphism shell, sensor pipeline, telemetry, controller, motion control.

---

## 10. Testing

### Run all tests

```bash
cd /path/to/hydrion-spectra
source .venv/bin/activate
python -m unittest discover -s tests -v
```

### What's tested (72 tests)

**test_thruster_mixer.py (26 tests):**
- 5-thruster mixer: neutral, forward/backward, yaw left/right, up/down, combined axes.
- Saturation clamping, unsupported axes (sway/pitch/roll), direction flip, five-output invariant.
- ThrusterManager: forward setpoints, emergency stop, clear stop, fallback provider, GPIO config.

**test_uart_transport.py (46 tests):**
- Protocol framing: header layout, uint16 sequence, motor command 11-byte payload, CRC covers header.
- CRC validation: CCITT-FALSE check value (0x29B1), bad CRC rejection, header-modified CRC.
- Roundtrip: build → parse, parse incomplete frame, parse oversized length.
- ACK/STATUS: firmware-style payloads, all 8 status codes, STATUS 14-byte payload region.
- Transport: open/close/rate-limited reconnect, send/write/drop, pump/resync through garbage,
  partial frame buffering across reads.
- Provider: safety gate (zeros until ACK), ESTOP message type (not flag), rearm handshake,
  sequence increment, stale link → failsafe, disconnect → no crash, stop zeroed, thread lifecycle.
- Manager: ESP32 without hardware, estop reaches provider, failsafe zeroes outputs.

### Headless smoke test

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python - <<'EOF'
from core.application import Application
from ui.theme import apply_theme
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
class SmokeApp(Application):
    def run(self):
        self.initialize()
        self.qt_app = QApplication(self.argv)
        apply_theme(self.qt_app)
        self.main_window = self.create_window()
        self.main_window.show()
        QTimer.singleShot(500, self.qt_app.quit)
        return self.qt_app.exec()
SmokeApp().run()
EOF
```

---

## 11. Working Style

Build one small step at a time; verify after each step.

```bash
tree -a -I "__pycache__|*.pyc|.venv"     # view structure
python app/main.py                        # run app
python -m unittest discover -s tests      # run all tests
```
