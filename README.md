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

Current milestone reached: **GUI window opens with live camera feed + top-right HUD mini-map,
fed by the sensors module (simulated IMU/depth/compass through the real pipeline).**

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
│   ├── sensors/         # sensor_manager.py — REAL (IMU/depth/compass via provider, simulated now)
│   ├── controller/  telemetry/  navigation/
│   ├── thrusters/  mission/  manipulator/  watchdog/
│   ├── diagnostics/  logger/  config/      # all empty
├── ui/                  # GUI
│   ├── main_window.py   # MainWindow — REAL (camera view + status bar + HUD hook)
│   └── hud.py           # HUD overlay — REAL (mini-map + trail + heading)
├── configs/             # YAML configs
│   ├── camera.yaml      # camera settings (device/width/height/fps/enabled)
│   ├── hud.yaml         # HUD settings (size/colors/trail)
│   ├── sensors.yaml     # sensor settings (provider/sim rates)
│   ├── network.yaml     # network settings
│   └── telemetry/thrusters/navigation/mission.yaml  # empty
├── systemd/             # rov-controller.service (empty — not set up yet)
├── scripts/             # start.sh / stop.sh / restart.sh (empty)
├── tests/               # (empty)
├── logs/                # system.log / errors.log / mission.log
└── .venv/               # Python 3.13 virtualenv with deps installed
```

---

## 3. Setup & Dependencies

Virtualenv: `.venv` (Python 3.13). Installed packages:

| Package        | Version |
|----------------|---------|
| opencv-python  | 5.0.0.93 |
| PySide6        | 6.11.1 |
| pillow         | 12.3.0 |
| PyYAML         | 6.0.3 |
| numpy          | 2.5.1 |

To re-activate the environment:

```bash
cd "/home/theexplorer/¬/rov-controller"
source .venv/bin/activate
```

> Note: project lives in `/home/theexplorer/¬/rov-controller` (the `¬` in the path is intentional).

---

## 4. How to Run

```bash
source .venv/bin/activate
python app/main.py
```

Expected behavior:

1. Console prints `[Camera] Camera opened (device 0)`.
2. A window **"Underwater ROV Controller"** opens:
   - Left: "Telemetry Panel (Placeholder)".
   - Center: live camera feed.
   - Top-right: HUD mini-map overlay (grid, ROV dot, cyan trail, heading arrow, DEPTH/HDG labels).
   - Status bar: `Status: Camera Connected | FPS: -- | Mode: Manual`.
3. Closing the window releases the camera cleanly.

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
  + `LoggerManager`, builds modules from config (`CameraManager` if `camera.enabled`,
  `SensorManager` if `sensors.enabled`), and initializes/starts them via the `ServiceManager`.
  `run()` then creates the `QApplication`, shows `MainWindow`, and shuts everything down on exit
  (`shutdown()` → `stop_all()`).
- `modules/sensors/sensor_manager.py` — `SensorManager(BaseModule)`: reads IMU/depth/compass through a
  swappable provider, exposes `get_state() -> HudState`. Default `SimulatedSensorProvider` (scripted
  values); unknown `provider` config falls back to simulated so it always runs. The `HudState`
  dataclass (`x`, `y`, `depth`, `yaw_deg`) lives here too — the sensor module owns the data model,
  `ui/hud.py` imports it (UI depends on the module, not vice-versa).
- `app/main.py` — thin entry point: `Application().run()`.
- `ui/main_window.py` — `MainWindow(QMainWindow)`: layout (left panel + camera view + status bar),
  `QTimer` polling camera at ~30 fps, converts BGR → QImage → QPixmap, calls HUD overlay before display.
- `ui/hud.py` — HUD overlay (see section 6).

### Placeholders (empty files, exist for structure)
- `core/event_bus.py`
- `app/app.py`, `app/bootstrap.py`
- All `modules/*` managers except camera, config, logger, sensors
- `systemd/rov-controller.service`, `scripts/*.sh`
- Empty configs: `telemetry.yaml`, `thrusters.yaml`, `navigation.yaml`, `mission.yaml`

---

## 6. HUD Mini-Map Overlay (ui/hud.py)

Top-right 2D local plan-view overlay drawn onto the video frame with OpenCV (before QImage conversion).

### Components
- **Panel**: 220x220 px (config), semi-transparent dark background (`panel_alpha`), cached grid.
- **Grid**: light-gray thin lines (`grid_lines` cells per side), cached for performance.
- **ROV marker**: white dot at map center.
- **Trail**: cyan polyline of last `N` position samples using a ring buffer
  (`collections.deque(maxlen=points)`).
- **Heading arrow**: green arrow from ROV marker at compass yaw.
- **Labels**: `DEPTH xx.xx m` and `HDG xxx°` in a small translucent strip below the map, with drop shadow.

### Coordinate frame
- Local **ENU**, origin at launch. Map is world-fixed (north-up).
- ROV pinned at map center; trail points are translated relative to current position.
- Heading arrow: screen angle = `-yaw` (screen Y is down), arrow tip = `center + (sin yaw, -cos yaw) * length`.

### Data flow
```
SensorManager.get_state()          # module -> provider (SimulatedSensorProvider today)
  ->  HudState(x, y, depth, yaw_deg)
HudOverlay.render(frame, state)   ->  frame with overlay
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

Nothing in `HudOverlay` or `MainWindow` changes — only the provider behind the module.

### Performance
Background (panel + grid) is pre-rendered once and cached per frame size; only dynamic elements are
drawn each frame. Measured headless: **~109 FPS** for sim + render (target ≥30 FPS).

### Config reference (`configs/hud.yaml`)
| Key | Meaning | Default |
|-----|---------|---------|
| `enabled` | master switch | `true` |
| `size` | mini-map side length (px) | `220` |
| `margin` | gap from frame edges (px) | `12` |
| `range_m` | half-width shown on map (m) | `6.0` |
| `panel_alpha` | background opacity | `0.45` |
| `grid_lines` | grid cells per side | `5` |
| `trail.seconds` / `trail.points` | trail window; ring buffer maxlen | `20` / `600` |
| `trail.color` (BGR) | cyan | `[255, 255, 0]` |
| `arrow.length` / `arrow.thickness` / `arrow.color` | heading arrow | `28` / `2` / green |
| `rov.color` / `rov.radius` | ROV marker | white / `4` |
| `text.*` | label font size/color | see file |

All colors in the YAML are **BGR** (OpenCV convention).

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

---

## 8. Progress Log & Where We Left Off

### Quick scan — how to resume work

> **State:** everything below runs on a laptop with simulated/dummy data — no hardware attached yet.
> Last finished step: **Step 3 (Real telemetry — sensor module).** Next to do: **Step 4 (Network / telemetry link).**

| # | Step | What it does (plain) | Status |
|---|------|----------------------|--------|
| 0 | GUI + camera + HUD | Window opens, live camera feed, mini-map overlay | ✅ done |
| 1 | Config + Logger | One place loads all config files; proper logging to file | ✅ done |
| 2 | ServiceManager / Application | The "conductor" — starts/stops every module in order | ✅ done |
| 3 | Real telemetry | HUD shows real IMU/depth/compass (simulated for now) | ✅ done |
| 4 | Network / telemetry link | Talks to surface station, heartbeat, commands down | ⏳ **NEXT** |
| 4 | Network / telemetry link | Talks to surface station, heartbeat, commands down | ⬜ pending |
| 5 | Thrusters / motion | Joystick → navigation → controller → motors (simulated) | ⬜ pending |
| 6 | systemd auto-start | ROV starts itself on boot, start/stop scripts | ⬜ pending |
| + | Safety extras | Watchdog (kill motors on failure), mission routes, claw | ⬜ pending |

### Change record (most recent first)

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

1. Read this README (§1 goal, §7 sim-first rule, §8 this table).
2. **Implement Step 4**: network / telemetry link — `modules/telemetry/telemetry_manager.py`
   (a `BaseModule` that packs sensor state + camera health into a lightweight frame and talks to the
   surface station over the link in `configs/network.yaml`: host/port, heartbeat interval, protocol).
   Simulated link first (loopback/log) with a provider-style swap to real sockets later.
3. Verify after each step (`python app/main.py`, headless test snippet in §9).
4. When done, update this table (move Step 4 to ✅), add a change-record line, and commit.

---

## 9. Working Style (per previous sessions)

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
