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

Current milestone reached: **GUI window opens with live camera feed + top-right HUD mini-map overlay.**

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
│   ├── application.py   # (empty placeholder)
│   ├── service_manager.py
│   └── event_bus.py
├── modules/             # Feature modules (mostly placeholders)
│   ├── camera/          # camera_manager.py — REAL (captures + reads frames)
│   ├── controller/  sensors/  telemetry/  navigation/
│   ├── thrusters/  mission/  manipulator/  watchdog/
│   ├── diagnostics/  logger/  config/      # all empty
├── ui/                  # GUI
│   ├── main_window.py   # MainWindow — REAL (camera view + status bar + HUD hook)
│   └── hud.py           # HUD overlay — REAL (mini-map + trail + heading)
├── configs/             # YAML configs
│   ├── camera.yaml      # camera settings (device/width/height/fps)
│   ├── hud.yaml         # HUD settings (size/colors/trail/sim)
│   ├── network.yaml     # network settings
│   └── sensors/telemetry/thrusters/navigation/mission.yaml  # empty
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
- `ui/main_window.py` — `MainWindow(QMainWindow)`: layout (left panel + camera view + status bar),
  `QTimer` polling camera at ~30 fps, converts BGR → QImage → QPixmap, calls HUD overlay before display.
- `ui/hud.py` — HUD overlay (see section 6).
- `app/main.py` — boots `ConfigManager` + `LoggerManager`, loads configs, creates `QApplication`,
  `CameraManager`, `HudOverlay`, `SimulatedHudProvider`, shows `MainWindow`.

### Placeholders (empty files, exist for structure)
- `core/application.py`, `core/service_manager.py`, `core/event_bus.py`
- `app/app.py`, `app/bootstrap.py`
- All `modules/*` managers except camera, config, logger
- `systemd/rov-controller.service`, `scripts/*.sh`
- Empty configs: `sensors.yaml`, `telemetry.yaml`, `thrusters.yaml`, `navigation.yaml`, `mission.yaml`

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
SimulatedHudProvider.get_state()  ->  HudState(x, y, depth, yaw_deg)
HudOverlay.render(frame, state)   ->  frame with overlay
```
`HudState` is a dataclass: `x` (East m), `y` (North m), `depth` (m), `yaw_deg` (0 = North, CW+).

### Wiring real sensor data (future)
Replace `SimulatedHudProvider` in `app/main.py` with a provider returning `HudState` from real sources:
- `yaw_deg` ← IMU/compass heading.
- `depth` ← pressure/depth sensor.
- `x, y` ← integrate velocity (vx·dt, vy·dt) into local XY from launch, or use a position estimate.

Nothing in `HudOverlay` or `MainWindow` changes — only the provider.

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
| `sim.*` | simulated provider params | see file |

All colors in the YAML are **BGR** (OpenCV convention).

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
> Last finished step: **Step 1 (Config + Logger).** Next to do: **Step 2 (ServiceManager/Application).**

| # | Step | What it does (plain) | Status |
|---|------|----------------------|--------|
| 0 | GUI + camera + HUD | Window opens, live camera feed, mini-map overlay | ✅ done |
| 1 | Config + Logger | One place loads all config files; proper logging to file | ✅ done |
| 2 | ServiceManager / Application | The "conductor" — starts/stops every module in order | ⏳ **NEXT** |
| 3 | Real telemetry | HUD shows real IMU/depth/compass (simulated for now) | ⬜ pending |
| 4 | Network / telemetry link | Talks to surface station, heartbeat, commands down | ⬜ pending |
| 5 | Thrusters / motion | Joystick → navigation → controller → motors (simulated) | ⬜ pending |
| 6 | systemd auto-start | ROV starts itself on boot, start/stop scripts | ⬜ pending |
| + | Safety extras | Watchdog (kill motors on failure), mission routes, claw | ⬜ pending |

### Change record (most recent first)

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
2. **Implement Step 2**: `core/service_manager.py` (create/start/update/stop/health-check all modules from
   config) and `core/application.py` (boots Config+Logger+ServiceManager+Qt). Wire into `app/main.py`.
3. Verify after each step (`python app/main.py`, headless test snippet in §9).
4. When done, update this table (move Step 2 to ✅), add a change-record line, and commit.

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
from ui.hud import HudOverlay, SimulatedHudProvider
cfg = yaml.safe_load(open("configs/hud.yaml"))
p = SimulatedHudProvider(cfg); o = HudOverlay(cfg)
f = np.full((720, 1280, 3), (90, 90, 130), dtype=np.uint8)
import cv2; cv2.imwrite("/tmp/hud.png", o.render(f, p.get_state()))
EOF
```
