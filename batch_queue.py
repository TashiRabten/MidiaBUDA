"""BatchQueuePanel — Queue table and control buttons for MediaBUDA.

All UI text in Portuguese.
"""
import json
import os
from dataclasses import asdict
from pathlib import Path

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QPushButton,
    QHeaderView, QFileDialog, QAbstractItemView,
)

from APP.ffmpeg_pro_studio_v2_pillow import Job, safe_stem


def _btn_icon(name: str) -> QIcon:
    path = os.path.join(os.path.dirname(__file__), "icons", name)
    return QIcon(path) if os.path.exists(path) else QIcon()


class BatchQueuePanel(QWidget):
    """Queue table + control buttons."""

    run_requested = pyqtSignal()
    stop_requested = pyqtSignal()

    COLUMNS = ["Título", "Operação", "Entrada", "Seleção", "Saída", "Status"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._jobs: list[Job] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Table
        self.table = QTableWidget(0, len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        header = self.table.horizontalHeader()
        header.setStretchLastSection(True)
        for i in range(len(self.COLUMNS) - 1):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.table)

        # Control buttons
        ctrl_row = QHBoxLayout()
        self.remove_btn = QPushButton("Remover selecionado")
        self.remove_btn.setIcon(_btn_icon("Vassoura.png"))
        self.clear_btn = QPushButton("Limpar fila")
        self.clear_btn.setIcon(_btn_icon("Vassoura.png"))
        self.save_btn = QPushButton("Salvar JSON")
        self.save_btn.setIcon(_btn_icon("salvar.png"))
        self.load_btn = QPushButton("Carregar JSON")
        self.load_btn.setIcon(_btn_icon("Mala.png"))
        for b in (self.remove_btn, self.clear_btn, self.save_btn, self.load_btn):
            ctrl_row.addWidget(b)
        ctrl_row.addStretch()
        layout.addLayout(ctrl_row)

        # Run buttons
        run_row = QHBoxLayout()
        self.run_btn = QPushButton("Executar fila")
        self.run_btn.setIcon(_btn_icon("Lotus2.png"))
        self.stop_btn = QPushButton("Parar após trabalho atual")
        self.stop_btn.setIcon(_btn_icon("Roda.png"))
        run_row.addWidget(self.run_btn)
        run_row.addWidget(self.stop_btn)
        run_row.addStretch()
        layout.addLayout(run_row)

        # Connections
        self.remove_btn.clicked.connect(self.remove_selected)
        self.clear_btn.clicked.connect(self.clear)
        self.save_btn.clicked.connect(self._save_dialog)
        self.load_btn.clicked.connect(self._load_dialog)
        self.run_btn.clicked.connect(self.run_requested.emit)
        self.stop_btn.clicked.connect(self.stop_requested.emit)

    def add_job(self, job: Job) -> None:
        """Add a job to the queue."""
        self._jobs.append(job)
        row = self.table.rowCount()
        self.table.insertRow(row)
        stem = safe_stem(job.input_path)
        selection = f"{job.start_time:.1f}s – {job.end_time:.1f}s"
        values = [job.title, job.operation, Path(job.input_path).name,
                  selection, f"{stem}.{job.container}", "Pendente"]
        for col, val in enumerate(values):
            self.table.setItem(row, col, QTableWidgetItem(val))

    def remove_selected(self) -> None:
        """Remove selected rows from the queue."""
        rows = sorted(set(idx.row() for idx in self.table.selectedIndexes()), reverse=True)
        for row in rows:
            if 0 <= row < len(self._jobs):
                self._jobs.pop(row)
                self.table.removeRow(row)

    def clear(self) -> None:
        """Clear all jobs from the queue."""
        self._jobs.clear()
        self.table.setRowCount(0)

    def get_all_jobs(self) -> list[Job]:
        """Return a copy of all jobs in the queue."""
        return list(self._jobs)

    def set_job_status(self, index: int, status: str) -> None:
        """Update the status column for a specific job."""
        if 0 <= index < self.table.rowCount():
            self.table.setItem(index, 5, QTableWidgetItem(status))

    def save_to_json(self, path: str) -> None:
        """Serialize jobs to JSON file."""
        data = [asdict(j) for j in self._jobs]
        Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def load_from_json(self, path: str) -> list[Job]:
        """Deserialize jobs from JSON file and add to queue."""
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        jobs = []
        for item in data:
            job = Job(**item)
            jobs.append(job)
            self.add_job(job)
        return jobs

    def _save_dialog(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Salvar fila", "", "JSON (*.json)"
        )
        if path:
            self.save_to_json(path)

    def _load_dialog(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Carregar fila", "", "JSON (*.json)"
        )
        if path:
            self.load_from_json(path)
