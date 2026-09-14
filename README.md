# ROV Controller

Underwater ROV (Remotely Operated Vehicle) control system for Raspberry Pi (Raspberry Pi OS),
designed as a modular, professional control station. This file is the session handover document:
reading it tells you exactly what exists, what runs, and what to do next.

---

## 1. Project Goal

Build a modular ROV software stack that:

- Auto-starts on Raspberry Pi boot (via systemd).
- Provides a professional GUI control station.
- Streams live camera video.
- Later: telemetry, sensors (IMU/depth/compass), thrusters, navigation, failsafe, logging, mission.

Current milestone reached: **A Hydrion Spectra GCS-style control station — a "Dark Ocean"
glassmorphism shell (top app bar, collapsible left nav rail, bottom system footer) around a
camera-first dashboard with live telemetry, plus working module pages (Sensors, Diagnostics,
Logs, Settings, Operations) and placeholders for future sections (Navigation, Manipulator,
Planner, AI Vision). On top of that, **Phase 1 hardware model is done**: the thruster stack now
represents the real 5-thruster ROV (M1–M5) with surge/yaw/heave mixing, per-motor GPIO +
direction config. **Phase 2 Part A is done**: `Esp32ThrusterProvider` + a UART transport push the
mixed M1..M5 setpoints to an ESP32 ESC controller over serial, with ACK/STATUS/HEARTBEAT parsing,
ESTOP and reconnect. Default stays `provider: simulated` — still fully functional with no hardware
attached. Part B (ESP32 firmware) is the next work item.**

---

## 2. Project Structure

```
rov-controller/
├── app/                 # Entry point
│   ├── main.py          # RUNS THE APP (launches GUI)
│   ├── app.py           # (empty placeholder)
│   └── bootstrap.py     # (empty placeholder)
├── core/                # Shared framework
│   ├── base_module.py   # BaseModule class (implemented)
│   ├── application.py   # Application (boots Config+Logger+ServiceManager+Qt)
│   ├── service_manager.py  # ServiceManager (module lifecycle conductor)
│   └── event_bus.py
├── modules/             # Feature modules (mostly placeholders)
│   ├── camera/          # camera_manager.py — REAL (captures + reads frames)
│   ├── sensors/         # sensor_manager.py — REAL (state + apply_motion, simulated provider)
│   ├── telemetry/       # telemetry_manager.py — REAL (JSON frames + heartbeat over a Link)
│   ├── controller/      # controller.py — REAL (MotionState merge: pad/keyboard/link/gamepad)
│   ├── thrusters/       # thruster_manager.py — REAL (5-thruster mixer + simulated provider)
│   │                    #   Esp32ThrusterProvider (Phase 2 Part A) + uart_transport.py (UART frames)
│   ├── navigation/  mission/  manipulator/  watchdog/  diagnostics/   # empty
├── ui/                  # GUI (Hydrion Spectra GCS "Dark Ocean" style)
│   ├── main_window.py   # MainWindow — REAL (app bar + nav rail + footer + workspaces)
│   ├── theme.py         # design tokens (colors/fonts from DESIGN.md) + global QSS
│   ├── glass.py         # GlassPanel / StatusPill / NavButton / ValueRow widgets
│   ├── control_pad.py   # ControlPad3D — REAL (circular joystick + yaw ring, bottom-right)
│   ├── sonar.py         # SonarPanel — REAL (top-right glass map: ship/cable/ROV/ping)
│   ├── hud.py           # HUD overlay — REAL (compass + crosshair + DEPTH/ALT pillars)
│   └── sections.py      # nav pages — REAL (Sensors/Diagnostics/Logs/Settings/Operations) + placeholders
├── configs/             # YAML configs
│   ├── camera.yaml      # camera settings (device/width/height/fps/enabled)
│   ├── hud.yaml         # HUD settings (panel alpha + compass/crosshair/depth-alt + colors)
│   ├── gcs.yaml         # GCS shell (sonar map + telemetry sim values + latency)
│   ├── sensors.yaml     # sensor settings (provider/start heading)
│   ├── network.yaml     # link settings (enabled/link/ip/port/intervals)
│   ├── controller.yaml  # keymap + gamepad codemap
│   ├── thrusters.yaml   # provider/speed + 5-motor map (GPIO=ESP32 pin, direction ±1)
│   ├── navigation.yaml  # (empty)
│   └── mission.yaml     # (empty)
├── systemd/             # rov-controller.service — TEMPLATE rendered by scripts/start.sh (Step 6 ✅)
├── scripts/             # start.sh / stop.sh / restart.sh — install+manage the systemd service (Step 6 ✅)
├── tests/               # test_thruster_mixer.py + test_uart_transport.py (run these!)
├── logs/                # system.log / errors.log / mission.log (runtime — gitignored)
└── .venv/               # Python 3.13 virtualenv with deps installed
```

> **Where this copy lives:** the active dev copy seen by these sessions is
> `/home/riazafridi/Downloads/Hydrion-Spectra-main` — and (since Step 6) this **is the Raspberry Pi
> 5 deployment host**, running directly from this path with its `.venv` present. The original
> deployment path (`/home/theexplorer/¬/rov-controller`) is an older copy. See §3 for setup/venv.

---

## 3. Setup & Dependencies

> This project currently runs on a **Raspberry Pi 5** (aarch64, Debian 13 trixie, systemd 257) at
> `/home/riazafridi/Downloads/Hydrion-Spectra-main`. The `.venv` is present here (recreated
> 2026-09-13 during Step 6). The original deployment path `/home/theexplorer/¬/rov-controller`
> (`¬` is intentional) is an older copy.

Virtualenv: `.venv` (Python 3.13). Installed packages (actual versions in this copy):

| Package        | Version |
|----------------|---------|
| opencv-python  | 5.0.0.93 |
| PySide6        | 6.11.2 |
| pillow         | 12.3.0 |
| PyYAML         | 6.0.3 |
| numpy          | 2.5.3 |
| pyserial       | 3.5   (ESP32 UART link — Phase 2. Optional: app runs without it) |

Activate / re-create:

```bash
cd /home/riazafridi/Downloads/Hydrion-Spectra-main        # <project root>
python3 -m venv .venv                                     # only if .venv is missing
source .venv/bin/activate
pip install opencv-python PySide6 pillow PyYAML numpy pyserial     # only if freshly created
```

> The GUI needs a graphical session. On this Pi that is `DISPLAY=:0` via XWayland; the systemd
> service (§6 step 6 / systemd section below) sets `DISPLAY`, `XAUTHORITY` and
> `QT_QPA_PLATFORM=xcb` for the Qt app automatically.

---

## 4. How to Run

```bash
source .venv/bin/activate
python app/main.py
```

> To run it automatically after boot instead of by hand (on the Pi), use the systemd service —
> see §8 (`bash scripts/start.sh` once, then it auto-starts).

Expected behavior:

