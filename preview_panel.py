"""PreviewPanel — Embedded video frame preview widget."""
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QLabel


def scale_keeping_ratio(orig_w: int, orig_h: int, max_w: int, max_h: int) -> tuple[int, int]:
    """Scale (orig_w, orig_h) to fit within (max_w, max_h) preserving aspect ratio.

    Returns (scaled_w, scaled_h). Both inputs must be > 0.
    """
    if orig_w <= 0 or orig_h <= 0 or max_w <= 0 or max_h <= 0:
        return (0, 0)
    ratio = min(max_w / orig_w, max_h / orig_h)
    sw = max(1, min(max_w, round(orig_w * ratio)))
    sh = max(1, min(max_h, round(orig_h * ratio)))
    return (sw, sh)


class PreviewPanel(QLabel):
    """Displays video preview frames, scaling to fit available space."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._original_pixmap: QPixmap | None = None
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(320, 60)
        self.setMaximumHeight(250)
        self.setStyleSheet(
            "background-color: #1a1a2e; color: #999; font-size: 14px; "
            "border: 1px solid #B8860B; border-radius: 6px;"
        )
        self.setText("🎬  Nenhuma mídia carregada — arraste um arquivo ou clique em Procurar")

    def set_frame(self, pixmap: QPixmap) -> None:
        """Store original pixmap and display scaled version."""
        self._original_pixmap = pixmap
        self.setMinimumHeight(180)
        self.setMaximumHeight(400)
        self._update_display()

    def clear_frame(self) -> None:
        """Reset to placeholder state."""
        self._original_pixmap = None
        self.setMinimumHeight(60)
        self.setMaximumHeight(250)
        self.setText("🎬  Nenhuma mídia carregada — arraste um arquivo ou clique em Procurar")

    def resizeEvent(self, event) -> None:
        """Re-scale pixmap to fit new size while preserving aspect ratio."""
        super().resizeEvent(event)
        if self._original_pixmap is not None:
            self._update_display()

    def _update_display(self) -> None:
        if self._original_pixmap is None:
            return
        scaled = self._original_pixmap.scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.setPixmap(scaled)
