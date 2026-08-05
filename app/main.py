import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

import yaml

from PySide6.QtWidgets import QApplication

from modules.camera.camera_manager import CameraManager
from ui.hud import HudOverlay, SimulatedHudProvider
from ui.main_window import MainWindow


def load_config(name):
    path = os.path.join(PROJECT_ROOT, "configs", name)
    with open(path) as f:
        return yaml.safe_load(f)


def main():
    camera_config = load_config("camera.yaml").get("camera", {})
    hud_config = load_config("hud.yaml")

    app = QApplication(sys.argv)

    camera = CameraManager(camera_config)
    camera.initialize()
    camera.start()

    hud_provider = SimulatedHudProvider(hud_config)
    overlay = HudOverlay(hud_config)

    window = MainWindow(camera, overlay=overlay, hud_provider=hud_provider)
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