1. Console prints `[Camera] Camera opened (device 0)` — or `Failed to open camera device` (this Pi's
   USB camera enumerates as `/dev/video19+`, so `configs/camera.yaml` `device: 0` does not match it;
   point it at the real node to get a live feed).
2. A window **"HYDRION SPECTRA - ROV Controller"** opens (dark navy "Dark Ocean" theme):
   - **Top app bar:** brand, WORKSPACE tab, status pills (BATT / LINK / UP time / MANUAL), avatar.
   - **Left nav rail** (expands on hover): Dashboard, Operations, Navigation, Sensors,
     Manipulator, Diagnostics, Planner, AI Vision, Logs, Settings, and a red LAUNCH MISSION button.
   - **Dashboard:** camera fills the center with overlays — LIVE indicator (top-left), sonar map
     (top-right), system telemetry (below the map), compass + crosshair + DEPTH/ALT pillars drawn
     into the video, control dock (ARMED/REC/SNAP/LIGHTS, bottom-center), circular motion controller
     (bottom-right), hidden mission-log flyout (left edge).
   - **Bottom footer:** FPS / CPU / RAM / STORAGE / DEPTH / LATENCY.
   - The module pages (Sensors, Diagnostics, Logs, Settings, Operations) show real data from the
     modules; Navigation/Manipulator/Planner/AI Vision are placeholders.
3. Drive the simulated ROV (see §5 "Manual control" / "5-thruster model" for the full table):
   - **Pad:** drag the circular stick — vertical = surge (forward/back), horizontal = yaw (turn) —
     springs back on release; the dashed ring spins while turning.
   - **Keyboard:** `W/S` forward/back, `A/D` + `Q/E` turn (yaw), `R/F` up/down (heave — the only way
     to change depth), `I/K` pitch, `J/L` roll (kept for future, no motor), `Shift` boost,
     `Backspace` kill. Keys are ignored while typing in a text field.
   - **Link:** from the surface console, `inject_command("FORWARD 0.5")` → the controller consumes it
     (`LEFT`/`RIGHT` now turn the ROV, since there is no sway thruster).
4. Telemetry + heartbeat frames are appended to `logs/mission.log` (JSON, one per line).
5. `SNAP` saves a frame to `logs/snapshots/`; `LIGHTS` brightens the feed; `ARMED` toggles whether
   any input moves the ROV.
6. Closing the window releases the camera and closes the link cleanly.

If no camera is available, status shows "No Camera Signal" (no crash).

---

## 5. Implemented vs Placeholders

### Implemented (real code)
- `core/base_module.py` — `BaseModule` with `initialize/start/update/stop/health_check`, `name`, `running`,
  and a `logging` logger per module.
- `modules/config/config_manager.py` — `ConfigManager(BaseModule)`: loads every `configs/*.yaml`
  centrally, unwraps the file's top-level key, exposes `get(section, key, default)`,
  `get_section(name)`, `sections()`.
- `modules/logger/logger_manager.py` — `LoggerManager(BaseModule)`: configures console + file logging
  to `logs/system.log` and `logs/errors.log` (ERROR+ only), `get_logger(name)`.
- `modules/camera/camera_manager.py` — `CameraManager(BaseModule)`: opens `cv2.VideoCapture(device)`,
  applies width/height/fps from config, `read_frame() -> BGR ndarray | None`, `stop()` releases.
- `core/service_manager.py` — `ServiceManager`: the "conductor". `register(module)` (any `BaseModule`),
  then `initialize_all/start_all/update_all/stop_all` run the lifecycle in order (stop is reversed),
  each guarded so one module failing doesn't kill the boot. `get(name)`, `modules()`,
  `health_check() -> {name: bool}` (a `None` result counts as OK).
- `core/application.py` — `Application`: top-level bootstrap. `initialize()` boots `ConfigManager`
  + `LoggerManager`, builds modules from config (`CameraManager`, `SensorManager`,
  `TelemetryManager`, `ControllerModule`, `ThrusterManager` — each gated by its section's
  `enabled`), and initializes/starts them via the `ServiceManager`. `run()` then creates the
  `QApplication`, a 100 ms timer that drives `ServiceManager.update_all()`, shows `MainWindow`,
  and shuts everything down on exit (`shutdown()` → `stop_all()`).
- `modules/sensors/sensor_manager.py` — `SensorManager(BaseModule)`: reads IMU/depth/compass through a
  swappable provider, exposes `get_state() -> HudState`. Default `SimulatedSensorProvider`
  (stationary until motion is applied); unknown `provider` config falls back to simulated so it
  always runs. `apply_motion(surge, sway, heave, yaw_rate, dt)` integrates commanded motion into
  `x/y/depth/yaw`. The `HudState` dataclass (`x`, `y`, `depth`, `yaw_deg`) lives here too — the
  sensor module owns the data model, `ui/hud.py` imports it (UI depends on the module, not vice-versa).
- `modules/telemetry/telemetry_manager.py` — `TelemetryManager(BaseModule)`: packs sensor state +
  camera status into JSON frames and sends them over a `Link`, emits heartbeats on an interval, and
  buffers incoming commands (consumed by the controller via `consume_commands()`). `Link` is the
  transport abstraction: `SimulatedLink` (default) appends frames to `logs/mission.log` and accepts
  `inject_command()`; unknown `link` config falls back to simulated. Driven by
  `ServiceManager.update_all()` on a 100 ms Application timer.
- `modules/controller/controller.py` — `ControllerModule(BaseModule)` with the `MotionState` dataclass
  (surge/sway/heave/yaw/pitch/roll/boost). Merges input sources (pad, keyboard, link commands) into
  one motion target — per axis the strongest source wins — and pushes it to the thrusters. Handles
  text link commands (`FORWARD 0.5`, `LEFT`, `UP`, `STOP`, …) and a `kill()` emergency stop.
  `LEFT`/`RIGHT` map to **yaw** (there is no sway thruster).
- `modules/thrusters/thruster_manager.py` — `ThrusterManager(BaseModule)`: 5-thruster model
  (`ThrusterId` enum: M1 front vertical, M2 middle-right horizontal, M3 middle-left horizontal,
  M4 back-right vertical, M5 back-left vertical). Pure `mix()` consumes only surge/yaw/heave
  (M1/M4/M5 = heave, M2 = surge+yaw, M3 = surge−yaw), clamps every motor to [-1,1], and applies
  configurable per-motor `direction` (+1/−1). `ThrusterProvider` ABC → `SimulatedThrusterProvider`
  (active, feeds `SensorManager.apply_motion()`) + `Esp32ThrusterProvider` (Phase 2 Part A, sends
  the mixed setpoints over UART via `modules/thrusters/uart_transport.py`). Per-motor
  GPIO (ESP32 pins) + direction live in `configs/thrusters.yaml` `motors`. `emergency_stop()` zeros
  all five motors independently of the controller, and latches a zeroed ESTOP frame to the ESP32.
  Unknown `provider` config falls back to simulated; `esp32` without hardware stays disconnected.
