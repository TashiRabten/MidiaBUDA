"""WorkerThread — Background FFmpeg job processing for MediaBUDA."""
import subprocess

from PyQt6.QtCore import QThread, pyqtSignal

from APP.ffmpeg_pro_studio_v2_pillow import FFmpegBackend, FFmpegError, Job, format_seconds


def compute_progress(out_time_us: float, duration_s: float) -> float:
    """Compute progress percentage from FFmpeg's out_time_us and expected duration.

    Returns a value clamped to [0, 100].
    """
    if duration_s <= 0:
        return 0.0
    elapsed_s = out_time_us / 1_000_000.0
    pct = (elapsed_s / duration_s) * 100.0
    return max(0.0, min(100.0, pct))


class WorkerThread(QThread):
    """Runs FFmpeg jobs in background, emits progress via signals."""

    progress = pyqtSignal(float, str)       # (percentage, label)
    log_line = pyqtSignal(str)              # raw FFmpeg output line
    job_finished = pyqtSignal(int, str)     # (job_index, output_path)
    all_done = pyqtSignal()
    error = pyqtSignal(int, str)            # (job_index, error_message)

    def __init__(self, backend: FFmpegBackend, jobs: list[Job],
                 tab_map: dict | None = None):
        super().__init__()
        self._backend = backend
        self._jobs = jobs
        self._tab_map = tab_map or {}
        self._stop_after_current = False
        self._current_process: subprocess.Popen | None = None

    def run(self) -> None:
        """Process jobs sequentially, emitting signals for each."""
        for idx, job in enumerate(self._jobs):
            if self._stop_after_current:
                break
            out_path = self._backend.build_output_path(job)
            # Use tab-specific command if available, else default trim cmd
            tab = self._tab_map.get(idx)
            if tab and hasattr(tab, 'get_ffmpeg_cmd'):
                cmd = tab.get_ffmpeg_cmd(self._backend, job, out_path)
            else:
                cmd = self._backend.build_trim_cmd(job, out_path)

            self.log_line.emit(f"Iniciando trabalho {idx+1}/{len(self._jobs)}: {job.title}")
            try:
                self._run_job(cmd, job, idx)
                self.job_finished.emit(idx, out_path)
            except FFmpegError as e:
                self.error.emit(idx, str(e))
                return
            except Exception as e:
                self.error.emit(idx, str(e))
                return
        self.all_done.emit()

    def _run_job(self, cmd: list[str], job: Job, idx: int):
        """Run a single FFmpeg command with progress tracking."""
        self._current_process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1,
        )
        latest = {}
        for raw in self._current_process.stdout:
            line = raw.rstrip("\n")
            self.log_line.emit(line)
            if "=" in line:
                k, v = line.split("=", 1)
                latest[k.strip()] = v.strip()
                out_time = latest.get("out_time_us")
                if out_time and out_time != "N/A":
                    try:
                        pct = compute_progress(float(out_time), job.duration)
                        self.progress.emit(pct, f"Trabalho {idx+1}: {pct:.0f}%")
                    except (ValueError, TypeError):
                        pass
        self._current_process.wait()
        self._current_process = None
        if self._current_process is None:
            pass  # normal completion

    def request_stop(self) -> None:
        """Stop after the current job finishes."""
        self._stop_after_current = True

    def force_cancel(self) -> None:
        """Kill the current FFmpeg subprocess immediately."""
        self._stop_after_current = True
        if self._current_process:
            try:
                self._current_process.kill()
            except OSError:
                pass
