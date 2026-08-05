import cv2

from core.base_module import BaseModule


class CameraManager(BaseModule):
    def __init__(self, config=None):
        super().__init__("Camera")
        self.config = config or {}
        self.capture = None

    def initialize(self):
        super().initialize()
        device = self.config.get("device", 0)
        width = self.config.get("width", 1280)
        height = self.config.get("height", 720)
        fps = self.config.get("fps", 30)

        self.capture = cv2.VideoCapture(device)
        if not self.capture.isOpened():
            print("[Camera] Failed to open camera device")
            self.capture = None
            return

        self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        self.capture.set(cv2.CAP_PROP_FPS, fps)
        print(f"[Camera] Camera opened (device {device})")

    def read_frame(self):
        if self.capture is None:
            return None
        ok, frame = self.capture.read()
        if not ok:
            return None
        return frame

    def stop(self):
        super().stop()
        if self.capture is not None:
            self.capture.release()
            self.capture = None
            print("[Camera] Camera released")