- `ui/control_pad.py` — `ControlPad3D`: circular glass motion controller (stick = surge/yaw with
  spring-return — no sway on the 5-thruster ROV, animated dashed yaw ring updated from stick drag
  and the keyboard yaw command); emits
  `MotionState` on drag.
- `ui/theme.py` — design tokens (colors, fonts) from the Stitch `DESIGN.md` + the global
  "Dark Ocean" stylesheet applied via `apply_theme(qt_app)`.
- `ui/glass.py` — reusable widgets: `GlassPanel`, `StatusPill`, `NavButton`, `ValueRow`,
  `IconTile`, `SectionPage`.
- `ui/sonar.py` — `SonarPanel`: glass map (ship, dashed umbilical, ROV triangle, animated sonar
  ping) fed from the sensor state.
- `ui/hud.py` — HUD overlays drawn into the video frame: heading compass (top-center), crosshair +
  pitch ladder (center), DEPTH/ALT pillars (left/right middle).
- `ui/sections.py` — nav-rail pages: **Sensors** (depth/heading/position/pitch/roll + health),
  **Diagnostics** (per-module `health_check()` pills, FPS/CPU/RAM/uptime), **Logs** (tails
  `mission.log` + `system.log`), **Settings** (config values), **Operations** (ARM status + link
  command injector); placeholders for Navigation/Manipulator/Planner/AI Vision.
- `app/main.py` — thin entry point: `Application().run()`.
- `ui/main_window.py` — `MainWindow(QMainWindow)`: the GCS shell — top app bar (brand + status
  pills), hover-expanding left nav rail, bottom footer (FPS/CPU/RAM/STORAGE/DEPTH/LATENCY), and a
  stacked workspace. The Dashboard fills the camera (center-cropped to cover), with overlays:
  LIVE pill, sonar map, system telemetry, control dock (ARMED/REC/SNAP/LIGHTS), motion controller,
  and a hidden mission-log flyout. Keyboard shortcuts are captured app-wide via an event filter
  for all movement axes + boost + kill.
- `ui/hud.py` — HUD overlay (see section 6).

### Manual control

| Input | What it drives | Status |
|-------|---------------|--------|
| `ControlPad3D` (mouse) | surge / yaw (+ yaw ring indicator) | ✅ live |
| Keyboard (`configs/controller.yaml` `keymap`) | surge / yaw / heave + boost + kill (pitch/roll keys kept for future) | ✅ live |
| Gamepad (codemap in `controller.yaml` `gamepad`) | mapped axes/buttons | ⏳ future provider |
| Link commands (`FORWARD`, `LEFT`, …) | same motion target | ✅ live |

Heave (up/down) is on the keyboard (**R/F**); the circular pad drives surge/yaw.

**5-thruster ROV (Phase 1):** only surge, yaw and heave are supported. There is no sway thruster —
left/right input (**A/D**, pad stick-x, link `LEFT`/`RIGHT`) turns the vehicle (yaw). Pitch/roll
input is kept in the controller for future stabilization but produces **no** motor command.

Default keys: **W/S** forward/back, **A/D** turn, **R/F** up/down, **Q/E** turn, **I/K** pitch,
**J/L** roll, **Shift** boost, **Backspace** kill (toggle). All reassignable in
`configs/controller.yaml`.

### 5-thruster motion model (Phase 1) — canonical reference

The ROV has **five** thrusters (wiring fixed, ESP32 GPIO already connected — do not change):

| ID | Role | ESP32 GPIO | Mixer equation | Direction |
|----|------|:----------:|----------------|:---------:|
| `M1_FRONT_VERTICAL` | Front vertical | 25 | `heave` | configurable ±1 |
| `M2_MIDDLE_RIGHT_HORIZONTAL` | Middle right | 33 | `surge + yaw` | configurable ±1 |
| `M3_MIDDLE_LEFT_HORIZONTAL` | Middle left | 32 | `surge − yaw` | configurable ±1 |
| `M4_BACK_RIGHT_VERTICAL` | Back right vertical | 27 | `heave` | configurable ±1 |
| `M5_BACK_LEFT_VERTICAL` | Back left vertical | 26 | `heave` | configurable ±1 |

- Supported axes: **surge, yaw, heave**. **No sway** (no lateral thruster). Pitch/roll are **not**
  mixed in Phase 1 (kept in `MotionState` + keyboard for future stabilization, produce zero motor).
- `mix()` in `modules/thrusters/thruster_manager.py` is a **pure function**:
  every motor output = `clamp(equation × direction, -1, 1)`, values in `[-1.0, 1.0]`, direction from
  `configs/thrusters.yaml` → `motors` (`+1` default; flip per-motor only after verifying the real
  mount — never guess in code).
- Example (all directions `+1`): `surge=1` → M2=+1, M3=+1; `yaw=1` → M2=+1, M3=−1; `heave=1` →
  M1/M4/M5=+1; `STOP`/e-stop → all five = 0.
- Provider swap: `ControllerModule` and UI only talk to `ThrusterManager`; the active provider is
  `thrusters.provider` (`simulated` today — default). `Esp32ThrusterProvider` (Phase 2 Part A) sits
  behind the same `ThrusterProvider` ABC and sends the mixed setpoints over the UART link (§7).
  `ThrusterManager.emergency_stop()` zeros all five independently and latches ESTOP to the ESP32.

### Placeholders (empty files, exist for structure)
- `core/event_bus.py`
- `app/app.py`, `app/bootstrap.py`
- `modules/navigation/`, `modules/watchdog/`, `modules/mission/`, `modules/manipulator/`,
  `modules/diagnostics/`
- Empty configs: `navigation.yaml`, `mission.yaml`

> The `systemd/` + `scripts/` placeholders are now **real** (Step 6) — see §8 (auto-start) and the
> tables in §9.

---

## 6. HUD Overlays (ui/hud.py + ui/sonar.py)

The dashboard HUD is split in two: **frame overlays** drawn into the video with OpenCV
(`ui/hud.py`) and the **sonar map** drawn as a Qt glass widget (`ui/sonar.py`) so it stays
aligned with the shell panels.

### Frame overlays (ui/hud.py) — drawn before QImage conversion
- **Compass** (top-center): glass pill with the current heading ± 20°; current value highlighted.
- **Crosshair + pitch ladder** (center): circle + tick marks and +10/−10 pitch lines.
- **DEPTH pillar** (left-middle) and **ALT pillar** (right-middle): vertical glass cards with the
  depth (real) and a sample altitude.
- Panels use a rounded-rect alpha mask; every overlay is toggleable via `configs/hud.yaml`
  (`compass` / `crosshair` / `depth_alt` / `colors`).

