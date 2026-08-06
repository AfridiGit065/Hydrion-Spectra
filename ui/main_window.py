import cv2
from PySide6.QtCore import QEvent, Qt, QTimer
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from modules.controller.controller import MotionState
from ui.control_pad import ControlPad3D


class MainWindow(QMainWindow):
    def __init__(self, camera_manager, overlay=None, hud_provider=None,
                 controller=None, keymap=None):
        super().__init__()
        self.camera = camera_manager
        self.overlay = overlay
        self.hud_provider = hud_provider
        self.controller = controller
        self.key_speed = 1.0
        self._pressed_actions = set()
        self._key_actions = self._build_keymap(keymap or {})
        self.setWindowTitle("Underwater ROV Controller")
        self.resize(1280, 720)

        self._build_ui()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_camera)
        self.timer.start(33)

        QApplication.instance().installEventFilter(self)

    def _build_keymap(self, keymap):
        actions = {}
        for action, name in keymap.items():
            if name is None:
                continue
            key = getattr(Qt.Key, f"Key_{name}", None)
            if key is not None:
                actions[key] = action
        return actions

    def _build_ui(self):
        central = QWidget()
        root = QHBoxLayout(central)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        self.left_panel = QLabel("Telemetry Panel\n\n(Placeholder)")
        self.left_panel.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        self.left_panel.setFrameShape(QFrame.StyledPanel)
        self.left_panel.setMinimumWidth(220)
        self.left_panel.setWordWrap(True)

        self.camera_container = QWidget()
        camera_layout = QVBoxLayout(self.camera_container)
        camera_layout.setContentsMargins(0, 0, 0, 0)

        self.camera_view = QLabel("LIVE CAMERA FEED")
        self.camera_view.setAlignment(Qt.AlignCenter)
        self.camera_view.setStyleSheet(
            "background-color: #1e1e1e; color: #888888; font-weight: bold;"
        )
        self.camera_view.setMinimumSize(640, 480)
        camera_layout.addWidget(self.camera_view)

        self.pad = ControlPad3D(self.camera_container)
        if self.controller is not None:
            self.pad.motionChanged.connect(
                lambda motion: self.controller.set_input("pad", motion)
            )

        root.addWidget(self.left_panel)
        root.addWidget(self.camera_container, 1)

        self.setCentralWidget(central)

        status = QStatusBar()
        self.setStatusBar(status)
        self.status_label = QLabel("Status: Initializing...")
        self.fps_label = QLabel("FPS: --")
        self.mode_label = QLabel("Mode: Manual")
        status.addWidget(self.status_label)
        status.addPermanentWidget(self.fps_label)
        status.addPermanentWidget(self.mode_label)

        self._reposition_pad()

    def _reposition_pad(self):
        self.pad.move(
            self.camera_container.width() - self.pad.width() - 8,
            self.camera_container.height() - self.pad.height() - 8,
        )
        self.pad.raise_()

    def _axis(self, action_pos, action_neg):
        return ((action_pos in self._pressed_actions) - (action_neg in self._pressed_actions)) \
            * self.key_speed

    def _keyboard_state(self):
        return MotionState(
            surge=self._axis("forward", "back"),
            sway=self._axis("right", "left"),
            heave=self._axis("up", "down"),
            yaw=self._axis("yaw_right", "yaw_left"),
            pitch=self._axis("pitch_up", "pitch_down"),
            roll=self._axis("roll_right", "roll_left"),
            boost="boost" in self._pressed_actions,
        )

    def _handle_key(self, key, pressed):
        action = self._key_actions.get(key)
        if action is None:
            return
        if action == "kill":
            if pressed and self.controller is not None:
                self.controller.kill()
            return
        if pressed:
            self._pressed_actions.add(action)
        else:
            self._pressed_actions.discard(action)
        if self.controller is not None:
            self.controller.set_input("keyboard", self._keyboard_state())

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.KeyPress:
            self._handle_key(event.key(), True)
        elif event.type() == QEvent.Type.KeyRelease:
            self._handle_key(event.key(), False)
        return super().eventFilter(obj, event)

    def _update_camera(self):
        frame = self.camera.read_frame()
        if frame is None:
            self.status_label.setText("Status: No Camera Signal")
            return
        if self.hud_provider is not None:
            state = self.hud_provider.get_state()
            if self.overlay is not None:
                frame = self.overlay.render(frame, state)
        self.status_label.setText("Status: Camera Connected")
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        image = QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(image)
        pixmap = pixmap.scaled(
            self.camera_view.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        self.camera_view.setPixmap(pixmap)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._reposition_pad()
        self._update_camera()

    def closeEvent(self, event):
        self.timer.stop()
        self.camera.stop()
        event.accept()
