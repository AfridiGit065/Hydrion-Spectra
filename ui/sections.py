"""Workspace pages for the GCS nav rail sections."""

from collections import deque
import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ui.glass import GlassPanel, SectionPage, StatusPill, ValueRow, caps_label


class SensorsPage(QWidget):
    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
        page = SectionPage(self)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(page)

        nav_panel = GlassPanel("CORE NAVIGATION")
        self.depth = ValueRow("DEPTH", "--", highlight=True)
        self.heading = ValueRow("HEADING", "--")
        self.pos_x = ValueRow("POSITION X", "--")
        self.pos_y = ValueRow("POSITION Y", "--")
        for r in (self.depth, self.heading, self.pos_x, self.pos_y):
            nav_panel.add_row(r)

        att_panel = GlassPanel("ATTITUDE")
        self.pitch = ValueRow("PITCH", "--")
        self.roll = ValueRow("ROLL", "--")
        self.boost = ValueRow("BOOST", "OFF")
        for r in (self.pitch, self.roll, self.boost):
            att_panel.add_row(r)

        power = GlassPanel("POWER")
        self.bus_v = ValueRow("BUS VOLTAGE", "--")
        self.bus_i = ValueRow("TOTAL CURRENT", "--")
        self.temp = ValueRow("INT TEMP", "--")
        self.leak = ValueRow("LEAK SENSOR", "SAFE")
        for r in (self.bus_v, self.bus_i, self.temp, self.leak):
            power.add_row(r)

        self.health = GlassPanel("SENSOR HEALTH")
        hl = QHBoxLayout()
        hl.setSpacing(8)
        self._health_pills = {}
        for name in ("IMU", "DEPTH", "CAMERA", "LINK"):
            pill = StatusPill(name, "info")
            self._health_pills[name] = pill
            hl.addWidget(pill)
        hl.addStretch(1)
        health_w = QWidget()
        health_w.setLayout(hl)
        self.health.add_row(health_w)

        page.add(nav_panel)
        page.add(att_panel)
        page.add(power)
        page.add(self.health)

    def update(self):
        st = self.ctx["sensors"]
        state = st.get_state() if st is not None else None
        if state is None:
            return
        self.depth.set_value(f"{state.depth:5.2f} m")
        self.heading.set_value(f"{state.yaw_deg:03.0f} deg")
        self.pos_x.set_value(f"{state.x:5.2f} m")
        self.pos_y.set_value(f"{state.y:5.2f} m")
        ctrl = self.ctx["controller"]
        if ctrl is not None:
            m = ctrl.last_motion
            self.pitch.set_value(f"{m.pitch * 60:+.0f}")
            self.roll.set_value(f"{m.roll * 60:+.0f}")
            self.boost.set_value("ON" if m.boost else "OFF")
        for name, pill in self._health_pills.items():
            pill.set_status("ok")


class DiagnosticsPage(QWidget):
    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
        page = SectionPage(self)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(page)

        self.health_panel = GlassPanel("SUBSYSTEM HEALTH")
        self.health_grid = QGridLayout()
        self.health_grid.setSpacing(8)
        self.health_panel.body().addLayout(self.health_grid)
        self._health_pills = {}

        perf = GlassPanel("COMPUTE CORE LOAD")
        self.fps = ValueRow("FPS", "--")
        self.cpu = ValueRow("CPU LOAD", "--")
        self.ram = ValueRow("MEMORY ALLOC", "--")
        self.uptime = ValueRow("UPTIME", "--")
        for r in (self.fps, self.cpu, self.ram, self.uptime):
            perf.add_row(r)

        umb = GlassPanel("UMBILICAL")
        self.latency = ValueRow("LATENCY", "--")
        self.link = ValueRow("LINK STATE", "--")
        for r in (self.latency, self.link):
            umb.add_row(r)

        page.add(self.health_panel)
        page.add(perf)
        page.add(umb)

    def update(self):
        sm = self.ctx["service_manager"]
        if sm is None:
            return
        health = sm.health_check()
        names = set(list(self._health_pills) + list(health))
        col = 0
        for name in sorted(names):
            if name not in self._health_pills:
                pill = StatusPill(name, "info")
                self.health_grid.addWidget(pill, 0, col)
                self._health_pills[name] = pill
                col += 1
            ok = health.get(name)
            pill = self._health_pills[name]
            pill.set_status("ok" if ok else ("bad" if ok is False else "info"))
        self.fps.set_value(self.ctx.get("fps")())
        cpu, ram = self._load()
        self.cpu.set_value(cpu)
        self.ram.set_value(ram)
        self.uptime.set_value(self.ctx.get("uptime")())

    @staticmethod
    def _load():
        try:
            import psutil

            return f"{psutil.cpu_percent():.0f}%", f"{psutil.virtual_memory().percent:.0f}%"
        except Exception:
            return "--", "--"