### Sonar map (ui/sonar.py) — Qt widget, top-right
- Glass panel with a "SONAR MAP" header, faint grid, the surface ship (blue dot), a dashed
  umbilical from ship to ROV, the ROV (cyan triangle) at the live `x/y` position, and an animated
  expanding sonar ping. Sized/tuned in `configs/gcs.yaml` (`sonar` section).

### Coordinate frame
- Local **ENU**, origin at launch. Sonar map is north-up; the ROV is placed at
  `center + (x, -y) * px_per_m`, clamped to the panel.

### Data flow
```
SensorManager.get_state()          # module -> provider (SimulatedSensorProvider today)
  ->  HudState(x, y, depth, yaw_deg)
HudOverlay.render(frame, state)   ->  frame with overlay        (ui/hud.py)
SonarPanel.set_state(state)       ->  repaint of the map widget (ui/sonar.py)
```
`HudState` is a dataclass (defined in `modules/sensors/sensor_manager.py`): `x` (East m),
`y` (North m), `depth` (m), `yaw_deg` (0 = North, CW+).

### Wiring real sensor data
The sensor pipeline already runs through the real module path: `SensorManager` is registered with the
`ServiceManager` and feeds the HUD as its provider. It reads whichever provider `sensors.provider`
names; today that's `simulated`. To attach real hardware later:
- Add a `RealSensorProvider` (same `get_state()` shape) and register it under the provider name in
  `SensorManager.initialize()`.
- Set `configs/sensors.yaml` → `provider: real` (keep the `simulated` fallback so it still runs if
  the hardware is absent).
- Real sources map to `HudState`: `yaw_deg` ← IMU/compass heading; `depth` ← pressure/depth sensor;
  `x, y` ← integrate velocity (vx·dt, vy·dt) into local XY from launch, or use a position estimate.

Nothing in `HudOverlay`, `SonarPanel` or `MainWindow` changes — only the provider behind the module.

### Performance
Frame overlays only re-compute masks on size changes; dynamic elements are drawn each frame.
Measured headless: well above 30 FPS for sim + render.

### Config reference (`configs/hud.yaml`)
| Key | Meaning | Default |
|-----|---------|---------|
| `enabled` | master switch | `true` |
| `panel_alpha` | glass panel opacity | `0.55` |
| `compass.enabled` | top-center heading pill | `true` |
| `crosshair.enabled` | center crosshair + pitch ladder | `true` |
| `depth_alt.enabled` | DEPTH/ALT side pillars | `true` |
| `colors.primary` (RGB) | ocean-cyan accent `#64FFDA` | `[100, 255, 218]` |
| `colors.secondary` (RGB) | electric-blue `#adc7ff` | `[173, 199, 255]` |

### Config reference (`configs/gcs.yaml`)
| Key | Meaning | Default |
|-----|---------|---------|
| `latency_ms` | footer LATENCY + link pill | `12` |
| `sonar.size` / `range_m` / `grid_lines` | sonar map size & tuning | `220` / `6.0` / `6` |
| `telemetry.*` | sample bus voltage / current / temp / leak (swap for real telemetry later) | see file |

Colors in `hud.yaml` are RGB values; the overlay converts them to BGR (OpenCV convention).

Simulated motion/rate parameters (`speed_mps`, `turn_rate_degps`, `depth_rate_mps`, `start_yaw_deg`)
moved to `configs/sensors.yaml` under `sensors.sim.*`.

---

## 7. Hardware Integration (Simulation-first)

**We develop without physical hardware.** Every sensor/actuator module is written against a clean
interface and currently returns **simulated/dummy values** (random or scripted) so the whole system
runs and is testable headless. Real hardware is attached later by swapping the simulated provider
for a real driver — nothing else in the system changes.

### Pattern

```
SimulatedProvider.get_x()  ->  module consumes x  ->  telemetry / GUI / thrusters
RealProvider.get_x()       ->  same shape, same consumer   (swap ONLY the provider)
```

### Rule for every future feature

Whenever a feature is added, the README must also document:

1. **How the hardware is attached/wired** (model, pins, bus — I2C/SPI/serial, addresses).
2. **What the user edits after attaching it** to get real values (config keys, provider class,
   calibration) — including a fallback so it still runs if the hardware is absent.

### Hardware attachment notes (current status: nothing attached — these are the future swap points)

**Thrusters / motors (5-thruster ROV — Phase 1 + Phase 2 Part A)**
- Final chain: MacBook → Ethernet tether → Raspberry Pi → Hydrion-Spectra → ESP32 → 5 × ESC → 5 ×
  thrusters. The Pi is the high-level computer (**does not** generate PWM); the ESP32 is the
  low-level real-time ESC controller. **Part A (Pi side) is implemented**: `Esp32ThrusterProvider` +
  `uart_transport.py` push the mixed setpoints over serial. **Part B (ESP32 firmware) is the next
  step** — the firmware must speak the same protocol (§7 → "ESP32 UART protocol").
- Wiring (when built): Raspberry Pi USB-UART adapter (TX↔ESP32 RX, RX↔ESP32 TX, common GND) →
  ESP32 → each ESC signal line → an ESP32 PWM-capable GPIO (wiring is already physical and must not
  change): M1 front vertical → GPIO 25, M2 middle right → GPIO 33, M3 middle left → GPIO 32, M4 back
  right → GPIO 27, M5 back left → GPIO 26. ESC power from the battery rail, common ground with the
  Pi/ESP32.
- Motor IDs / GPIO / direction metadata live in `configs/thrusters.yaml` → `motors`
  (`M1_FRONT_VERTICAL`, `M2_MIDDLE_RIGHT_HORIZONTAL`, `M3_MIDDLE_LEFT_HORIZONTAL`,
  `M4_BACK_RIGHT_VERTICAL`, `M5_BACK_LEFT_VERTICAL`), each with `gpio` (ESP32 pin — metadata) and
  `direction` (+1/−1).
- To get real values: set `thrusters.provider: esp32` and point `thrusters.esp32.serial_port` at the
  UART adapter (prefer `/dev/serial/by-id/...`). Nothing else changes — `Esp32ThrusterProvider`
  exposes the same `setpoints()` + `apply()` shape as `SimulatedThrusterProvider`, so switching the
  provider never touches the controller, GUI or telemetry.
- **Fallback (default): `provider: simulated`** — the app runs fully with no ESP32 connected.
  Even with `provider: esp32` and no hardware, the app keeps running: the provider stays
  disconnected, reports `status()` (connected/link_alive/dropped-frames/crc/ack stats) and retries
  reconnects — it never crashes.
- Calibration: ESCs need throttle range calibration on first power-up (see ESC manual). Verify the
  direction of each motor and flip its `direction` in `configs/thrusters.yaml` if mounted reversed —
  never guess the sign in code.

### ESP32 UART protocol (Phase 2 — reference for the ESP32 firmware)

One binary, length-prefixed, CRC-checked frame each direction over the UART. Layout (little-endian):

