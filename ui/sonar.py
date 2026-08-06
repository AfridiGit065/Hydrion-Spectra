"""Sonar map glass panel (Qt widget so it stays aligned with the shell panels).

Draws the ship, umbilical cable, ROV position and an animated sonar ping.
"""

import math
import time

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QWidget

from ui.theme import C


class SonarPanel(QWidget):
    def __init__(self, parent=None, size=220, range_m=6.0, grid_lines=6):
        super().__init__(parent)
        self._state = None
        self._t0 = time.time()
        self._grid = grid_lines
        self._px = (size - 24) / 2 / range_m
        self.setFixedSize(size, size + 24)
        self._anim = QTimer(self)
        self._anim.timeout.connect(self.update)
        self._anim.start(60)

    def set_state(self, state):
        self._state = state

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        panel = QRectF(0, 0, w - 1, h - 1)
        p.setBrush(QColor(17, 34, 64, 190))
        p.setPen(QPen(QColor(100, 255, 218, 60), 1))
        p.drawRoundedRect(panel, 10, 10)

        head = QRectF(2, 2, w - 4, 20)
        p.fillRect(head, QColor(39, 53, 76, 150))
        p.setPen(QColor(214, 227, 255))
        f = p.font()
        f.setPointSize(7)
        f.setBold(True)
        p.setFont(f)
        p.drawText(QRectF(10, 2, 120, 20), Qt.AlignVCenter | Qt.AlignLeft, "SONAR MAP")
        p.setPen(QColor(100, 255, 218))
        p.drawEllipse(QPointF(w - 22, 12), 5, 5)
        p.drawLine(QPointF(w - 22, 12), QPointF(w - 19, 9))

        gy0 = 24
        cell = (w - 2) / self._grid
        p.setPen(QPen(QColor(100, 255, 218, 30), 1))
        for i in range(1, self._grid):
            x = 1 + i * cell
            p.drawLine(QPointF(x, gy0), QPointF(x, h - 1))
            y = gy0 + i * cell
            p.drawLine(QPointF(1, y), QPointF(w - 1, y))

        cx, cy = w / 2, gy0 + (h - gy0) / 2
        ship = QPointF(cx, gy0 + 14)
        p.setBrush(QColor(173, 199, 255))
        p.setPen(Qt.NoPen)
        p.drawEllipse(ship, 3, 3)

        rx, ry = cx, cy
        if self._state is not None:
            rx = cx + self._state.x * self._px
            ry = cy - self._state.y * self._px
        rx = max(8, min(w - 8, rx))
        ry = max(gy0 + 8, min(h - 8, ry))
        rov = QPointF(rx, ry)

        p.setPen(QPen(QColor(173, 199, 255, 110), 1))
        p.setBrush(Qt.NoBrush)
        pen = p.pen()
        pen.setDashPattern([3, 3])
        p.setPen(pen)
        p.drawLine(ship, rov)
        p.setPen(QPen(QColor(100, 255, 218), 1))
        p.setBrush(QColor(100, 255, 218))
        tri = QPolygonF([
            QPointF(rov.x(), rov.y() - 9),
            QPointF(rov.x() + 8, rov.y() + 8),
            QPointF(rov.x() - 8, rov.y() + 8),
        ])
        p.drawPolygon(tri)

        t = (time.time() - self._t0) % 2.4
        pr = 10 + t / 2.4 * 30
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(100, 255, 218, 110), 1))
        p.drawEllipse(rov, pr, pr)
        p.drawEllipse(rov, max(2.0, pr - 10), max(2.0, pr - 10))
        p.end()