class LogsPage(QWidget):
    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
        self.mission_path = os.path.join(ctx["log_dir"], "mission.log")
        self.system_path = os.path.join(ctx["log_dir"], "system.log")

        page = SectionPage(self)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(page)

        mission = GlassPanel("MISSION LOG (TELEMETRY)")
        self.mission_box = QTextEdit()
        self.mission_box.setReadOnly(True)
        mission.add_row(self.mission_box)

        system = GlassPanel("SYSTEM LOG")
        self.system_box = QTextEdit()
        self.system_box.setReadOnly(True)
        system.add_row(self.system_box)

        refresh = QPushButton("REFRESH LOGS")
        refresh.clicked.connect(self.update)
        page.add(mission)
        page.add(system)
        page.add(refresh)

    @staticmethod
    def _tail(path, n=80):
        try:
            with open(path) as f:
                return "".join(deque(f, n))
        except FileNotFoundError:
            return "(no log file yet)\n"

    def update(self):
        self.mission_box.setPlainText(self._tail(self.mission_path))
        self.system_box.setPlainText(self._tail(self.system_path))


class SettingsPage(QWidget):
    def __init__(self, ctx):
        super().__init__()
        page = SectionPage(self)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(page)
        cm = ctx["config_manager"]
        if cm is None:
            page.add(GlassPanel("CONFIG"))
            return
        for section in cm.sections():
            data = cm.get_section(section) or {}
            panel = GlassPanel(section.upper())
            for k, v in list(data.items())[:14]:
                panel.add_row(ValueRow(k.replace("_", " ").upper(), str(v)))
            page.add(panel)


class OperationsPage(QWidget):
    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
        page = SectionPage(self)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(page)

        status = GlassPanel("SYSTEM STATUS")
        self.mode = ValueRow("MODE", "MANUAL")
        self.link_pill_row = QWidget()
        row = QHBoxLayout(self.link_pill_row)
        row.setContentsMargins(0, 0, 0, 0)
        self.link_pill = StatusPill("LINK", "info")
        self.armed_pill = StatusPill("DISARMED", "warn")
        row.addWidget(self.link_pill)
        row.addWidget(self.armed_pill)
        row.addStretch(1)
        status.add_row(self.mode)
        status.add_row(self.link_pill_row)

        cmd = GlassPanel("COMMAND CHANNEL")
        self.cmd_input = QTextEdit()
        self.cmd_input.setMaximumHeight(64)
        self.cmd_input.setPlaceholderText('e.g. FORWARD 0.5  (space-separated command)')
        send = QPushButton("SEND COMMAND")
        send.clicked.connect(self._send)
        cmd.add_row(self.cmd_input)
        cmd.add_row(send)

        page.add(status)
        page.add(cmd)

    def _send(self):
        text = self.cmd_input.toPlainText().strip()
        telemetry = self.ctx.get("telemetry")
        if text and telemetry is not None:
            telemetry.inject_command(text)

    def update(self):
        armed = self.ctx.get("armed")()
        self.armed_pill.setText("ARMED" if armed else "DISARMED")
        self.armed_pill.set_status("ok" if armed else "warn")
        self.link_pill.setText("LINK OK" if self.ctx.get("link_ok")() else "LINK DOWN")
        self.link_pill.set_status("ok" if self.ctx.get("link_ok")() else "bad")