```
BYTE    FIELD        NOTES
0-1     HEADER       0xAA 0x55 (sync)
2       VERSION      0x01
3       TYPE         0x01 MOTOR_COMMAND (Pi->ESP32) | 0x02 ACK | 0x03 NACK |
                     0x04 STATUS | 0x05 HEARTBEAT (ESP32->Pi)
4       LENGTH       payload bytes (MOTOR_COMMAND payload = 10)
5       SEQUENCE     rolling counter & 0xFF (ACK echoes the command's sequence)
6       FLAGS        bit0 ESTOP (must halt all ESCs); bit1 HEARTBEAT_REQ
7..     PAYLOAD      M1..M5 as int16 * MOTOR_SCALE (MOTOR_SCALE = 1000):
                     normalized -1.0..+1.0 <-> -1000..+1000, little-endian
last-2  CRC16        CRC-16/CCITT-FALSE over bytes 2..end-of-payload
```

- The Pi **always** sends already-mixed, clamped M1..M5 — never surge/yaw/heave.
- ESTOP (FLAGS bit0): the Pi re-issues a zeroed ESTOP frame while e-stop is latched so the ESP32 is
  expected to halt immediately and hold. Design the firmware-side command watchdog: if no fresh
  MOTOR_COMMAND arrives (e.g. 250 ms), the ESP32 should also stop on its own.
- Reference implementation (Python): `modules/thrusters/uart_transport.py` (`build_motor_command`,
  `parse_frame`, `crc16_ccitt`); tests in `tests/test_uart_transport.py`.

**Gamepad / joystick (future)**
- Wiring: USB gamepad (e.g. Xbox/PS style) plugged into the Pi — no GPIO.
- To get real values: set `controller.gamepad.enabled: true` and add a `GamepadProvider` that polls
  the device (e.g. via `pygame`/`sdl2`), mapping axes/buttons by the codemap in
  `configs/controller.yaml` (`gamepad.axes` / `gamepad.buttons` / `gamepad.deadzone`), emitting the
  same `MotionState` the pad and keyboard produce. Fallback: gamepad disabled/absent → pad +
  keyboard still work.

**Sensors / link** — swap points documented in §6 (sensor provider) and the telemetry bullet in §5
(`Link`).

---

## 8. Raspberry Pi Auto-Start (systemd) — Step 6 ✅

The ROV controller auto-starts when the Pi boots into its graphical desktop and restarts if it
crashes.

- **Service name:** `rov-controller.service`
- **Deployment path (this Pi):** `/home/riazafridi/Downloads/Hydrion-Spectra-main`
- **Unit:** `systemd/rov-controller.service` is a **template** — `scripts/start.sh` renders it into
  `/etc/systemd/system/rov-controller.service` using the paths/user/python it **discovers** (project
  root from the script location, service user = project owner, python = `.venv/bin/python`). Nothing
  is hardcoded/guessed.
- **GUI environment:** `scripts/start.sh` also writes `/etc/rov-controller.env` with live-display
  values (DISPLAY / XAUTHORITY / QT_QPA_PLATFORM=xcb) so Qt can open the window. On this Pi that is
  `DISPLAY=:0` via XWayland, `XAUTHORITY=/home/riazafridi/.Xauthority`.
- **Behaviour:** starts after `graphical.target`; `Restart=on-failure`, `RestartSec=5` → crashes
  auto-restart, clean exit / `systemctl stop` does **not** restart (no loop); systemd guarantees a
  single instance; runs as the project owner (never root).

### Commands

| Action | Command |
|--------|---------|
| **Install + start** (renders unit, writes env, enables + starts) | `bash scripts/start.sh` |
| Start (if already installed) | `sudo systemctl start rov-controller.service` |
| Enable at boot | `sudo systemctl enable rov-controller.service` |
| Disable at boot (stop autostart) | `sudo systemctl disable rov-controller.service` |
| Stop (clean, no auto-restart) | `sudo systemctl stop rov-controller.service` |
| Restart | `sudo systemctl restart rov-controller.service` |
| Status / verify | `systemctl status rov-controller.service` |
| Live logs | `journalctl -u rov-controller.service -f` |
| Last 100 log lines | `journalctl -u rov-controller.service -n 100 --no-pager` |

> `scripts/start.sh` / `stop.sh` / `restart.sh` are wrapper helpers that self-promote to root via
> `sudo` and handle install/render/report; they are the recommended entry point
> (`bash scripts/start.sh`, `bash scripts/stop.sh`, `bash scripts/restart.sh`).

### How to verify auto-start after reboot

```bash
sudo reboot            # on the Pi
# after the desktop comes up, wait ~15s, then:
systemctl status rov-controller.service   # should show "active (running)"
systemctl is-enabled rov-controller.service && echo enabled
pgrep -af "[a]pp/main.py"                 # exactly one python app/main.py
journalctl -u rov-controller.service --no-pager -n 100 | grep "Main window shown"
```

The service is considered running only when the last command prints
`Main window shown, entering event loop` (after the GUI connected to the display).

### Step 6 verification performed (2026-09-13, on this Pi)

- `systemd-analyze verify` on the rendered unit — exit 0 (no syntax errors).
- Full runtime lifecycle was exercised with an **identical user-instance** unit (the system-level
  install needs your sudo password): start → **active**, GUI launched
  (`Main window shown, entering event loop`); **crash** (SIGKILL) → auto-restarted with a new PID;
  **stop** → inactive, no restart loop; **restart** → active again; **idempotent re-start** → still
  exactly one instance; app logs captured.
- Existing tests: `python -m unittest tests.test_thruster_mixer -v` → 26/26 OK.
- Manual launch: `.venv/bin/python app/main.py` → runs, GUI shown.
- ⚠️ The **boot-time systemd step itself** (`sudo bash scripts/start.sh`) still needs to be run once
  by you (it requires root); the scripts + unit are verified and ready.

---

## 9. Progress Log & Where We Left Off

### Quick scan — how to resume work

> **State:** everything below runs on this Pi/laptop with simulated/dummy data — real ESP32
> hardware is not attached yet.
> Last finished step: **Phase 2 Part A (ESP32 UART link, Pi side).** Next to do: **Phase 2 Part B
> (ESP32 firmware — parse MOTOR_COMMAND, drive 5 × ESC, ACK/STATUS/HEARTBEAT).**

