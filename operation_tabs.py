"""Operation tab widgets for MediaBUDA.

Each tab is a QWidget subclass with build_job / get_ffmpeg_cmd interface.
All UI text in Portuguese.
"""
import shlex
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QComboBox, QCheckBox, QLabel, QSpinBox, QSlider,
    QListWidget, QPushButton, QRadioButton, QButtonGroup,
    QFileDialog, QAbstractItemView,
)

from APP.ffmpeg_pro_studio_v2_pillow import (
    Job, FFmpegBackend, format_seconds, safe_stem,
    VIDEO_EXTS, AUDIO_EXTS,
)


class BaseOperationTab(QWidget):
    """Base class for operation tabs."""

    tab_label: str = ""

    def build_job(self, input_path: str, output_dir: str, media_info: dict,
                  start_time: float, end_time: float,
                  export_settings: dict) -> Job:
        """Construct a Job from this tab's current settings."""
        raise NotImplementedError

    def get_ffmpeg_cmd(self, backend: FFmpegBackend, job: Job, out_path: str) -> list[str]:
        """Build the FFmpeg command for this operation."""
        raise NotImplementedError


class TrimTab(BaseOperationTab):
    """Trim tab — Between/Before/After with re-encode toggle."""

    tab_label = "Cortar"

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QFormLayout(self)

        self.operation_combo = QComboBox()
        self.operation_combo.addItems(["Between", "Before", "After"])
        layout.addRow("Operação:", self.operation_combo)

        self.reencode_check = QCheckBox("Re-codificar (recomendado para cortes precisos)")
        self.reencode_check.setChecked(True)
        layout.addRow(self.reencode_check)

    def build_job(self, input_path, output_dir, media_info, start_time, end_time, export_settings):
        return Job(
            input_path=input_path, output_dir=output_dir,
            operation=self.operation_combo.currentText(),
            start_time=start_time, end_time=end_time,
            duration=media_info.get("duration", 0),
            reencode=self.reencode_check.isChecked(),
            vcodec=export_settings.get("vcodec", "libx264"),
            acodec=export_settings.get("acodec", "aac"),
            crf=export_settings.get("crf", "18"),
            preset=export_settings.get("preset", "medium"),
            abitrate=export_settings.get("abitrate", "192k"),
            extra_args=export_settings.get("extra_args", ""),
            container=export_settings.get("container", "mp4"),
            title=f"Cortar ({self.operation_combo.currentText()})",
        )

    def get_ffmpeg_cmd(self, backend, job, out_path):
        return backend.build_trim_cmd(job, out_path)


