import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from PySide6.QtWidgets import QApplication

from modules.camera.camera_manager import CameraManager
from modules.config.config_manager import ConfigManager
from modules.logger.logger_manager import LoggerManager
from ui.hud import HudOverlay, SimulatedHudProvider
from ui.main_window import MainWindow


def main():
    config_manager = ConfigManager()
    config_manager.initialize()

    logger_manager = LoggerManager(level=config_manager.get("logger", "level", "INFO"))
    logger_manager.initialize()
    log = logger_manager.get_logger("app")

    camera_config = config_manager.get_section("camera")
    hud_config = config_manager.get_section("hud")

    app = QApplication(sys.argv)

    camera = CameraManager(camera_config)
    camera.initialize()
    camera.start()

    hud_provider = SimulatedHudProvider(hud_config)
    overlay = HudOverlay(hud_config)

    window = MainWindow(camera, overlay=overlay, hud_provider=hud_provider)
    window.show()

    log.info("Main window shown, entering event loop")
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