| # | Step | What it does (plain) | Status |
|---|------|----------------------|--------|
| 0 | GUI + camera + HUD | Window opens, live camera feed, mini-map overlay | ✅ done |
| 1 | Config + Logger | One place loads all config files; proper logging to file | ✅ done |
| 2 | ServiceManager / Application | The "conductor" — starts/stops every module in order | ✅ done |
| 3 | Real telemetry | HUD shows real IMU/depth/compass (simulated for now) | ✅ done |
| 4 | Network / telemetry link | Talks to surface station, heartbeat, commands down | ✅ done |
| 5 | Thrusters / motion | Joystick → navigation → controller → motors (simulated) | ✅ done |
| P1 | **5-thruster hardware model** | Real 5-motor layout mixer (M1–M5) + GPIO/direction config + ESP32 provider seam | ✅ done |
| 6 | systemd auto-start | ROV starts itself on boot, start/stop scripts | ✅ done |
| P2A | ESP32 link (Pi side) | `Esp32ThrusterProvider` → UART transport → MOTOR_COMMAND (M1..M5) + ACK/STATUS/HEARTBEAT parse, ESTOP, reconnect, status() | ✅ done |
| P2B | ESP32 firmware | The ESP32 side: parse MOTOR_COMMAND, drive 5 × ESC PWM, send ACK/STATUS/HEARTBEAT, command watchdog + its own ESTOP | ⏳ **NEXT** |
| + | Safety extras | Watchdog (kill motors on failure), mission routes, claw | ⬜ pending |

### Change record (most recent first)

- **2026-09-13 — Phase 2 Part A: ESP32 UART link (Raspberry Pi side)**
  - `modules/thrusters/uart_transport.py` (new) — pyserial-based transport: open/close/safe-exit,
    non-blocking read pump with partial-frame buffering + header resync, send with short-write
    check + auto-reconnect, receive-side validation (header/version/length/CRC-16/CCITT),
    gracefully degrades when pyserial is missing or the port does not exist.
  - `modules/thrusters/thruster_manager.py` — real `Esp32ThrusterProvider` behind the existing
    `ThrusterProvider` ABC: receives the **already-mixed** M1..M5 setpoints from the manager and
    sends them as MOTOR_COMMAND frames (normalized -1..+1, re-clamped before transmit; int16
    ×1000), rolls a per-frame sequence, parses ACK/STATUS/HEARTBEAT (ack correlation, missing-ack
    count, link-stale detection), exposes everything via `status()` for later telemetry (telemetry
    system untouched). Manager e-stop now latching `notify_estop()` → immediate zeroed ESTOP frame +
    per-tick zero ESTOP keepalive. `apply()` gained an optional `setpoints=` so the provider never
    re-mixes. No controller/`mix()`/`ThrusterId`/simulated-provider changes.
  - `configs/thrusters.yaml` — new `esp32:` block (serial_port / baudrate / timeout_ms /
    command_rate_hz / heartbeat_timeout_ms / reconnect_interval_s); nothing hardcoded in Python.
    Default stays `provider: simulated`; flipping to `esp32` without hardware still runs (disconnected
    state, reconnect retries, no crash).
  - Wire protocol (frame layout, types, flags, CRC) documented in §7 "ESP32 UART protocol" — this is
    the contract the Part B firmware must implement.
  - Added `pyserial` to `config` deps; tests: `tests/test_uart_transport.py` (34 new). Full suite
    60/60 pass; app boots with `provider: simulated` unchanged; esp32-without-hardware integration
    verified (connected=False, frames dropped, warning once). GPIO metadata, mixer and controller
    architecture untouched per the task constraints.
  - ⚠️ **Part B (ESP32 firmware) not done — next block below.**

- **2026-09-13 — Step 6: systemd auto-start (Raspberry Pi, graphical boot)**
  - `systemd/rov-controller.service` — unit **template** (`@ROV_USER@`, `@ROV_DIR@`,
    `@ROV_PYTHON@` tokens), starts after `graphical.target`, `Type=simple`,
    `Restart=on-failure` (crashes restart, clean exit/stop does not), `RestartSec=5`,
    `KillMode=control-group`, runs as the project owner, logging to journald.
  - `scripts/start.sh` (install: self-`sudo`, discovers project root from script location, service
    user = project owner, venv python, writes `/etc/rov-controller.env` with live-session
    DISPLAY/XAUTHORITY/QT_QPA_PLATFORM, renders unit via `sed` with token guards, `daemon-reload`
    + `enable` + `restart`, then `is-active` + `journalctl` on failure), `scripts/stop.sh`
    (stop only, never disables), `scripts/restart.sh`. All `chmod +x`, `bash -n` clean, and
    verified with `systemd-analyze verify` (exit 0).
  - Verified on the Pi (2026-09-13): full lifecycle exercised via an **identical user-instance
    unit** — start → active + GUI shown (`Main window shown, entering event loop`), SIGKILL →
    auto-restart with new PID, stop → inactive (no restart loop), restart → active, idempotent
    start → single instance, app logs captured. Manual launch + all 26 mixer tests pass.
  - ⚠️ Remaining (needs root): run `sudo bash scripts/start.sh` once, then verify after reboot
    (commands in §8). **No Phase 2 work done — ESP32 provider still a stub.**

- **2026-08-07 — Phase 1: 5-thruster hardware model (real ROV layout)**
  - `modules/thrusters/thruster_manager.py` — replaced the 6-motor `MIXING_MATRIX` with the actual
    5-motor ROV: `ThrusterId` enum (M1_FRONT_VERTICAL, M2_MIDDLE_RIGHT_HORIZONTAL,
    M3_MIDDLE_LEFT_HORIZONTAL, M4_BACK_RIGHT_VERTICAL, M5_BACK_LEFT_VERTICAL); pure `mix()`
    consuming only surge/yaw/heave (M1/M4/M5 = heave, M2 = surge+yaw, M3 = surge−yaw), each output
    clamped to [-1,1]; per-motor `direction` (±1) applied at config time (no guessed signs).
    `ThrusterProvider` ABC with `SimulatedThrusterProvider` (active) and `Esp32ThrusterProvider`
    stub (Phase 2 only; setting `provider: esp32` warns + falls back to simulated).
    `ThrusterManager.emergency_stop()` zeros all five motors independently. Sway/pitch/roll never
    produce a motor command.
  - `configs/thrusters.yaml` — `motors` map: GPIO (ESP32 pin, Pi does not drive PWM) + direction:
    M1→25, M2→33, M3→32, M4→27, M5→26.
  - `modules/controller/controller.py` — `LEFT`/`RIGHT` link commands now turn (yaw); sway command
    removed; pitch/roll command slots kept for future but unmixed.
  - `ui/control_pad.py` — pad stick-x now drives yaw (no sway); ring animates on stick drag.
  - `ui/main_window.py` — keyboard **A/D** (+ Q/E) turn the ROV; no sway generated; pitch/roll keys
    retained for future stabilization.
  - `tests/test_thruster_mixer.py` — 26 tests (neutral/stop/6 axes + combos/saturation/unsupported
    sway+pitch+roll/direction flip/e-stop/five-output invariant). Run: `python -m unittest
    tests.test_thruster_mixer -v`.
  - Verified: all tests pass; headless smoke test (config → ThrusterManager GPIO/direction ==
    [25,33,32,27,26]; controller→thrusters→sensors chain drives the sim; e-stop zeroes all motors).
    **No hardware involved, no PWM, no ESP32 networking in Phase 1.**

