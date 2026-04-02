"""MainWindow — PyQt6 main application window for MediaBUDA."""
import os
import threading
from pathlib import Path

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QUrl
from PyQt6.QtGui import QAction, QKeySequence, QIcon
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QPushButton, QGroupBox, QSplitter,
    QProgressBar, QTextEdit, QLabel, QFileDialog, QMessageBox,
    QMenu, QProgressDialog, QTabWidget,
)

from APP.ffmpeg_pro_studio_v2_pillow import (
    FFmpegBackend, FFmpegError, Job,
    load_config, save_config, add_recent_file, format_seconds,
    download_ffmpeg, FFMPEG_LOCAL_DIR,
    VIDEO_EXTS, AUDIO_EXTS,
)
from APP.preview_panel import PreviewPanel
from APP.timeline_scrubber import TimelineScrubber
from APP.operation_tabs import (
    TrimTab, ConvertTab, MergeTab, ExtractAudioTab,
    CompressTab, ScreenshotsTab, ResizeCropTab,
)
from APP.export_settings import ExportSettingsGroup
from APP.batch_queue import BatchQueuePanel
from APP.worker_thread import WorkerThread
from APP.ui_colors import get_stylesheet
from APP.autoupdater import MediaBUDAUpdater, APP_VERSION

APP_TITLE = "MediaBUDA"

SUPPORTED_EXTS = set(VIDEO_EXTS + AUDIO_EXTS)


def _get_icon_path(name: str) -> str:
    """Return absolute path to an icon in APP/icons/."""
    return os.path.join(os.path.dirname(__file__), "icons", name)


def _btn_icon(name: str, size: int = 20) -> QIcon:
    """Load a QIcon from APP/icons/ at the given size, or return empty QIcon."""
    path = _get_icon_path(name)
    if os.path.exists(path):
        return QIcon(path)
    return QIcon()


class DownloadThread(QThread):
    """Background thread for downloading FFmpeg binaries."""
    status = pyqtSignal(str)
    finished_ok = pyqtSignal(str, str)  # (ffmpeg_path, ffprobe_path)
    error = pyqtSignal(str)

    def run(self):
        try:
            ff, fp = download_ffmpeg(on_status=lambda msg: self.status.emit(msg))
            self.finished_ok.emit(ff, fp)
        except Exception as e:
            self.error.emit(str(e))