class ConvertTab(BaseOperationTab):
    """Convert tab — format presets and codec selectors."""

    tab_label = "Converter"

    PRESETS = {
        "Web (MP4 H.264)": {"container": "mp4", "vcodec": "libx264", "crf": "23", "preset": "medium"},
        "Arquivo (MKV H.265)": {"container": "mkv", "vcodec": "libx265", "crf": "20", "preset": "slow"},
        "Móvel": {"container": "mp4", "vcodec": "libx264", "crf": "28", "preset": "fast"},
        "GIF": {"container": "gif", "vcodec": "gif", "crf": "0", "preset": "medium"},
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QFormLayout(self)

        self.preset_combo = QComboBox()
        self.preset_combo.addItems(list(self.PRESETS.keys()))
        layout.addRow("Predefinição:", self.preset_combo)

        self.format_combo = QComboBox()
        self.format_combo.addItems(["mp4", "mkv", "mov", "avi", "webm", "gif"])
        layout.addRow("Formato de saída:", self.format_combo)

        self.preset_combo.currentTextChanged.connect(self._on_preset_changed)
        self._on_preset_changed(self.preset_combo.currentText())

    def _on_preset_changed(self, name):
        p = self.PRESETS.get(name, {})
        fmt = p.get("container", "mp4")
        idx = self.format_combo.findText(fmt)
        if idx >= 0:
            self.format_combo.setCurrentIndex(idx)

    def build_job(self, input_path, output_dir, media_info, start_time, end_time, export_settings):
        p = self.PRESETS.get(self.preset_combo.currentText(), {})
        return Job(
            input_path=input_path, output_dir=output_dir,
            operation="Convert",
            start_time=0, end_time=media_info.get("duration", 0),
            duration=media_info.get("duration", 0),
            reencode=True,
            vcodec=p.get("vcodec", export_settings.get("vcodec", "libx264")),
            acodec=export_settings.get("acodec", "aac"),
            crf=p.get("crf", export_settings.get("crf", "18")),
            preset=p.get("preset", export_settings.get("preset", "medium")),
            abitrate=export_settings.get("abitrate", "192k"),
            extra_args=export_settings.get("extra_args", ""),
            container=self.format_combo.currentText(),
            title=f"Converter → {self.format_combo.currentText().upper()}",
        )

    def get_ffmpeg_cmd(self, backend, job, out_path):
        return backend.build_trim_cmd(job, out_path)


class MergeTab(BaseOperationTab):
    """Merge tab — file list with add/remove/reorder."""

    tab_label = "Mesclar"

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        self.file_list = QListWidget()
        self.file_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        layout.addWidget(self.file_list)

        btn_row = QHBoxLayout()
        self.add_btn = QPushButton("Adicionar")
        self.remove_btn = QPushButton("Remover")
        self.up_btn = QPushButton("↑")
        self.down_btn = QPushButton("↓")
        for b in (self.add_btn, self.remove_btn, self.up_btn, self.down_btn):
            btn_row.addWidget(b)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.add_btn.clicked.connect(self._add_files)
        self.remove_btn.clicked.connect(self._remove_selected)
        self.up_btn.clicked.connect(self._move_up)
        self.down_btn.clicked.connect(self._move_down)

    def _add_files(self):
        exts = VIDEO_EXTS + AUDIO_EXTS
        filter_str = "Arquivos de mídia (" + " ".join(f"*{e}" for e in exts) + ")"
        paths, _ = QFileDialog.getOpenFileNames(self, "Adicionar arquivos", "", filter_str)
        for p in paths:
            self.file_list.addItem(p)

    def _remove_selected(self):
        for item in self.file_list.selectedItems():
            self.file_list.takeItem(self.file_list.row(item))

    def _move_up(self):
        row = self.file_list.currentRow()
        if row > 0:
            item = self.file_list.takeItem(row)
            self.file_list.insertItem(row - 1, item)
            self.file_list.setCurrentRow(row - 1)

    def _move_down(self):
        row = self.file_list.currentRow()
        if row < self.file_list.count() - 1:
            item = self.file_list.takeItem(row)
            self.file_list.insertItem(row + 1, item)
            self.file_list.setCurrentRow(row + 1)

    def get_file_paths(self) -> list[str]:
        return [self.file_list.item(i).text() for i in range(self.file_list.count())]

    def build_job(self, input_path, output_dir, media_info, start_time, end_time, export_settings):
        paths = self.get_file_paths()
        files_str = "|".join(paths) if paths else input_path
        return Job(
            input_path=files_str, output_dir=output_dir,
            operation="Merge",
            start_time=0, end_time=0, duration=0,
            reencode=True,
            vcodec=export_settings.get("vcodec", "libx264"),
            acodec=export_settings.get("acodec", "aac"),
            crf=export_settings.get("crf", "18"),
            preset=export_settings.get("preset", "medium"),
            abitrate=export_settings.get("abitrate", "192k"),
            extra_args=export_settings.get("extra_args", ""),
            container=export_settings.get("container", "mp4"),
            title="Mesclar arquivos",
        )

    def get_ffmpeg_cmd(self, backend, job, out_path):
        # Concat demuxer approach
        import tempfile
        paths = job.input_path.split("|")
        concat_file = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False)
        for p in paths:
            concat_file.write(f"file '{p}'\n")
        concat_file.close()
        cmd = [
            backend.ffmpeg, "-y", "-hide_banner", "-progress", "pipe:1", "-nostats",
            "-f", "concat", "-safe", "0", "-i", concat_file.name,
            "-c", "copy", out_path,
        ]
        return cmd


