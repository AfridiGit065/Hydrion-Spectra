import cv2
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)


class MainWindow(QMainWindow):
    def __init__(self, camera_manager, overlay=None, hud_provider=None):
        super().__init__()
        self.camera = camera_manager
        self.overlay = overlay
        self.hud_provider = hud_provider
        self.setWindowTitle("Underwater ROV Controller")
        self.resize(1280, 720)

        self._build_ui()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_camera)
        self.timer.start(33)

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

        camera_box = QWidget()
        camera_layout = QVBoxLayout(camera_box)
        camera_layout.setContentsMargins(0, 0, 0, 0)

        self.camera_view = QLabel("LIVE CAMERA FEED")
        self.camera_view.setAlignment(Qt.AlignCenter)
        self.camera_view.setStyleSheet(
            "background-color: #1e1e1e; color: #888888; font-weight: bold;"
        )
        self.camera_view.setMinimumSize(640, 480)
        camera_layout.addWidget(self.camera_view)

        root.addWidget(self.left_panel)
        root.addWidget(camera_box, 1)

        self.setCentralWidget(central)

        status = QStatusBar()
        self.setStatusBar(status)
        self.status_label = QLabel("Status: Initializing...")
        self.fps_label = QLabel("FPS: --")
        self.mode_label = QLabel("Mode: Manual")
        status.addWidget(self.status_label)
        status.addPermanentWidget(self.fps_label)
        status.addPermanentWidget(self.mode_label)

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
        self._update_camera()

    def closeEvent(self, event):
        self.timer.stop()
        self.camera.stop()
        event.accept()
