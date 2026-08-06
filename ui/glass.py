"""Reusable glass widgets for the GCS shell."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ui.theme import C, FONT_DATA


def caps_label(text):
    label = QLabel(text)
    label.setObjectName("CapsLabel")
    return label


def data_label(text, large=False):
    label = QLabel(text)
    label.setObjectName("DataValueLg" if large else "DataValue")
    return label


class GlassPanel(QFrame):
    """Floating glass card with an optional uppercase title bar."""

    def __init__(self, title=None, parent=None):
        super().__init__(parent)
        self.setObjectName("GlassPanel")
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(10, 8, 10, 10)
        self._layout.setSpacing(6)
        if title is not None:
            self.set_title(title)

    def set_title(self, title):
        bar = QLabel(title)
        bar.setObjectName("GlassTitle")
        bar.setFixedHeight(20)
        self._layout.insertWidget(0, bar)

    def body(self):
        return self._layout

    def add_row(self, widget, stretch=0):
        self._layout.addWidget(widget, stretch)


class StatusPill(QLabel):
    """Pill-shaped status badge."""

    STYLES = {
        "ok": "rgba(100, 255, 218, 0.15)",
        "warn": "rgba(255, 211, 100, 0.15)",
        "bad": "rgba(255, 180, 171, 0.15)",
        "info": "rgba(173, 199, 255, 0.15)",
    }
    TEXT = {"ok": "#64ffda", "warn": "#ffd364", "bad": "#ffb4ab", "info": "#adc7ff"}

    def __init__(self, text="OK", status="ok", parent=None):
        super().__init__(text, parent)
        self.setObjectName("StatusPill")
        self.set_status(status)

    def set_status(self, status):
        self.setStyleSheet(
            f"background-color: {self.STYLES.get(status, self.STYLES['info'])};"
            f"color: {self.TEXT.get(status, self.TEXT['info'])};"
        )


class IconTile(QLabel):
    """Rounded tile holding a unicode glyph (stands in for an icon font)."""

    def __init__(self, glyph, checked=False, parent=None):
        super().__init__(glyph, parent)
        self.setFixedSize(34, 34)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet(
            f"background-color: rgba(100, 255, 218, 0.12); color: {C['primary']};"
            f"border: 1px solid rgba(100, 255, 218, 0.3); border-radius: 8px;"
            f"font-size: 16px;"
        )


class NavButton(QPushButton):
    """Rail button: glyph tile + label. Text hidden when collapsed."""

    def __init__(self, glyph, text, parent=None):
        super().__init__(parent)
        self._glyph = glyph
        self._label = text
        self.setText(f"{glyph}   {text}")
        self.setObjectName("NavBtn")
        self.setCheckable(True)
        self.setMinimumHeight(38)
        self.setCursor(Qt.PointingHandCursor)

    def set_collapsed(self, collapsed):
        self.setText(self._glyph if collapsed else f"{self._glyph}   {self._label}")


class ValueRow(QWidget):
    """Glass card row: caps label left, data value right."""

    def __init__(self, label, value="--", highlight=False, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 6, 10, 6)
        lay.setSpacing(8)
        self._label = caps_label(label)
        self._value = QLabel(value)
        self._value.setStyleSheet(
            f"font-family: {FONT_DATA}; font-size: 14px; "
            f"color: {C['primary'] if highlight else C['secondary']};"
        )
        lay.addWidget(self._label)
        lay.addStretch(1)
        lay.addWidget(self._value)
        self.setStyleSheet(
            f"background: rgba(17, 32, 54, 0.6); border-top: 1px solid "
            f"rgba(100, 255, 218, 0.5); border-radius: 6px;"
        )

    def set_value(self, value):
        self._value.setText(str(value))


class SectionPage(QWidget):
    """Base page: scrollable column of glass panels."""

    def __init__(self, parent=None):
        super().__init__(parent)
        from PySide6.QtWidgets import QScrollArea

        self._scroll = QScrollArea(self)
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.NoFrame)
        inner = QWidget()
        self._col = QVBoxLayout(inner)
        self._col.setContentsMargins(16, 16, 16, 16)
        self._col.setSpacing(12)
        self._col.addStretch(1)
        self._scroll.setWidget(inner)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._scroll)

    def add(self, widget, stretch=0):
        self._col.insertWidget(self._col.count() - 1, widget, stretch)