- **2026-08-06 — Fix: nav-rail hover expand (layout starvation)**
  - Symptom: keeping the cursor on the left sidebar did not expand it, so the icon labels stayed
    clipped (only glyphs visible).
  - Root cause: the dashboard's `camera_view` QLabel reported `sizeHint`/`minimumSizeHint` of
    1384×744 (the full camera pixmap it displays), forcing the stacked workspace to refuse
    shrinking below 1384 px. With a 1440 px window the rail was pinned to its 56 px minimum, so
    it could never visually expand even though the hover logic fired and set the logical state.
  - Fix (`ui/main_window.py`): `camera_view` now uses `QSizePolicy.Ignored` + `setMinimumSize(1, 1)`
    — the pixmap is already center-cropped to fill in `_update_camera`, so the label imposes no
    minimum on the layout. The rail now expands to 208 px on hover, holds while the cursor stays,
    and collapses on leave.
  - Verified on a real display (`QT_QPA_PLATFORM=xcb`, `QCursor.setPos`): rail 56 → 208 on enter,
    stable while hovered, back to 56 on leave.
- **2026-08-06 — UI: Hydrion Spectra GCS redesign (matches `stitch_hydrion_spectra_gcs/` design)**
  - The whole GUI is now a "Dark Ocean" glassmorphism control station derived from the Stitch
    screens (see `stitch_hydrion_spectra_gcs/hydrion_spectra_gcs/DESIGN.md` for the design system).
  - `ui/theme.py` (new) — design tokens + global QSS, applied in `Application.run()`.
  - `ui/glass.py` (new) — `GlassPanel` / `StatusPill` / `NavButton` / `ValueRow` / `SectionPage`.
  - `ui/main_window.py` — rewritten into the GCS shell: top app bar (brand + BATT/LINK/UP/MANUAL
    pills), hover-expanding left nav rail (Dashboard/Operations/Navigation/Sensors/Manipulator/
    Diagnostics/Planner/AI Vision/Logs/Settings + LAUNCH MISSION), bottom footer (FPS/CPU/RAM/
    STORAGE/DEPTH/LATENCY), stacked workspaces. Dashboard = full-bleed camera (center-cropped to
    cover) with overlays: LIVE pill, control dock (ARMED/REC/SNAP/LIGHTS), motion controller,
    mission-log flyout. Keyboard shortcuts ignore typing widgets. ARM state gates all motion input;
    SNAP saves frames to `logs/snapshots/`; LIGHTS brightens the feed.
  - `ui/control_pad.py` — circular glass motion controller (stick = surge/sway, animated yaw ring).
  - `ui/sonar.py` (new) — `SonarPanel` glass map (ship / dashed umbilical / ROV triangle / sonar
    ping), fed live from sensor state.
  - `ui/hud.py` — replaced the trail mini-map with compass + crosshair/pitch-ladder + DEPTH/ALT
    pillars (all toggleable in `configs/hud.yaml`).
  - `ui/sections.py` (new) — nav pages: Sensors, Diagnostics, Logs, Settings, Operations are real;
    Navigation/Manipulator/Planner/AI Vision are styled placeholders until those modules exist.
  - `configs/hud.yaml` rewritten + `configs/gcs.yaml` (new) — shell/sonar/telemetry sample values.
  - `modules/controller/controller.py` — added `last_motion` (exposes commanded pitch/roll/boost to
    the UI).
  - Verified headless: all 10 sections switch, keyboard forward moves the sim, disarm holds,
    pad drag emits sway, SNAP writes a file, boot clean (exit 124 = running).
- **2026-08-06 — Step 5: Thrusters / motion (manual 3D control, keyboard, gamepad codemap)**
  - `modules/controller/controller.py` — `ControllerModule(BaseModule)` + `MotionState`
    (surge/sway/heave/yaw/pitch/roll/boost). Merges input sources per-axis (strongest wins), handles
    link commands (`FORWARD`, `LEFT`, `UP`, `STOP`, …) and a `kill()` emergency stop.
  - `modules/thrusters/thruster_manager.py` — `ThrusterManager(BaseModule)`: `MIXING_MATRIX`
    (X4-vectored horizontal + 2 vertical) → per-thruster setpoints, applied by
    `SimulatedThrusterProvider` → `SensorManager.apply_motion()`. Unknown `provider` falls back to
    simulated.
  - `modules/sensors/sensor_manager.py` — added `apply_motion()` (heading-aware integration into
    x/y/depth/yaw); removed the old scripted auto-drift — the vehicle now only moves on command.
  - `ui/control_pad.py` — `ControlPad3D` (new): joystick = surge/sway, slider = heave, overlaid
    bottom-right of the camera feed, spring-return on release.
  - `ui/main_window.py` — hosts the pad overlay (repositioned on resize) and captures keyboard
    shortcuts app-wide via an event filter (all 6 axes + boost + kill).
  - `configs/controller.yaml` (new) — `keymap` (W/S/A/D/R/F/Q/E/I/K/J/L, Shift boost, Backspace
    kill) + `gamepad` codemap (`axes`/`buttons`/`deadzone`) ready for a future gamepad provider.
  - `configs/thrusters.yaml` (filled) — `provider`, `speed_mps`, `turn_rate_degps`, `layout`.
  - `modules/telemetry/telemetry_manager.py` — incoming commands are now buffered and consumed by
    the controller via `consume_commands()` (still logged).
  - `core/application.py` — registers `ControllerModule` + `ThrusterManager` (registration order
    Camera → Sensors → Telemetry → Controller → Thrusters so the controller feeds the thrusters in
    the same tick); passes controller + keymap into `MainWindow`.
  - Verified: headless chain test (keyboard FORWARD/RIGHT/DOWN/TURN_RIGHT move the simulated state,
    release holds exactly, link command `FORWARD 0.5` moves, `kill()` freezes); GUI offscreen test
    (pad drag emits surge, W-hold drives the ROV forward, Backspace kills); `python app/main.py`
    boots clean.
  - **Hardware note:** no hardware involved. Real thrusters (see §7): swap `thrusters.provider` to a
    PWM/ESC driver; real controller: add a gamepad provider using the `controller.yaml` codemap.
