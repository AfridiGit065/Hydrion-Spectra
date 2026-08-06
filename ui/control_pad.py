import math

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

from modules.controller.controller import MotionState


class ControlPad3D(QWidget):
    """3-axis manual control: joystick (surge/sway) + vertical slider (heave)."""

    motionChanged = Signal(object)

    PAD_X, PAD_Y, PAD_SIZE = 10, 12, 130
    BAR_W, BAR_GAP = 22, 14
    RADIUS = PAD_SIZE / 2 - 6

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(230, 190)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._joy = QPointF()
        self._heave = 0.0
        self._drag_joy = False
        self._drag_heave = False

    def _bar_rect(self):
        x = self.PAD_X + self.PAD_SIZE + self.BAR_GAP
        return x, self.PAD_Y, self.BAR_W, self.PAD_SIZE

    def _emit(self):
        self.motionChanged.emit(
            MotionState(surge=-self._joy.y(), sway=self._joy.x(), heave=self._heave)
        )

    def _update_joy(self, pos):
        cx = self.PAD_X + self.PAD_SIZE / 2
        cy = self.PAD_Y + self.PAD_SIZE / 2
        dx = (pos.x() - cx) / self.RADIUS
        dy = (pos.y() - cy) / self.RADIUS
        length = math.hypot(dx, dy)
        if length > 1.0:
            dx, dy = dx / length, dy / length
        self._joy = QPointF(dx, dy)
        self._emit()
        self.update()

    def _update_heave(self, pos):
        bx, by, bw, bh = self._bar_rect()
        half = bh / 2 - 10
        mid = by + bh / 2
        self._heave = max(-1.0, min(1.0, (mid - pos.y()) / half))
        self._emit()
        self.update()

    def mousePressEvent(self, event):
        pos = event.position()
        if self._joy.isNull() and self.PAD_X <= pos.x() <= self.PAD_X + self.PAD_SIZE \
                and self.PAD_Y <= pos.y() <= self.PAD_Y + self.PAD_SIZE:
            self._drag_joy = True
            self._update_joy(pos)
        elif pos.x() >= self._bar_rect()[0]:
            self._drag_heave = True
            self._update_heave(pos)
        event.accept()

    def mouseMoveEvent(self, event):
        pos = event.position()
        if self._drag_joy:
            self._update_joy(pos)
        elif self._drag_heave:
            self._update_heave(pos)
        event.accept()

    def mouseReleaseEvent(self, event):
        if self._drag_joy:
            self._drag_joy = False
            self._joy = QPointF()
            self._emit()
        if self._drag_heave:
            self._drag_heave = False
            self._heave = 0.0
            self._emit()
        self.update()
        event.accept()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QColor(20, 25, 30, 210))
        p.setPen(QPen(QColor(120, 140, 160), 1))
        p.drawRoundedRect(1, 1, self.width() - 2, self.height() - 2, 8, 8)

        cx = self.PAD_X + self.PAD_SIZE / 2
        cy = self.PAD_Y + self.PAD_SIZE / 2

        p.setBrush(QColor(30, 40, 50))
        p.drawEllipse(QPointF(cx, cy), self.RADIUS, self.RADIUS)
        p.setPen(QPen(QColor(90, 110, 130), 1))
        p.drawLine(int(cx - self.RADIUS), int(cy), int(cx + self.RADIUS), int(cy))
        p.drawLine(int(cx), int(cy - self.RADIUS), int(cx), int(cy + self.RADIUS))

        p.setPen(QPen(QColor(0, 200, 180), 2))
        knob = self._joy * self.RADIUS
        p.drawEllipse(QPointF(cx + knob.x(), cy + knob.y()), 13, 13)

        bx, by, bw, bh = self._bar_rect()
        p.setBrush(QColor(30, 40, 50))
        p.drawRoundedRect(bx, by, bw, bh, 4, 4)
        mid = by + bh / 2
        if abs(self._heave) > 0.01:
            knob_y = mid - self._heave * (bh / 2 - 10)
        else:
            knob_y = mid
        p.setBrush(QColor(0, 180, 220))
        p.drawRoundedRect(bx + 2, int(knob_y) - 9, bw - 4, 18, 3, 3)

        p.setPen(QPen(QColor(200, 215, 225), 1))
        p.drawText(self.PAD_X, self.PAD_Y - 3, "FWD")
        p.drawText(int(cx - 18), self.PAD_Y + self.PAD_SIZE + 14, "BACK")
        p.drawText(self.PAD_X + self.PAD_SIZE + 8, int(cy) - 5, "UP")
        p.drawText(self.PAD_X + self.PAD_SIZE + 8, int(cy) + 15, "DOWN")
        p.end()