class ExtractAudioTab(BaseOperationTab):
    """Extract Audio tab — format and bitrate selectors."""

    tab_label = "Extrair Áudio"

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QFormLayout(self)

        self.format_combo = QComboBox()
        self.format_combo.addItems(["mp3", "wav", "flac", "aac"])
        layout.addRow("Formato:", self.format_combo)

        self.bitrate_combo = QComboBox()
        self.bitrate_combo.addItems(["96k", "128k", "192k", "256k", "320k"])
        self.bitrate_combo.setCurrentText("192k")
        layout.addRow("Bitrate:", self.bitrate_combo)

    def build_job(self, input_path, output_dir, media_info, start_time, end_time, export_settings):
        fmt = self.format_combo.currentText()
        codec_map = {"mp3": "libmp3lame", "wav": "pcm_s16le", "flac": "flac", "aac": "aac"}
        return Job(
            input_path=input_path, output_dir=output_dir,
            operation="ExtractAudio",
            start_time=start_time, end_time=end_time,
            duration=media_info.get("duration", 0),
            reencode=True,
            vcodec="none",
            acodec=codec_map.get(fmt, "aac"),
            crf="0",
            preset="medium",
            abitrate=self.bitrate_combo.currentText(),
            extra_args=export_settings.get("extra_args", ""),
            container=fmt,
            title=f"Extrair Áudio → {fmt.upper()}",
        )

    def get_ffmpeg_cmd(self, backend, job, out_path):
        cmd = [
            backend.ffmpeg, "-y", "-hide_banner", "-progress", "pipe:1", "-nostats",
            "-i", job.input_path, "-vn",
            "-c:a", job.acodec, "-b:a", job.abitrate,
        ]
        if job.start_time > 0:
            cmd[4:4] = ["-ss", format_seconds(job.start_time)]
        if job.end_time > 0 and job.end_time < job.duration:
            cmd += ["-t", format_seconds(job.end_time - job.start_time)]
        if job.extra_args.strip():
            cmd += shlex.split(job.extra_args)
        cmd.append(out_path)
        return cmd