class NavigationPage(QWidget):
    def __init__(self, ctx):
        super().__init__()
        page = SectionPage(self)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(page)

        hold = GlassPanel("HOLD CONTROLS (FUTURE)")
        self.depth_hold = QCheckBox("DEPTH HOLD")
        self.depth_set = QSpinBox()
        self.depth_set.setRange(0, 500)
        self.depth_set.setValue(10)
        self.depth_set.setSuffix(" m")
        dh = QWidget()
        row = QHBoxLayout(dh)
        row.addWidget(self.depth_hold)
        row.addWidget(self.depth_set)
        row.addStretch(1)
        self.heading_hold = QCheckBox("HEADING HOLD")
        self.hdg_set = QSpinBox()
        self.hdg_set.setRange(0, 359)
        self.hdg_set.setValue(0)
        self.hdg_set.setSuffix(" deg")
        hh = QWidget()
        row2 = QHBoxLayout(hh)
        row2.addWidget(self.heading_hold)
        row2.addWidget(self.hdg_set)
        row2.addStretch(1)
        hold.add_row(dh)
        hold.add_row(hh)
        page.add(hold)
        wp = GlassPanel("WAYPOINTS")
        wp.add_row(caps_label("No waypoints yet"))
        page.add(wp)


class ManipulatorPage(QWidget):
    def __init__(self, ctx):
        super().__init__()
        page = SectionPage(self)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(page)
        arm = GlassPanel("MANIPULATOR ARM (FUTURE)")
        btns = QWidget()
        row = QHBoxLayout(btns)
        open_b = QPushButton("CLAW OPEN")
        close_b = QPushButton("CLAW CLOSE")
        open_b.setEnabled(False)
        close_b.setEnabled(False)
        row.addWidget(open_b)
        row.addWidget(close_b)
        row.addStretch(1)
        arm.add_row(btns)
        arm.add_row(ValueRow("JAW POSITION", "--"))
        hyd = GlassPanel("HYDRAULICS")
        hyd.add_row(ValueRow("PRESSURE", "--"))
        hyd.add_row(ValueRow("TEMP", "--"))
        hyd.add_row(ValueRow("FLOW RATE", "--"))
        page.add(arm)
        page.add(hyd)


class AIVisionPage(QWidget):
    def __init__(self, ctx):
        super().__init__()
        page = SectionPage(self)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(page)
        det = GlassPanel("OBJECT DETECTION (FUTURE)")
        enable = QCheckBox("ENABLE DETECTION")
        enable.setEnabled(False)
        det.add_row(enable)
        det.add_row(ValueRow("MODEL STATUS", "NOT LOADED"))
        det.add_row(ValueRow("INFERENCE FPS", "--"))
        page.add(det)
        results = GlassPanel("DETECTIONS")
        results.add_row(ValueRow("PIPELINE JOINT", "92%"))
        results.add_row(ValueRow("L. PERTUSA", "88%"))
        results.add_row(ValueRow("UNKNOWN OBJ", "64%"))
        page.add(results)


class PlannerPage(QWidget):
    def __init__(self, ctx):
        super().__init__()
        page = SectionPage(self)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(page)
        page.add(GlassPanel("MISSION BLOCKS (FUTURE)"))
        seq = GlassPanel("SEQUENCE LOGIC")
        seq.add_row(caps_label("No mission loaded"))
        page.add(seq)
        val = GlassPanel("PLAN VALIDATION")
        val.add_row(ValueRow("STATUS", "--"))
        page.add(val)


def build(ctx):
    """Return {key: (title, glyph, widget)} for every non-dashboard section."""
    pages = {}
    for key, cls in (
        ("operations", OperationsPage),
        ("navigation", NavigationPage),
        ("sensors", SensorsPage),
        ("manipulator", ManipulatorPage),
        ("diagnostics", DiagnosticsPage),
        ("planner", PlannerPage),
        ("ai_vision", AIVisionPage),
        ("logs", LogsPage),
        ("settings", SettingsPage),
    ):
        pages[key] = cls(ctx)
    return pages
