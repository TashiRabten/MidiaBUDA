"""TimelineScrubber — Compact timeline with start/end markers and preview."""
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout,
    QSlider, QLabel, QPushButton,
)

from APP.ffmpeg_pro_studio_v2_pillow import format_seconds


class TimelineScrubber(QWidget):
    """Compact timeline with preview scrubber and start/end trim markers.

    Sliders use integer ticks (milliseconds) mapped to float seconds.
    Invariant: start <= end is always enforced via clamping.
    """

    start_changed = pyqtSignal(float)
    end_changed = pyqtSignal(float)
    preview_changed = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._duration_ms = 0

        # --- Sliders ---
        self.preview_slider = QSlider(Qt.Orientation.Horizontal)
        self.start_slider = QSlider(Qt.Orientation.Horizontal)
        self.end_slider = QSlider(Qt.Orientation.Horizontal)

        for s in (self.preview_slider, self.start_slider, self.end_slider):
            s.setRange(0, 0)
            s.setSingleStep(100)
            s.setPageStep(1000)

        # --- Labels (compact) ---
        self.preview_label = QLabel("00:00:00.000")
        self.start_label = QLabel("00:00:00.000")
        self.end_label = QLabel("00:00:00.000")
        for lbl in (self.preview_label, self.start_label, self.end_label):
            lbl.setFixedWidth(90)
            lbl.setStyleSheet("font-size: 10px; font-family: Consolas, monospace;")

        # --- Buttons (small, disabled until media loaded) ---
        self.set_start_btn = QPushButton("I←")
        self.set_end_btn = QPushButton("F←")
        self.set_start_btn.setToolTip("Definir início a partir da posição de prévia")
        self.set_end_btn.setToolTip("Definir fim a partir da posição de prévia")
        self.set_start_btn.setFixedWidth(32)
        self.set_end_btn.setFixedWidth(32)
        self.set_start_btn.setEnabled(False)
        self.set_end_btn.setEnabled(False)
        self.set_start_btn.clicked.connect(self.set_start_from_preview)
        self.set_end_btn.clicked.connect(self.set_end_from_preview)

        # --- Layout: two rows using HBoxLayouts ---
        main = QVBoxLayout(self)
        main.setContentsMargins(0, 2, 0, 0)
        main.setSpacing(2)

        # Row 0: [I←] ═══preview slider═══ [timecode] [F←]
        row0 = QHBoxLayout()
        row0.setSpacing(4)
        row0.addWidget(self.set_start_btn)
        row0.addWidget(self.preview_slider, stretch=1)
        row0.addWidget(self.preview_label)
        row0.addWidget(self.set_end_btn)
        main.addLayout(row0)

        # Row 1: I: [timecode] ═══start═══ | F: [timecode] ═══end═══
        row1 = QHBoxLayout()
        row1.setSpacing(4)
        row1.addWidget(QLabel("I:"))
        row1.addWidget(self.start_label)
        row1.addWidget(self.start_slider, stretch=1)
        row1.addWidget(QLabel("F:"))
        row1.addWidget(self.end_label)
        row1.addWidget(self.end_slider, stretch=1)
        main.addLayout(row1)

        # --- Connections ---
        self.preview_slider.valueChanged.connect(self._on_preview_changed)
        self.start_slider.valueChanged.connect(self._on_start_changed)
        self.end_slider.valueChanged.connect(self._on_end_changed)

    # ── Public API ───────────────────────────────────────────────────

    def set_duration(self, duration: float) -> None:
        """Set the total duration in seconds. Resets all markers."""
        self._duration_ms = max(0, int(duration * 1000))
        for s in (self.preview_slider, self.start_slider, self.end_slider):
            s.blockSignals(True)
            s.setRange(0, self._duration_ms)
            s.blockSignals(False)
        self.start_slider.setValue(0)
        self.end_slider.setValue(self._duration_ms)
        self.preview_slider.setValue(0)
        # Enable buttons now that we have a valid range
        self.set_start_btn.setEnabled(self._duration_ms > 0)
        self.set_end_btn.setEnabled(self._duration_ms > 0)

    def get_start(self) -> float:
        return self.start_slider.value() / 1000.0

    def get_end(self) -> float:
        return self.end_slider.value() / 1000.0

    def get_preview(self) -> float:
        return self.preview_slider.value() / 1000.0

    def set_start_from_preview(self) -> None:
        """Copy preview position to start marker."""
        val = self.preview_slider.value()
        self.start_slider.setValue(val)

    def set_end_from_preview(self) -> None:
        """Copy preview position to end marker."""
        val = self.preview_slider.value()
        self.end_slider.setValue(val)

    # ── Internal slots ───────────────────────────────────────────────

    def _on_preview_changed(self, val_ms: int) -> None:
        self.preview_label.setText(format_seconds(val_ms / 1000.0))
        self.preview_changed.emit(val_ms / 1000.0)

    def _on_start_changed(self, val_ms: int) -> None:
        if val_ms > self.end_slider.value():
            self.end_slider.setValue(val_ms)
        self.start_label.setText(format_seconds(val_ms / 1000.0))
        self.start_changed.emit(val_ms / 1000.0)

    def _on_end_changed(self, val_ms: int) -> None:
        if val_ms < self.start_slider.value():
            self.start_slider.setValue(val_ms)
        self.end_label.setText(format_seconds(val_ms / 1000.0))
        self.end_changed.emit(val_ms / 1000.0)
