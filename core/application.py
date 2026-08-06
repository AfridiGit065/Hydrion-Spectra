import sys

from PySide6.QtWidgets import QApplication

from core.service_manager import ServiceManager
from modules.camera.camera_manager import CameraManager
from modules.config.config_manager import ConfigManager
from modules.logger.logger_manager import LoggerManager
from modules.sensors.sensor_manager import SensorManager
from ui.hud import HudOverlay
from ui.main_window import MainWindow


class Application:
    """Top-level bootstrap: wires config, logger, services, and the Qt GUI."""

    def __init__(self, argv=None, configs_dir=None, log_dir=None):
        self.argv = list(argv) if argv is not None else sys.argv
        self.config_manager = ConfigManager(configs_dir)
        self.logger_manager = LoggerManager(log_dir)
        self.service_manager = ServiceManager()
        self.qt_app = None
        self.main_window = None
        self.log = None

    def initialize(self):
        self.config_manager.initialize()
        self.logger_manager.initialize()
        self.log = self.logger_manager.get_logger("app")
        self._build_modules()
        self.service_manager.initialize_all()
        self.service_manager.start_all()

    def _build_modules(self):
        camera_config = self.config_manager.get_section("camera")
        if self.config_manager.get("camera", "enabled", True):
            self.service_manager.register(CameraManager(camera_config))
        if self.config_manager.get("sensors", "enabled", True):
            self.service_manager.register(
                SensorManager(self.config_manager.get_section("sensors"))
            )

    def create_window(self):
        hud_config = {"hud": self.config_manager.get_section("hud")}
        camera = self.service_manager.get("Camera")
        sensors = self.service_manager.get("Sensors")
        return MainWindow(
            camera,
            overlay=HudOverlay(hud_config),
            hud_provider=sensors,
        )

    def run(self):
        self.initialize()
        self.qt_app = QApplication(self.argv)
        self.main_window = self.create_window()
        self.main_window.show()
        self.log.info("Main window shown, entering event loop")
        try:
            exit_code = self.qt_app.exec()
        finally:
            self.shutdown()
        return exit_code

    def shutdown(self):
        self.service_manager.stop_all()
        if self.log is not None:
            self.log.info("Application shutdown complete")