class CompressTab(BaseOperationTab):
    """Compress tab — target size based on loaded file, quality presets."""

    tab_label = "Comprimir"

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QFormLayout(self)

        self._file_size_mb = 0  # current file size in MB

        self.info_label = QLabel("Nenhuma mídia carregada")
        layout.addRow("Arquivo:", self.info_label)

        self.size_slider = QSlider(Qt.Orientation.Horizontal)
        self.size_slider.setRange(1, 100)
        self.size_slider.setValue(50)
        self.size_label = QLabel("50 MB")
        self.size_slider.valueChanged.connect(self._on_slider_changed)

        size_row = QHBoxLayout()
        size_row.addWidget(self.size_slider, stretch=1)
        size_row.addWidget(self.size_label)
        layout.addRow("Tamanho alvo:", size_row)

        self.quality_combo = QComboBox()
        self.quality_combo.addItems(["Rápido (baixa qualidade)", "Balanceado", "Lento (alta qualidade)"])
        self.quality_combo.setCurrentIndex(1)
        layout.addRow("Qualidade:", self.quality_combo)

    def set_media_info(self, media_info: dict | None):
        """Update slider range based on loaded file size."""
        if media_info is None:
            self._file_size_mb = 0
            self.info_label.setText("Nenhuma mídia carregada")
            self.size_slider.setRange(1, 100)
            self.size_slider.setValue(50)
            return
        size_bytes = int(media_info.get("format", {}).get("size", 0) or 0)
        self._file_size_mb = max(1, size_bytes // (1024 * 1024))
        self.info_label.setText(f"{self._file_size_mb} MB")
        # Slider range: 1 MB to file size, default to ~50%
        self.size_slider.setRange(1, self._file_size_mb)
        self.size_slider.setValue(max(1, self._file_size_mb // 2))

    def _on_slider_changed(self, val):
        if val >= 1024:
            self.size_label.setText(f"{val / 1024:.1f} GB")
        else:
            self.size_label.setText(f"{val} MB")

    def build_job(self, input_path, output_dir, media_info, start_time, end_time, export_settings):
        quality_map = {0: "veryfast", 1: "medium", 2: "slow"}
        preset = quality_map.get(self.quality_combo.currentIndex(), "medium")
        target_mb = self.size_slider.value()
        return Job(
            input_path=input_path, output_dir=output_dir,
            operation="Compress",
            start_time=start_time, end_time=end_time,
            duration=media_info.get("duration", 0),
            reencode=True,
            vcodec=export_settings.get("vcodec", "libx264"),
            acodec=export_settings.get("acodec", "aac"),
            crf=export_settings.get("crf", "23"),
            preset=preset,
            abitrate=export_settings.get("abitrate", "128k"),
            extra_args=export_settings.get("extra_args", ""),
            container=export_settings.get("container", "mp4"),
            title=f"Comprimir → {target_mb} MB",
        )

    def get_ffmpeg_cmd(self, backend, job, out_path):
        dur = job.duration or 1
        target_mb = self.size_slider.value()
        target_bits = target_mb * 8 * 1024 * 1024
        audio_bits = int(job.abitrate.replace("k", "")) * 1000 * dur
        video_bitrate = max(100000, int((target_bits - audio_bits) / dur))
        cmd = [
            backend.ffmpeg, "-y", "-hide_banner", "-progress", "pipe:1", "-nostats",
            "-i", job.input_path,
            "-c:v", job.vcodec, "-b:v", str(video_bitrate),
            "-preset", job.preset,
            "-c:a", job.acodec, "-b:a", job.abitrate,
            "-movflags", "+faststart",
            out_path,
        ]
        return cmd


class ScreenshotsTab(BaseOperationTab):
    """Screenshots tab — single/interval/contact sheet."""

    tab_label = "Capturas"

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        self.mode_group = QButtonGroup(self)
        self.single_radio = QRadioButton("Quadro único (posição da prévia)")
        self.interval_radio = QRadioButton("A cada N segundos")
        self.contact_radio = QRadioButton("Folha de contato")
        self.single_radio.setChecked(True)

        self.mode_group.addButton(self.single_radio, 0)
        self.mode_group.addButton(self.interval_radio, 1)
        self.mode_group.addButton(self.contact_radio, 2)

        layout.addWidget(self.single_radio)

        interval_row = QHBoxLayout()
        interval_row.addWidget(self.interval_radio)
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(1, 3600)
        self.interval_spin.setValue(10)
        self.interval_spin.setSuffix(" s")
        interval_row.addWidget(self.interval_spin)
        interval_row.addStretch()
        layout.addLayout(interval_row)

        layout.addWidget(self.contact_radio)
        layout.addStretch()

    def build_job(self, input_path, output_dir, media_info, start_time, end_time, export_settings):
        modes = {0: "Single", 1: "Interval", 2: "Contact"}
        mode = modes.get(self.mode_group.checkedId(), "Single")
        extra = f"interval={self.interval_spin.value()}" if mode == "Interval" else ""
        return Job(
            input_path=input_path, output_dir=output_dir,
            operation=f"Screenshots_{mode}",
            start_time=start_time, end_time=end_time,
            duration=media_info.get("duration", 0),
            reencode=False, vcodec="", acodec="", crf="", preset="",
            abitrate="", extra_args=extra, container="png",
            title=f"Capturas ({mode})",
        )

    def get_ffmpeg_cmd(self, backend, job, out_path):
        if "Single" in job.operation:
            return backend.build_preview_frame_cmd(job.input_path, job.start_time, out_path)
        elif "Interval" in job.operation:
            interval = self.interval_spin.value()
            return [
                backend.ffmpeg, "-y", "-hide_banner",
                "-i", job.input_path,
                "-vf", f"fps=1/{interval}",
                "-q:v", "2",
                out_path.replace(".png", "_%04d.png"),
            ]
        else:  # Contact sheet
            return [
                backend.ffmpeg, "-y", "-hide_banner",
                "-i", job.input_path,
                "-vf", "fps=1/10,scale=320:-1,tile=4x4",
                "-frames:v", "1",
                out_path,
            ]


class ResizeCropTab(BaseOperationTab):
    """Resize/Crop tab — presets, custom W/H, rotate/flip."""

    tab_label = "Redimensionar"

    PRESETS = {
        "Personalizado": (0, 0),
        "1080p (1920×1080)": (1920, 1080),
        "720p (1280×720)": (1280, 720),
        "480p (854×480)": (854, 480),
        "Instagram (1080×1080)": (1080, 1080),
        "TikTok (1080×1920)": (1080, 1920),
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QFormLayout(self)

        self.preset_combo = QComboBox()
        self.preset_combo.addItems(list(self.PRESETS.keys()))
        layout.addRow("Predefinição:", self.preset_combo)

        self.width_spin = QSpinBox()
        self.width_spin.setRange(0, 8000)
        self.width_spin.setValue(0)
        self.width_spin.setSpecialValueText("Auto")
        layout.addRow("Largura:", self.width_spin)

        self.height_spin = QSpinBox()
        self.height_spin.setRange(0, 8000)
        self.height_spin.setValue(0)
        self.height_spin.setSpecialValueText("Auto")
        layout.addRow("Altura:", self.height_spin)

        self.transform_combo = QComboBox()
        self.transform_combo.addItems([
            "Nenhum", "Girar 90° horário", "Girar 90° anti-horário",
            "Girar 180°", "Espelhar horizontal", "Espelhar vertical",
        ])
        layout.addRow("Transformação:", self.transform_combo)

        self.preset_combo.currentTextChanged.connect(self._on_preset_changed)

    def _on_preset_changed(self, name):
        w, h = self.PRESETS.get(name, (0, 0))
        if w > 0:
            self.width_spin.setValue(w)
            self.height_spin.setValue(h)

    def build_job(self, input_path, output_dir, media_info, start_time, end_time, export_settings):
        w = self.width_spin.value()
        h = self.height_spin.value()
        transform = self.transform_combo.currentText()
        extra_parts = []
        vf_parts = []
        if w > 0 or h > 0:
            sw = str(w) if w > 0 else "-2"
            sh = str(h) if h > 0 else "-2"
            vf_parts.append(f"scale={sw}:{sh}")
        transform_map = {
            "Girar 90° horário": "transpose=1",
            "Girar 90° anti-horário": "transpose=2",
            "Girar 180°": "transpose=1,transpose=1",
            "Espelhar horizontal": "hflip",
            "Espelhar vertical": "vflip",
        }
        if transform in transform_map:
            vf_parts.append(transform_map[transform])
        if vf_parts:
            extra_parts.append(f"-vf {','.join(vf_parts)}")
        base_extra = export_settings.get("extra_args", "")
        if base_extra:
            extra_parts.append(base_extra)
        return Job(
            input_path=input_path, output_dir=output_dir,
            operation="Resize",
            start_time=start_time, end_time=end_time,
            duration=media_info.get("duration", 0),
            reencode=True,
            vcodec=export_settings.get("vcodec", "libx264"),
            acodec=export_settings.get("acodec", "aac"),
            crf=export_settings.get("crf", "18"),
            preset=export_settings.get("preset", "medium"),
            abitrate=export_settings.get("abitrate", "192k"),
            extra_args=" ".join(extra_parts),
            container=export_settings.get("container", "mp4"),
            title=f"Redimensionar",
        )

    def get_ffmpeg_cmd(self, backend, job, out_path):
        return backend.build_trim_cmd(job, out_path)
