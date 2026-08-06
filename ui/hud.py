import math
from collections import deque

import cv2
import numpy as np

from modules.sensors.sensor_manager import HudState


class HudOverlay:
    def __init__(self, config):
        cfg = config.get("hud", {})
        self.enabled = cfg.get("enabled", True)
        self.size = cfg.get("size", 220)
        self.margin = cfg.get("margin", 12)
        self.range_m = cfg.get("range_m", 6.0)
        self.panel_alpha = cfg.get("panel_alpha", 0.45)
        self.grid_lines = cfg.get("grid_lines", 5)
        self.grid_thickness = cfg.get("grid_thickness", 1)
        self.grid_color = self._color(cfg.get("grid_color", [200, 200, 200]))

        trail = cfg.get("trail", {})
        self.trail_seconds = trail.get("seconds", 20)
        self.trail_points = trail.get("points", 600)
        self.trail_color = self._color(trail.get("color", [255, 255, 0]))
        self.trail_thickness = trail.get("thickness", 2)
        self.trail_marker_radius = trail.get("marker_radius", 2)

        rov = cfg.get("rov", {})
        self.rov_color = self._color(rov.get("color", [255, 255, 255]))
        self.rov_radius = rov.get("radius", 4)

        arrow = cfg.get("arrow", {})
        self.arrow_length = arrow.get("length", 28)
        self.arrow_thickness = arrow.get("thickness", 2)
        self.arrow_color = self._color(arrow.get("color", [0, 255, 0]))

        text = cfg.get("text", {})
        self.text_color = self._color(text.get("color", [255, 255, 255]))
        self.shadow_color = self._color(text.get("shadow_color", [0, 0, 0]))
        self.text_scale = text.get("scale", 0.45)
        self.text_thickness = text.get("thickness", 1)

        self.px_per_m = (self.size / 2.0) / self.range_m
        self.trail = deque(maxlen=self.trail_points)
        self._bg = None
        self._bg_shape = None

    @staticmethod
    def _color(value):
        return tuple(int(v) for v in value)

    def update(self, state):
        if self.enabled:
            self.trail.append((state.x, state.y))

    def _rect(self, w, h):
        x0 = w - self.size - self.margin
        y0 = self.margin
        x1 = x0 + self.size
        y1 = y0 + self.size
        return x0, y0, x1, y1

    def _build_background(self, w, h):
        if self._bg is not None and self._bg_shape == (w, h):
            return
        self._bg_shape = (w, h)
        bg = np.zeros((h, w, 3), dtype=np.uint8)
        x0, y0, x1, y1 = self._rect(w, h)
        cv2.rectangle(bg, (x0, y0), (x1, y1), (20, 20, 20), -1)
        cell = self.size / self.grid_lines
        for i in range(1, self.grid_lines):
            p = int(round(x0 + i * cell))
            cv2.line(bg, (p, y0), (p, y1), self.grid_color, self.grid_thickness)
            q = int(round(y0 + i * cell))
            cv2.line(bg, (x0, q), (x1, q), self.grid_color, self.grid_thickness)
        self._bg = bg

    def _draw_text(self, frame, text, org, color=None):
        cv2.putText(
            frame, text, (org[0] + 1, org[1] + 1),
            cv2.FONT_HERSHEY_SIMPLEX, self.text_scale, self.shadow_color,
            self.text_thickness + 1, cv2.LINE_AA,
        )
        cv2.putText(
            frame, text, org,
            cv2.FONT_HERSHEY_SIMPLEX, self.text_scale, color or self.text_color,
            self.text_thickness, cv2.LINE_AA,
        )

    def render(self, frame, state):
        if not self.enabled or frame is None:
            return frame

        self.update(state)
        h, w = frame.shape[:2]
        if h < self.size + 40 or w < self.size + 40:
            return frame

        self._build_background(w, h)
        x0, y0, x1, y1 = self._rect(w, h)
        cx, cy = (x0 + x1) // 2, (y0 + y1) // 2

        panel = self._bg[y0:y1, x0:x1]
        frame[y0:y1, x0:x1] = cv2.addWeighted(
            frame[y0:y1, x0:x1], 1.0 - self.panel_alpha, panel, self.panel_alpha, 0
        )

        if len(self.trail) > 1:
            pts = []
            for px, py in self.trail:
                sx = int(round(cx + (px - state.x) * self.px_per_m))
                sy = int(round(cy - (py - state.y) * self.px_per_m))
                pts.append((sx, sy))
            arr = np.array(pts, dtype=np.int32).reshape(-1, 1, 2)
            cv2.polylines(frame, [arr], False, self.trail_color, self.trail_thickness)
            for sx, sy in pts:
                cv2.circle(frame, (sx, sy), self.trail_marker_radius,
                           self.trail_color, -1)

        cv2.circle(frame, (cx, cy), self.rov_radius, self.rov_color, -1)

        rad = math.radians(state.yaw_deg)
        ex = int(round(cx + math.sin(rad) * self.arrow_length))
        ey = int(round(cy - math.cos(rad) * self.arrow_length))
        cv2.arrowedLine(frame, (cx, cy), (ex, ey), self.arrow_color,
                        self.arrow_thickness, tipLength=0.3)

        strip_y0 = y1 + self.margin
        strip_h = 18
        strip_y1 = strip_y0 + strip_h
        if strip_y1 <= h:
            strip = np.full((strip_h, x1 - x0, 3), (20, 20, 20), dtype=np.uint8)
            region = frame[strip_y0:strip_y1, x0:x1]
            frame[strip_y0:strip_y1, x0:x1] = cv2.addWeighted(
                region, 1.0 - self.panel_alpha, strip, self.panel_alpha, 0
            )
            baseline = strip_y0 + 13
            self._draw_text(frame, f"DEPTH {state.depth:5.2f} m", (x0 + 8, baseline))
            self._draw_text(frame, f"HDG {state.yaw_deg:3.0f}", (x0 + self.size // 2 + 4, baseline))

        return frame