- **2026-08-06 — Step 4: Telemetry link (network / telemetry over the `Link` abstraction)**
  - `modules/telemetry/telemetry_manager.py` — `TelemetryManager(BaseModule)`: packs sensor state +
    camera status into JSON frames, sends them over a `Link` on `telemetry_interval_s`, emits
    `heartbeat` frames on `heartbeat_interval_s`, and logs incoming commands. `Link` is the transport
    abstraction (open/send/receive/close): `SimulatedLink` appends frames to `logs/mission.log` and
    accepts `inject_command()`; unknown `link` config falls back to simulated.
  - `core/application.py` — registers `TelemetryManager` (if `network.enabled`), passing the Sensors +
    Camera modules as its data sources; added a 100 ms `QTimer` that drives
    `ServiceManager.update_all()` so time-based modules tick without blocking the GUI.
  - `configs/network.yaml` — filled in: `enabled`, `link`, `ip`, `port`, `telemetry_interval_s`,
    `heartbeat_interval_s`. Removed the empty `configs/telemetry.yaml` placeholder (network.yaml is
    the single source for the link).
  - Verified: offscreen test (modules: Camera, Sensors, Telemetry; all health OK; telemetry +
    heartbeat frames in `logs/mission.log`; injected commands received and logged) + `python
    app/main.py` boots into the event loop with no errors.
  - **Hardware note:** simulated link only — frames go to a log file. When a real tether is built
    (Ethernet/PoE), add a `SocketLink` under the same `Link` interface and set `network.link` (§7).
- **2026-08-06 — Step 3: Sensors module (real telemetry pipeline, simulated values)**
  - `modules/sensors/sensor_manager.py` — `SensorManager(BaseModule)` with the standard lifecycle and
    `get_state() -> HudState`. Provider abstraction: `SimulatedSensorProvider` (moved from the old
    `SimulatedHudProvider` in `ui/hud.py`); unknown `provider` config falls back to simulated so it
    always runs. `HudState` now lives here — the sensor module owns the telemetry data model and
    `ui/hud.py` imports it.
  - `configs/sensors.yaml` — filled in: `enabled`, `provider`, and the `sim` rate params (moved out of
    `hud.yaml`, whose `sim` block was removed).
  - `core/application.py` — registers `SensorManager` (if `sensors.enabled`) and passes it to
    `MainWindow` as the HUD provider; `SimulatedHudProvider` deleted.
  - Verified: offscreen smoke test (modules: Camera, Sensors; both health OK; HUD renders from module
    data) + `python app/main.py` boots into the event loop with no errors.
  - **Hardware note:** no hardware involved — values are scripted. When a real IMU/pressure sensor is
    attached, add a `RealSensorProvider` and set `sensors.provider` (see §6).
- **2026-08-06 — Step 2: ServiceManager + Application implemented**
  - `core/service_manager.py` — the "conductor": `register(module)` any `BaseModule`, then
    `initialize_all` / `start_all` / `update_all` / `stop_all` (reverse order) run the lifecycle.
    Each step is try/except-guarded so one bad module can't kill the boot. `get(name)`, `modules()`,
    `health_check() -> {name: bool}` (a `None` health result counts as OK).
  - `core/application.py` — `Application` boots Config + Logger, builds modules from config
    (`CameraManager` only if `camera.enabled`), starts them, then creates the `QApplication`,
    `MainWindow` (HUD overlay + simulated provider), and on exit runs `stop_all`.
  - `app/main.py` — reduced to a thin `Application().run()` entry point.
  - `configs/camera.yaml` — added `enabled: true` (per-module on/off switch from config).
  - Also fixed: HUD provider/overlay now receive `{"hud": ...}` so non-default `hud.yaml` values
    are actually respected (previously defaults were used silently).
  - Verified: offscreen smoke test (modules: Camera; health OK; clean stop) + `python app/main.py`
    boots into the event loop with no errors.
  - **Hardware note:** no hardware involved in this step (pure software).
- **2026-08-05 — Step 1: Config + Logger implemented**
  - `modules/config/config_manager.py` — loads every `configs/*.yaml` at once; `get(section, key, default)`,
    `get_section(name)`, `sections()`. Handles the double-wrapped YAML keys (e.g. `camera.yaml` is `camera: {...}`).
  - `modules/logger/logger_manager.py` — console + `logs/system.log` + `logs/errors.log` (ERROR+ only).
  - Replaced all `print()` with `logging`: `core/base_module.py` (logger per module), `camera_manager.py`,
    `app/main.py` (uses the two managers, no more hand-rolled `load_config`).
  - Verified: unit test (all 8 sections load, defaults work, logs written) + headless run (`Camera opened`,
    `Main window shown, entering event loop`).
  - **Hardware note:** no hardware involved in this step (pure software).
- **2026-08-05 — Step 0: Baseline committed**
  - GUI (`ui/main_window.py`), live camera (`modules/camera/camera_manager.py`), HUD overlay (`ui/hud.py`),
    `core/base_module.py`, `app/main.py`, configs. First commit `5a9691a`.
  - Added §7 "Hardware Integration (Simulation-first)" rule: every feature documents how hardware is wired
    and what the user edits to get real data.

### Next session — start here

1. Read this README (§1 goal, §7 sim-first rule + ESP32 UART protocol, §9 this table, §8 auto-start).
2. **Phase 2 Part B — ESP32 firmware (the other end of the UART link):**
   - Implement the ESP32 program against the protocol in §7: parse MOTOR_COMMAND (M1..M5 int16,
     MOTOR_SCALE=1000), drive 5 × ESC PWM on GPIO 25/33/32/27/26, reply ACK (echo sequence) /
     STATUS / HEARTBEAT frames, honor FLAGS ESTOP, and add a command timeout watchdog (~250 ms) so
     the ESP32 stops the ESCs on its own if the Pi link dies.
   - Recommend: MicroPython or Arduino-ESP32 sketch under an `esp32/` folder in this repo; reuse the
     `build_motor_command`/`parse_frame`/`crc16_ccitt` from `uart_transport.py` as the reference.
   - Verify with a Pi↔ESP32 loopback harness (or the `pytest`-style tests already in
     `tests/test_uart_transport.py` acting as a frame fixture), then flip
     `configs/thrusters.yaml` `provider: esp32` on the bench — the app already tolerates a missing
     device.
3. Finish Step 6 verify if not yet done on the Pi: run `sudo bash scripts/start.sh`, reboot, confirm
   per §8.
4. Verify after each step (`python app/main.py`, headless-test snippet in §10). Update this table +
   change record when done.

---

## 10. Working Style (per previous sessions)

Build one small step at a time; verify after each step. Useful commands:

```bash
tree -a -I "__pycache__|*.pyc|.venv"     # view structure
python app/main.py                        # run app
```

To verify the overlay without a camera/display (headless test):

```bash
.venv/bin/python - <<'EOF'
import sys, yaml, numpy as np
sys.path.insert(0, ".")
from ui.hud import HudOverlay
from modules.sensors.sensor_manager import SensorManager
hud_cfg = yaml.safe_load(open("configs/hud.yaml"))
sensor_cfg = yaml.safe_load(open("configs/sensors.yaml"))["sensors"]
o = HudOverlay(hud_cfg)
s = SensorManager(sensor_cfg); s.initialize()
f = np.full((720, 1280, 3), (90, 90, 130), dtype=np.uint8)
import cv2; cv2.imwrite("/tmp/hud.png", o.render(f, s.get_state()))
EOF
```