def _format_file_size(size_bytes: int | float) -> str:
    """Format bytes into a human-readable string."""
    size = float(size_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def extract_media_info_labels(info: dict | None) -> dict:
    """Extract display strings from a probe result dict.

    Returns a dict with keys: duration, resolution, codecs, file_size.
    Missing fields show '—'.
    """
    if info is None:
        return {
            "duration": "Duração: —",
            "resolution": "Resolução: —",
            "codecs": "Codecs: —",
            "file_size": "Tamanho: —",
        }

    # Duration
    dur = info.get("duration", 0)
    dur_str = format_seconds(dur) if dur else "—"

    # Resolution
    video = info.get("video")
    if video and video.get("width") and video.get("height"):
        res_str = f"{video['width']}×{video['height']}"
    else:
        res_str = "—"

    # Codecs
    vcodec = video.get("codec_name", "—") if video else "—"
    audio = info.get("audio")
    acodec = audio.get("codec_name", "—") if audio else "—"
    codecs_str = f"{vcodec} / {acodec}"

    # File size
    fmt = info.get("format", {})
    size_raw = fmt.get("size")
    if size_raw:
        size_str = _format_file_size(int(size_raw))
    else:
        size_str = "—"

    return {
        "duration": f"Duração: {dur_str}",
        "resolution": f"Resolução: {res_str}",
        "codecs": f"Codecs: {codecs_str}",
        "file_size": f"Tamanho: {size_str}",
    }


class MainWindow(QMainWindow):
    """Main application window for MediaBUDA (PyQt6)."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.setMinimumSize(800, 600)
        self.resize(1100, 750)

        # Set window icon (.ico for Windows taskbar)
        icon_path = _get_icon_path("pramana.ico")
        if not os.path.exists(icon_path):
            icon_path = _get_icon_path("BUDA.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        # Apply global stylesheet
        self.setStyleSheet(get_stylesheet())

        # State
        self.config: dict = load_config()
        self.backend: FFmpegBackend = FFmpegBackend(on_status=self._on_backend_status)
        self.media_info: dict | None = None
        self.worker = None  # WorkerThread, set by later tasks

        self._build_ui()
        self._restore_geometry()
        self._restore_tab_settings()
        self._check_ffmpeg_startup()

    # ── FFmpeg startup check ─────────────────────────────────────────

    def _check_ffmpeg_startup(self):
        """On first launch, download FFmpeg if not available."""
        try:
            self.backend.check_tools()
            self._log(f"FFmpeg: {self.backend.get_version()}")
        except FFmpegError:
            self._start_ffmpeg_download()

    def _start_ffmpeg_download(self):
        """Show a progress dialog and download FFmpeg in background."""
        self._dl_dialog = QProgressDialog(
            "Baixando FFmpeg (isso só acontece uma vez)...",
            "Cancelar", 0, 0, self
        )
        self._dl_dialog.setWindowTitle(APP_TITLE)
        self._dl_dialog.setMinimumDuration(0)
        self._dl_dialog.setCancelButton(None)  # no cancel during download
        self._dl_dialog.setModal(True)
        self._dl_dialog.show()

        self._dl_thread = DownloadThread()
        self._dl_thread.status.connect(lambda msg: self._dl_dialog.setLabelText(msg))
        self._dl_thread.finished_ok.connect(self._on_download_ok)
        self._dl_thread.error.connect(self._on_download_error)
        self._dl_thread.start()

    def _on_download_ok(self, ff_path: str, fp_path: str):
        self._dl_dialog.close()
        self.backend.ffmpeg = ff_path
        self.backend.ffprobe = fp_path
        self._log(f"✓ FFmpeg baixado: {self.backend.get_version()}")

    def _on_download_error(self, msg: str):
        self._dl_dialog.close()
        reply = QMessageBox.critical(
            self, APP_TITLE,
            f"Falha ao baixar FFmpeg:\n{msg}\n\nTentar novamente?",
            QMessageBox.StandardButton.Retry | QMessageBox.StandardButton.Cancel,
        )
        if reply == QMessageBox.StandardButton.Retry:
            self._start_ffmpeg_download()
        else:
            self._log("FFmpeg não disponível. Instale manualmente.")

    # ── UI Construction ──────────────────────────────────────────────

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        self.setAcceptDrops(True)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(10, 10, 10, 10)

        # --- Top file row ---
        file_row = QHBoxLayout()
        file_row.addWidget(QLabel("Arquivo de entrada:"))
        self.input_edit = QLineEdit()
        self.input_edit.setPlaceholderText("Selecione um arquivo de mídia...")
        file_row.addWidget(self.input_edit, stretch=1)
        self.browse_btn = QPushButton("Procurar")
        self.browse_btn.setIcon(_btn_icon("Roda.png"))
        self.browse_btn.clicked.connect(self.open_file)
        file_row.addWidget(self.browse_btn)
        self.load_btn = QPushButton("Carregar")
        self.load_btn.setIcon(_btn_icon("Mala.png"))
        self.load_btn.clicked.connect(self._on_load_clicked)
        file_row.addWidget(self.load_btn)
        root_layout.addLayout(file_row)

        # --- Output folder row ---
        out_row = QHBoxLayout()
        out_row.addWidget(QLabel("Pasta de saída:"))
        self.output_edit = QLineEdit()
        self.output_edit.setText(self.config.get("output_dir", str(Path.home() / "Videos")))
        out_row.addWidget(self.output_edit, stretch=1)
        self.out_browse_btn = QPushButton("Procurar")
        self.out_browse_btn.setIcon(_btn_icon("Roda.png"))
        self.out_browse_btn.clicked.connect(self._browse_output_dir)
        out_row.addWidget(self.out_browse_btn)
        root_layout.addLayout(out_row)

        # --- Media info group ---
        self.media_info_group = QGroupBox("Informações da mídia")
        mi_layout = QHBoxLayout(self.media_info_group)
        self.duration_label = QLabel("Duração: —")
        self.resolution_label = QLabel("Resolução: —")
        self.codecs_label = QLabel("Codecs: —")
        self.filesize_label = QLabel("Tamanho: —")
        for lbl in (self.duration_label, self.resolution_label,
                     self.codecs_label, self.filesize_label):
            mi_layout.addWidget(lbl)
        mi_layout.addStretch()
        root_layout.addWidget(self.media_info_group)

        # --- Preview (left) + Timeline (right) side by side ---
        preview_timeline_row = QHBoxLayout()
        preview_timeline_row.setSpacing(8)

        self.preview_panel = PreviewPanel()
        self.preview_panel.setFixedSize(320, 180)
        preview_timeline_row.addWidget(self.preview_panel)

        timeline_col = QVBoxLayout()
        timeline_col.setSpacing(2)
        self.timeline = TimelineScrubber()
        timeline_col.addWidget(self.timeline)
        # Update preview frame when preview slider is released
        self.timeline.preview_slider.sliderReleased.connect(self._preview_frame)
        self.preview_frame_btn = QPushButton("Prévia")
        self.preview_frame_btn.setIcon(_btn_icon("Lotus2.png"))
        self.preview_frame_btn.setFixedWidth(90)
        self.preview_frame_btn.clicked.connect(self._preview_frame)
        timeline_col.addWidget(self.preview_frame_btn)
        timeline_col.addStretch()
        preview_timeline_row.addLayout(timeline_col, stretch=1)

        root_layout.addLayout(preview_timeline_row)

        # --- Horizontal splitter (tabs+settings | queue) ---
        self.splitter = QSplitter(Qt.Orientation.Horizontal)

        self.left_panel = QWidget()
        self.left_layout = QVBoxLayout(self.left_panel)
        self.left_layout.setContentsMargins(0, 0, 0, 0)
        self.left_layout.setSpacing(4)

        # Operation tabs
        self.operation_tabs = QTabWidget()
        self.trim_tab = TrimTab()
        self.convert_tab = ConvertTab()
        self.merge_tab = MergeTab()
        self.extract_audio_tab = ExtractAudioTab()
        self.compress_tab = CompressTab()
        self.screenshots_tab = ScreenshotsTab()
        self.resize_crop_tab = ResizeCropTab()
        for tab in (self.trim_tab, self.convert_tab, self.merge_tab,
                     self.extract_audio_tab, self.compress_tab,
                     self.screenshots_tab, self.resize_crop_tab):
            self.operation_tabs.addTab(tab, tab.tab_label)
        self.left_layout.addWidget(self.operation_tabs)

        # Export settings
        self.export_settings = ExportSettingsGroup()
        self.left_layout.addWidget(self.export_settings)

        # Toggle: clicking a tab collapses export settings
        self.operation_tabs.currentChanged.connect(self._on_tab_changed_collapse_export)

        # Action buttons
        action_row = QHBoxLayout()
        self.add_queue_btn = QPushButton("Adicionar à fila")
        self.add_queue_btn.setIcon(_btn_icon("salvar.png"))
        self.run_now_btn = QPushButton("Executar agora")
        self.run_now_btn.setIcon(_btn_icon("Lotus2.png"))
        action_row.addWidget(self.add_queue_btn)
        action_row.addWidget(self.run_now_btn)
        action_row.addStretch()
        self.left_layout.addLayout(action_row)

        self.right_panel = QWidget()
        self.right_layout = QVBoxLayout(self.right_panel)
        self.right_layout.setContentsMargins(0, 0, 0, 0)
        self.batch_queue = BatchQueuePanel()
        self.right_layout.addWidget(self.batch_queue)

        self.splitter.addWidget(self.left_panel)
        self.splitter.addWidget(self.right_panel)
        self.splitter.setStretchFactor(0, 3)
        self.splitter.setStretchFactor(1, 2)
        root_layout.addWidget(self.splitter, stretch=1)

        # --- Log group (collapsible, starts collapsed) ---
        self.log_group = QGroupBox("Log de saída")
        self.log_group.setCheckable(True)
        self.log_group.setChecked(False)
        self.log_group.setMaximumHeight(150)
        log_layout = QVBoxLayout(self.log_group)

        progress_row = QHBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        progress_row.addWidget(self.progress_bar, stretch=1)
        self.progress_label = QLabel("Ocioso")
        progress_row.addWidget(self.progress_label)
        log_layout.addLayout(progress_row)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        log_layout.addWidget(self.log_text)

        # Toggle log visibility via checkable group
        self.log_group.toggled.connect(self._on_log_toggled)
        self._on_log_toggled(False)  # start collapsed

        root_layout.addWidget(self.log_group)

        # --- Menu bar ---
        self._build_menu_bar()

        # --- Wire action buttons ---
        self.add_queue_btn.clicked.connect(self._add_to_queue)
        self.run_now_btn.clicked.connect(self._run_now)
        self.batch_queue.run_requested.connect(self._run_batch_queue)
        self.batch_queue.stop_requested.connect(self._stop_worker)

    def _on_log_toggled(self, checked: bool):
        """Show/hide log content based on group checkbox."""
        self.log_text.setVisible(checked)
        if checked:
            self.log_group.setMaximumHeight(300)
        else:
            self.log_group.setMaximumHeight(60)

    def _on_tab_changed_collapse_export(self, _index: int):
        """When a tab is clicked/changed, collapse the export settings."""
        self.export_settings.setChecked(False)

    # ── Menu Bar ─────────────────────────────────────────────────────

    def _build_menu_bar(self):
        """Build the menu bar with Arquivo and Ajuda menus."""
        menu_bar = self.menuBar()

        # -- Arquivo (File) menu --
        self.file_menu = menu_bar.addMenu("Arquivo")

        open_action = QAction("Abrir...", self)
        open_action.setShortcut(QKeySequence("Ctrl+O"))
        open_action.triggered.connect(self.open_file)
        self.file_menu.addAction(open_action)

        # Recent files submenu
        self.recent_menu = QMenu("Arquivos recentes", self)
        self.file_menu.addMenu(self.recent_menu)
        self._refresh_recent_menu()

        self.file_menu.addSeparator()

        update_action = QAction("Verificar atualizações do FFmpeg", self)
        update_action.triggered.connect(self._check_ffmpeg_updates)
        self.file_menu.addAction(update_action)

        self.file_menu.addSeparator()

        exit_action = QAction("Sair", self)
        exit_action.triggered.connect(self.close)
        self.file_menu.addAction(exit_action)

        # -- Ajuda (Help) menu --
        self.help_menu = menu_bar.addMenu("Ajuda")

        update_app_action = QAction("Verificar atualizações", self)
        update_app_action.triggered.connect(self._check_app_updates)
        self.help_menu.addAction(update_app_action)

        self.help_menu.addSeparator()

        about_action = QAction("Sobre", self)
        about_action.triggered.connect(self._show_about)
        self.help_menu.addAction(about_action)

    def _refresh_recent_menu(self):
        """Rebuild the recent files submenu from config."""
        self.recent_menu.clear()
        recents = self.config.get("recent_files", [])
        if not recents:
            no_files = QAction("(nenhum arquivo recente)", self)
            no_files.setEnabled(False)
            self.recent_menu.addAction(no_files)
        else:
            for path in recents:
                display = Path(path).name if len(path) > 60 else path
                action = QAction(display, self)
                action.setData(path)
                action.triggered.connect(lambda checked, p=path: self._open_recent(p))
                self.recent_menu.addAction(action)

    def _open_recent(self, path: str):
        """Open a file from the recent files list."""
        if not Path(path).exists():
            QMessageBox.warning(
                self, APP_TITLE, f"Arquivo não encontrado:\n{path}"
            )
            return
        self.input_edit.setText(path)
        self.load_media(path)

    def _check_ffmpeg_updates(self):
        """Force re-download FFmpeg to get the latest version."""
        def _work():
            try:
                ext = ".exe" if os.name == "nt" else ""
                for name in ("ffmpeg", "ffprobe"):
                    p = FFMPEG_LOCAL_DIR / f"{name}{ext}"
                    p.unlink(missing_ok=True)
                ff, fp = download_ffmpeg(
                    on_status=lambda msg: self._log(msg)
                )
                self.backend.ffmpeg = ff
                self.backend.ffprobe = fp
                version = self.backend.get_version()
                self._log(f"✓ FFmpeg atualizado: {version}")
            except Exception as e:
                self._log(f"Falha na atualização: {e}")

        threading.Thread(target=_work, daemon=True).start()

    def _show_about(self):
        """Show the About dialog with FFmpeg version."""
        version = self.backend.get_version()
        QMessageBox.information(
            self, f"Sobre — {APP_TITLE}",
            f"{APP_TITLE} v{APP_VERSION}\n\n"
            f"Ferramenta amigável de edição de vídeo/áudio.\n"
            f"O FFmpeg é baixado automaticamente na primeira execução.\n\n"
            f"FFmpeg: {version}\n"
            f"Localização: {self.backend.ffmpeg}",
        )

    # ── App auto-update ──────────────────────────────────────────────

    def _check_app_updates(self):
        """Check GitHub for a newer MediaBUDA release."""
        updater = MediaBUDAUpdater()
        has_update, info = updater.check_for_updates()

        if not has_update or info is None:
            QMessageBox.information(
                self, APP_TITLE,
                f"Você já está usando a versão mais recente (v{APP_VERSION}).",
            )
            return

        reply = QMessageBox.question(
            self, APP_TITLE,
            f"Nova versão disponível: v{info['version']}\n\n"
            f"{info.get('release_notes', '')}\n\n"
            f"Deseja baixar a atualização?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        url = info.get("download_url")
        if not url:
            QMessageBox.warning(
                self, APP_TITLE,
                "Nenhum instalador encontrado para esta plataforma.",
            )
            return

        # Show progress dialog during download
        dlg = QProgressDialog(
            "Baixando atualização...", "Cancelar", 0, 100, self
        )
        dlg.setWindowTitle(APP_TITLE)
        dlg.setMinimumDuration(0)
        dlg.setModal(True)
        dlg.show()

        from PyQt6.QtWidgets import QApplication
        cancelled = [False]

        def _progress(pct):
            if dlg.wasCanceled():
                cancelled[0] = True
                return
            dlg.setValue(pct)
            QApplication.processEvents()

        path = updater.download_installer(url, progress_callback=_progress)
        dlg.close()

        if cancelled[0] or path is None:
            if not cancelled[0]:
                QMessageBox.warning(
                    self, APP_TITLE, "Falha ao baixar a atualização."
                )
            return

        reply = QMessageBox.question(
            self, APP_TITLE,
            f"Download concluído: {path.name}\n\nAbrir o instalador agora?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            MediaBUDAUpdater.launch_installer(path)

    # ── Slots / Actions ──────────────────────────────────────────────

    def open_file(self):
        """Open a file dialog to select a media file."""
        exts = VIDEO_EXTS + AUDIO_EXTS
        filter_str = "Arquivos de mídia (" + " ".join(f"*{e}" for e in exts) + ")"
        path, _ = QFileDialog.getOpenFileName(
            self, "Selecionar arquivo de mídia", "", filter_str
        )
        if path:
            self.input_edit.setText(path)
            self.load_media(path)

    def _on_load_clicked(self):
        """Handle the Load button click."""
        path = self.input_edit.text().strip()
        if not path:
            QMessageBox.warning(self, APP_TITLE, "Nenhum arquivo selecionado.")
            return
        if not Path(path).exists():
            QMessageBox.warning(self, APP_TITLE, f"Arquivo não encontrado:\n{path}")
            return
        self.load_media(path)

    def load_media(self, path: str):
        """Probe the media file and update the UI with its info."""
        try:
            info = self.backend.probe(path)
        except FFmpegError as e:
            QMessageBox.critical(
                self, APP_TITLE,
                f"Não foi possível ler o arquivo de mídia.\n\n{e}"
            )
            self.media_info = None
            self._update_media_labels()
            return

        self.media_info = info
        self.input_edit.setText(path)

        # Update recent files
        self.config = add_recent_file(self.config, path)
        self._refresh_recent_menu()

        self._update_media_labels()

        # Set timeline duration and preview first frame
        dur = info.get("duration", 0)
        if dur:
            self.timeline.set_duration(dur)
            self._preview_frame()

        # Update compress tab with file size
        self.compress_tab.set_media_info(info)

        self._log(f"Mídia carregada: {Path(path).name}")

    def _update_media_labels(self):
        """Refresh the media info labels from current media_info."""
        labels = extract_media_info_labels(self.media_info)
        self.duration_label.setText(labels["duration"])
        self.resolution_label.setText(labels["resolution"])
        self.codecs_label.setText(labels["codecs"])
        self.filesize_label.setText(labels["file_size"])

    def _browse_output_dir(self):
        """Open a folder dialog for the output directory."""
        current = self.output_edit.text() or str(Path.home() / "Videos")
        folder = QFileDialog.getExistingDirectory(
            self, "Selecionar pasta de saída", current
        )
        if folder:
            self.output_edit.setText(folder)

    def _on_backend_status(self, msg: str):
        """Callback for backend status messages (e.g., FFmpeg download)."""
        self._log(msg)

    def _log(self, text: str):
        """Append a line to the log text area."""
        self.log_text.append(text)

    def set_progress(self, value: float, label: str):
        """Update the progress bar and label."""
        self.progress_bar.setValue(max(0, min(100, int(value))))
        self.progress_label.setText(label)

    # ── Queue / Worker ─────────────────────────────────────────────────

    def _get_current_tab(self):
        """Return the currently active operation tab."""
        return self.operation_tabs.currentWidget()

    def _build_current_job(self):
        """Build a Job from the current tab and export settings."""
        tab = self._get_current_tab()
        if tab is None or self.media_info is None:
            return None
        return tab.build_job(
            input_path=self.input_edit.text().strip(),
            output_dir=self.output_edit.text().strip(),
            media_info=self.media_info,
            start_time=self.timeline.get_start(),
            end_time=self.timeline.get_end(),
            export_settings=self.export_settings.get_settings(),
        )

    def _add_to_queue(self):
        """Add the current operation to the batch queue."""
        if self.media_info is None:
            QMessageBox.warning(self, APP_TITLE, "Nenhuma mídia carregada.")
            return
        job = self._build_current_job()
        if job:
            self.batch_queue.add_job(job)
            self._log(f"Trabalho adicionado à fila: {job.title}")

    def _run_now(self):
        """Run the current operation immediately (single job)."""
        if self.media_info is None:
            QMessageBox.warning(self, APP_TITLE, "Nenhuma mídia carregada.")
            return
        job = self._build_current_job()
        tab = self._get_current_tab()
        if job:
            self._start_worker([job], tab_map={0: tab})

    def _run_batch_queue(self):
        """Run all jobs in the batch queue."""
        jobs = self.batch_queue.get_all_jobs()
        if not jobs:
            QMessageBox.warning(self, APP_TITLE, "A fila está vazia.")
            return
        self._start_worker(jobs)

    def _start_worker(self, jobs: list, tab_map: dict | None = None):
        """Start the WorkerThread with the given jobs."""
        if self.worker is not None and self.worker.isRunning():
            QMessageBox.warning(self, APP_TITLE, "Um trabalho já está em andamento.")
            return
        self.worker = WorkerThread(self.backend, jobs, tab_map=tab_map)
        self.worker.progress.connect(self.set_progress)
        self.worker.log_line.connect(self._log)
        self.worker.job_finished.connect(self._on_job_finished)
        self.worker.all_done.connect(self._on_all_done)
        self.worker.error.connect(self._on_worker_error)
        self.worker.start()
        self._log("Processamento iniciado...")

    def _on_job_finished(self, idx: int, out_path: str):
        self.batch_queue.set_job_status(idx, "Concluído")
        self._log(f"✓ Trabalho {idx+1} concluído: {out_path}")

    def _on_all_done(self):
        self.set_progress(100.0, "Tudo concluído")
        self._log("✓ Todos os trabalhos concluídos!")
        self.worker = None

    def _on_worker_error(self, idx: int, msg: str):
        self.batch_queue.set_job_status(idx, "Erro")
        self.set_progress(0.0, "Falhou")
        self._log(f"✗ Erro no trabalho {idx+1}: {msg}")
        QMessageBox.critical(self, APP_TITLE, f"Erro no trabalho {idx+1}:\n{msg}")
        self.worker = None

    def _stop_worker(self):
        """Stop the worker after the current job."""
        if self.worker and self.worker.isRunning():
            self.worker.request_stop()
            self._log("Parando após o trabalho atual...")

    # ── Geometry persistence ─────────────────────────────────────────

    def _restore_geometry(self):
        """Restore window geometry from config if available."""
        geo = self.config.get("window_geometry")
        if geo and isinstance(geo, dict):
            x = geo.get("x", 100)
            y = geo.get("y", 100)
            w = geo.get("w", 1100)
            h = geo.get("h", 750)
            self.setGeometry(x, y, w, h)

    def _save_geometry(self):
        """Save current window geometry to config."""
        g = self.geometry()
        self.config["window_geometry"] = {
            "x": g.x(), "y": g.y(), "w": g.width(), "h": g.height()
        }

    def _save_tab_settings(self):
        """Save current tab and export settings to config."""
        self.config["tab_settings"] = {
            "active_tab": self.operation_tabs.currentIndex(),
            "trim": {
                "operation": self.trim_tab.operation_combo.currentText(),
                "reencode": self.trim_tab.reencode_check.isChecked(),
            },
            "convert": {
                "preset": self.convert_tab.preset_combo.currentText(),
            },
            "extract_audio": {
                "format": self.extract_audio_tab.format_combo.currentText(),
                "bitrate": self.extract_audio_tab.bitrate_combo.currentText(),
            },
            "compress": {
                "target_size": self.compress_tab.size_slider.value(),
                "quality": self.compress_tab.quality_combo.currentIndex(),
            },
            "export": self.export_settings.get_settings(),
        }

    def _restore_tab_settings(self):
        """Restore tab and export settings from config."""
        ts = self.config.get("tab_settings")
        if not ts or not isinstance(ts, dict):
            return
        # Active tab
        idx = ts.get("active_tab", 0)
        if 0 <= idx < self.operation_tabs.count():
            self.operation_tabs.setCurrentIndex(idx)
        # Trim
        trim = ts.get("trim", {})
        if "operation" in trim:
            i = self.trim_tab.operation_combo.findText(trim["operation"])
            if i >= 0:
                self.trim_tab.operation_combo.setCurrentIndex(i)
        if "reencode" in trim:
            self.trim_tab.reencode_check.setChecked(trim["reencode"])
        # Convert
        conv = ts.get("convert", {})
        if "preset" in conv:
            i = self.convert_tab.preset_combo.findText(conv["preset"])
            if i >= 0:
                self.convert_tab.preset_combo.setCurrentIndex(i)
        # Extract audio
        ea = ts.get("extract_audio", {})
        if "format" in ea:
            i = self.extract_audio_tab.format_combo.findText(ea["format"])
            if i >= 0:
                self.extract_audio_tab.format_combo.setCurrentIndex(i)
        if "bitrate" in ea:
            i = self.extract_audio_tab.bitrate_combo.findText(ea["bitrate"])
            if i >= 0:
                self.extract_audio_tab.bitrate_combo.setCurrentIndex(i)
        # Compress
        comp = ts.get("compress", {})
        if "target_size" in comp:
            self.compress_tab.size_slider.setValue(comp["target_size"])
        if "quality" in comp:
            self.compress_tab.quality_combo.setCurrentIndex(comp["quality"])
        # Export settings
        exp = ts.get("export", {})
        for attr, combo in [
            ("vcodec", self.export_settings.vcodec_combo),
            ("acodec", self.export_settings.acodec_combo),
            ("crf", self.export_settings.crf_combo),
            ("preset", self.export_settings.preset_combo),
            ("abitrate", self.export_settings.abitrate_combo),
            ("container", self.export_settings.container_combo),
        ]:
            val = exp.get(attr)
            if val:
                i = combo.findText(val)
                if i >= 0:
                    combo.setCurrentIndex(i)
        extra = exp.get("extra_args", "")
        if extra:
            self.export_settings.extra_args_edit.setText(extra)

    # ── Preview ────────────────────────────────────────────────────────

    def _preview_frame(self):
        """Extract and display the frame at the current preview position."""
        if self.media_info is None:
            return
        import tempfile
        from PIL import Image
        from PyQt6.QtGui import QPixmap

        t = self.timeline.get_preview()
        path = self.input_edit.text().strip()
        if not path:
            return

        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            cmd = self.backend.build_preview_frame_cmd(path, t, tmp_path)
            self.backend.run_simple(cmd)
            pixmap = QPixmap(tmp_path)
            if not pixmap.isNull():
                self.preview_panel.set_frame(pixmap)
        except Exception as e:
            self._log(f"Erro na prévia: {e}")
        finally:
            import os as _os
            _os.unlink(tmp_path) if _os.path.exists(tmp_path) else None

    # ── Drag and drop ───────────────────────────────────────────────

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if Path(path).suffix.lower() in SUPPORTED_EXTS:
                self.input_edit.setText(path)
                self.load_media(path)
                break

    # ── Close event ──────────────────────────────────────────────────

    def closeEvent(self, event):
        """Save config and prompt if a worker is running."""
        # Check if a worker thread is active
        if self.worker is not None and self.worker.isRunning():
            reply = QMessageBox.question(
                self, APP_TITLE,
                "Um trabalho está em andamento. Cancelar e sair?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.No:
                event.ignore()
                return
            # Force cancel the worker
            if hasattr(self.worker, 'force_cancel'):
                self.worker.force_cancel()
            self.worker.wait(2000)

        # Save config
        self.config["output_dir"] = self.output_edit.text()
        self._save_geometry()
        self._save_tab_settings()
        save_config(self.config)
        event.accept()
