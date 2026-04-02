"""ExportSettingsGroup — Shared encoding settings for MediaBUDA.

All UI text in Portuguese.
"""
from PyQt6.QtWidgets import (
    QGroupBox, QFormLayout, QHBoxLayout,
    QComboBox, QLineEdit, QLabel,
)


# Valid codec/container combinations
VALID_COMBOS = {
    "mp4": {"vcodec": ["libx264", "libx265", "mpeg4"], "acodec": ["aac", "libmp3lame", "copy"]},
    "mkv": {"vcodec": ["libx264", "libx265", "mpeg4"], "acodec": ["aac", "libmp3lame", "copy", "flac", "opus"]},
    "mov": {"vcodec": ["libx264", "libx265", "mpeg4"], "acodec": ["aac", "copy"]},
    "avi": {"vcodec": ["libx264", "mpeg4"], "acodec": ["libmp3lame", "copy"]},
    "webm": {"vcodec": ["libvpx", "libvpx-vp9"], "acodec": ["libopus", "libvorbis", "copy"]},
    "gif": {"vcodec": ["gif"], "acodec": []},
}


def validate_export_settings(vcodec: str, acodec: str, container: str) -> str | None:
    """Validate codec/container compatibility.

    Returns None if valid, or an error message string if invalid.
    """
    combos = VALID_COMBOS.get(container)
    if combos is None:
        return None  # Unknown container — allow anything
    valid_v = combos.get("vcodec", [])
    valid_a = combos.get("acodec", [])
    errors = []
    if valid_v and vcodec not in valid_v:
        errors.append(f"Codec de vídeo '{vcodec}' não é compatível com o contêiner '{container}'")
    if valid_a and acodec not in valid_a and acodec != "copy":
        errors.append(f"Codec de áudio '{acodec}' não é compatível com o contêiner '{container}'")
    return "; ".join(errors) if errors else None


class ExportSettingsGroup(QGroupBox):
    """Shared export settings: codecs, CRF, preset, bitrate, container.

    Checkable group box — when unchecked the grid content is hidden
    but the title bar stays visible.  Starts collapsed by default.
    """

    def __init__(self, parent=None):
        super().__init__("Configurações de exportação", parent)

        # Make the title bar a toggle
        self.setCheckable(True)
        self.setChecked(False)  # start collapsed

        from PyQt6.QtWidgets import QGridLayout
        grid = QGridLayout(self)
        grid.setSpacing(6)
        grid.setContentsMargins(6, 8, 6, 6)

        # Row 0: Video codec | Audio codec | CRF
        grid.addWidget(QLabel("Vídeo:"), 0, 0)
        self.vcodec_combo = QComboBox()
        self.vcodec_combo.addItems(["libx264", "libx265", "mpeg4"])
        grid.addWidget(self.vcodec_combo, 0, 1)

        grid.addWidget(QLabel("Áudio:"), 0, 2)
        self.acodec_combo = QComboBox()
        self.acodec_combo.addItems(["aac", "libmp3lame", "copy"])
        grid.addWidget(self.acodec_combo, 0, 3)

        grid.addWidget(QLabel("CRF:"), 0, 4)
        self.crf_combo = QComboBox()
        self.crf_combo.addItems(["14", "18", "20", "23", "28"])
        self.crf_combo.setCurrentText("18")
        grid.addWidget(self.crf_combo, 0, 5)

        # Row 1: Preset | Bitrate | Container
        grid.addWidget(QLabel("Preset:"), 1, 0)
        self.preset_combo = QComboBox()
        self.preset_combo.addItems(["ultrafast", "veryfast", "fast", "medium", "slow"])
        self.preset_combo.setCurrentText("medium")
        grid.addWidget(self.preset_combo, 1, 1)

        grid.addWidget(QLabel("Bitrate:"), 1, 2)
        self.abitrate_combo = QComboBox()
        self.abitrate_combo.addItems(["96k", "128k", "192k", "256k", "320k"])
        self.abitrate_combo.setCurrentText("192k")
        grid.addWidget(self.abitrate_combo, 1, 3)

        grid.addWidget(QLabel("Formato:"), 1, 4)
        self.container_combo = QComboBox()
        self.container_combo.addItems(["mp4", "mkv", "mov", "avi", "webm"])
        grid.addWidget(self.container_combo, 1, 5)

        # Row 2: Extra args (spans full width)
        grid.addWidget(QLabel("Args:"), 2, 0)
        self.extra_args_edit = QLineEdit()
        self.extra_args_edit.setPlaceholderText("Argumentos extras do FFmpeg...")
        grid.addWidget(self.extra_args_edit, 2, 1, 1, 5)

        # Row 3: Validation label
        self.validation_label = QLabel("")
        self.validation_label.setStyleSheet("color: red; font-size: 10px;")
        grid.addWidget(self.validation_label, 3, 0, 1, 6)

        # Auto-validate on change
        for combo in (self.vcodec_combo, self.acodec_combo, self.container_combo):
            combo.currentTextChanged.connect(self._validate)

        # Keep references to all content widgets so we can show/hide them
        self._content_widgets = [
            self.vcodec_combo, self.acodec_combo, self.crf_combo,
            self.preset_combo, self.abitrate_combo, self.container_combo,
            self.extra_args_edit, self.validation_label,
        ]
        # Also grab the QLabel children already added to the grid
        for i in range(grid.count()):
            w = grid.itemAt(i).widget()
            if w is not None and w not in self._content_widgets:
                self._content_widgets.append(w)

        # Wire toggle
        self.toggled.connect(self._on_toggled)
        self._on_toggled(self.isChecked())  # apply initial state

    def _on_toggled(self, checked: bool):
        """Show or hide the grid content when the group box is toggled."""
        for w in self._content_widgets:
            w.setVisible(checked)

    def get_settings(self) -> dict:
        """Return current settings as a dict matching Job fields."""
        return {
            "vcodec": self.vcodec_combo.currentText(),
            "acodec": self.acodec_combo.currentText(),
            "crf": self.crf_combo.currentText(),
            "preset": self.preset_combo.currentText(),
            "abitrate": self.abitrate_combo.currentText(),
            "container": self.container_combo.currentText(),
            "extra_args": self.extra_args_edit.text().strip(),
        }

    def _validate(self):
        s = self.get_settings()
        err = validate_export_settings(s["vcodec"], s["acodec"], s["container"])
        self.validation_label.setText(err or "")
