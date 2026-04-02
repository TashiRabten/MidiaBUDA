
import os
import sys
import shlex
import json
import math
import queue
import shutil
import tempfile
import threading
import subprocess
import urllib.request
import zipfile
from dataclasses import dataclass, asdict
from pathlib import Path

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk


APP_TITLE = "MediaBUDA"
VIDEO_EXTS = [".mp4", ".mkv", ".mov", ".avi", ".webm", ".flv", ".m4v", ".ts", ".mts"]
AUDIO_EXTS = [".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".opus"]
FFMPEG_LOCAL_DIR = Path.home() / ".ffmpeg_pro_studio"
CONFIG_FILE = FFMPEG_LOCAL_DIR / "config.json"


def format_seconds(seconds: float) -> str:
    seconds = max(0.0, float(seconds))
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"


def safe_stem(path: str) -> str:
    return Path(path).stem.replace(" ", "_")


def which_or_name(name: str) -> str:
    """Find executable on PATH, or return name as-is for PyInstaller bundles."""
    import shutil
    found = shutil.which(name)
    if found:
        return found
    # Check if bundled with PyInstaller
    if getattr(sys, '_MEIPASS', None):
        bundled = os.path.join(sys._MEIPASS, name)
        if os.path.isfile(bundled):
            return bundled
        if os.name == 'nt':
            bundled_exe = bundled + '.exe'
            if os.path.isfile(bundled_exe):
                return bundled_exe
    return name


def load_config() -> dict:
    """Load app config (recent files, etc.)."""
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"recent_files": [], "output_dir": str(Path.home() / "Videos")}


def save_config(cfg: dict):
    """Save app config."""
    FFMPEG_LOCAL_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2), encoding="utf-8")


def add_recent_file(cfg: dict, path: str) -> dict:
    """Add a file to the recent files list (max 10)."""
    recents = cfg.get("recent_files", [])
    if path in recents:
        recents.remove(path)
    recents.insert(0, path)
    cfg["recent_files"] = recents[:10]
    return cfg


def download_ffmpeg(on_status=None):
    """
    Download FFmpeg binaries to ~/.ffmpeg_pro_studio/ if not already present.
    Returns (ffmpeg_path, ffprobe_path) or raises on failure.
    """
    FFMPEG_LOCAL_DIR.mkdir(parents=True, exist_ok=True)
    ext = ".exe" if os.name == "nt" else ""
    ffmpeg_path = FFMPEG_LOCAL_DIR / f"ffmpeg{ext}"
    ffprobe_path = FFMPEG_LOCAL_DIR / f"ffprobe{ext}"

    if ffmpeg_path.exists() and ffprobe_path.exists():
        return str(ffmpeg_path), str(ffprobe_path)

    if on_status:
        on_status("Downloading FFmpeg (this only happens once)...")

    if sys.platform == "win32":
        url = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
    elif sys.platform == "darwin":
        # macOS — use evermeet.cx static builds
        url_ff = "https://evermeet.cx/ffmpeg/getrelease/zip"
        url_fp = "https://evermeet.cx/ffmpeg/getrelease/ffprobe/zip"
        tmp_ff = FFMPEG_LOCAL_DIR / "ffmpeg_dl.zip"
        tmp_fp = FFMPEG_LOCAL_DIR / "ffprobe_dl.zip"
        try:
            if on_status:
                on_status("Downloading ffmpeg for macOS...")
            urllib.request.urlretrieve(url_ff, str(tmp_ff))
            with zipfile.ZipFile(str(tmp_ff), 'r') as z:
                for name in z.namelist():
                    if name.endswith("ffmpeg"):
                        with z.open(name) as src, open(str(ffmpeg_path), 'wb') as dst:
                            dst.write(src.read())
                        os.chmod(str(ffmpeg_path), 0o755)
            if on_status:
                on_status("Downloading ffprobe for macOS...")
            urllib.request.urlretrieve(url_fp, str(tmp_fp))
            with zipfile.ZipFile(str(tmp_fp), 'r') as z:
                for name in z.namelist():
                    if name.endswith("ffprobe"):
                        with z.open(name) as src, open(str(ffprobe_path), 'wb') as dst:
                            dst.write(src.read())
                        os.chmod(str(ffprobe_path), 0o755)
            tmp_ff.unlink(missing_ok=True)
            tmp_fp.unlink(missing_ok=True)
            return str(ffmpeg_path), str(ffprobe_path)
        except Exception as e:
            raise RuntimeError(f"Failed to download FFmpeg for macOS: {e}") from e
    else:
        raise RuntimeError("Auto-download not supported on this platform. Install FFmpeg manually.")

    # Windows path
    tmp_zip = FFMPEG_LOCAL_DIR / "ffmpeg_dl.zip"
    try:
        if on_status:
            on_status("Downloading FFmpeg (~90MB, please wait)...")
        urllib.request.urlretrieve(url, str(tmp_zip))
        if on_status:
            on_status("Extracting FFmpeg...")
        with zipfile.ZipFile(str(tmp_zip), 'r') as z:
            for name in z.namelist():
                basename = Path(name).name.lower()
                if basename == "ffmpeg.exe":
                    with z.open(name) as src, open(str(ffmpeg_path), 'wb') as dst:
                        dst.write(src.read())
                elif basename == "ffprobe.exe":
                    with z.open(name) as src, open(str(ffprobe_path), 'wb') as dst:
                        dst.write(src.read())
        tmp_zip.unlink(missing_ok=True)
        if not ffmpeg_path.exists() or not ffprobe_path.exists():
            raise RuntimeError("Could not find ffmpeg/ffprobe in the downloaded archive.")
        return str(ffmpeg_path), str(ffprobe_path)
    except Exception as e:
        tmp_zip.unlink(missing_ok=True)
        raise RuntimeError(f"Failed to download FFmpeg: {e}") from e


def shell_join(args):
    if os.name == "nt":
        return subprocess.list2cmdline(args)
    return " ".join(shlex.quote(str(x)) for x in args)


@dataclass
class Job:
    input_path: str
    output_dir: str
    operation: str
    start_time: float
    end_time: float
    duration: float
    reencode: bool
    vcodec: str
    acodec: str
    crf: str
    preset: str
    abitrate: str
    extra_args: str
    container: str
    title: str


class FFmpegError(RuntimeError):
    pass


class FFmpegBackend:
    def __init__(self, on_status=None):
        self.ffmpeg = which_or_name("ffmpeg")
        self.ffprobe = which_or_name("ffprobe")
        self._on_status = on_status

    def check_tools(self):
        """Check if ffmpeg/ffprobe work. If not found, auto-download them."""
        for tool in (self.ffmpeg, self.ffprobe):
            try:
                subprocess.run(
                    [tool, "-version"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=True,
                    text=True,
                )
            except Exception:
                # Not found on PATH — try auto-download
                try:
                    ff, fp = download_ffmpeg(on_status=self._on_status)
                    self.ffmpeg = ff
                    self.ffprobe = fp
                    # Verify the downloaded binaries work
                    subprocess.run([self.ffmpeg, "-version"],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
                    subprocess.run([self.ffprobe, "-version"],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
                    if self._on_status:
                        self._on_status("FFmpeg downloaded and ready.")
                    return
                except Exception as dl_err:
                    raise FFmpegError(
                        f"FFmpeg not found and auto-download failed.\n\n"
                        f"Please install FFmpeg manually:\n"
                        f"  Windows: https://www.gyan.dev/ffmpeg/builds/\n"
                        f"  macOS: brew install ffmpeg\n"
                        f"  Linux: sudo apt install ffmpeg\n\n"
                        f"Error: {dl_err}"
                    ) from dl_err
                return  # only need to download once

    def get_version(self) -> str:
        """Get the installed FFmpeg version string."""
        try:
            result = subprocess.run(
                [self.ffmpeg, "-version"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            first_line = result.stdout.split("\n")[0] if result.stdout else "unknown"
            return first_line
        except Exception:
            return "unknown"

    def probe(self, path: str) -> dict:
        cmd = [
            self.ffprobe, "-v", "error",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise FFmpegError(result.stderr.strip() or "ffprobe failed")
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError as e:
            raise FFmpegError("Failed to parse ffprobe output") from e

        duration = float(data.get("format", {}).get("duration", 0) or 0)
        streams = data.get("streams", [])
        video = next((s for s in streams if s.get("codec_type") == "video"), None)
        audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
        return {
            "duration": duration,
            "video": video,
            "audio": audio,
            "format": data.get("format", {}),
            "streams": streams,
        }

    def build_output_path(self, job: Job) -> str:
        ext = job.container if job.container.startswith(".") else "." + job.container
        stem = safe_stem(job.input_path)
        if job.operation == "Between":
            suffix = f"_between_{int(job.start_time)}_{int(job.end_time)}"
        elif job.operation == "Before":
            suffix = f"_before_{int(job.end_time)}"
        elif job.operation == "After":
            suffix = f"_after_{int(job.start_time)}"
        else:
            suffix = "_export"
        out_name = f"{stem}{suffix}{ext}"
        return str(Path(job.output_dir) / out_name)

    def build_trim_cmd(self, job: Job, out_path: str):
        cmd = [self.ffmpeg, "-y", "-hide_banner", "-progress", "pipe:1", "-nostats"]

        # Accurate seeking choices:
        # Before: from 0 to end_time
        # After:  from start_time to EOF
        # Between: from start_time with duration end-start
        if job.operation == "Between":
            cmd += ["-ss", format_seconds(job.start_time)]
        elif job.operation == "After":
            cmd += ["-ss", format_seconds(job.start_time)]

        cmd += ["-i", job.input_path]

        if job.operation == "Between":
            cmd += ["-t", format_seconds(max(0.01, job.end_time - job.start_time))]
        elif job.operation == "Before":
            cmd += ["-t", format_seconds(max(0.01, job.end_time))]

        if job.reencode:
            cmd += ["-c:v", job.vcodec, "-preset", job.preset, "-crf", job.crf]
            cmd += ["-c:a", job.acodec, "-b:a", job.abitrate]
            cmd += ["-movflags", "+faststart"]
        else:
            cmd += ["-c", "copy"]

        if job.extra_args.strip():
            cmd += shlex.split(job.extra_args)

        cmd += [out_path]
        return cmd

    def build_preview_frame_cmd(self, input_path: str, t: float, out_jpg: str):
        return [
            self.ffmpeg, "-y", "-hide_banner",
            "-ss", format_seconds(t),
            "-i", input_path,
            "-frames:v", "1",
            "-q:v", "2",
            out_jpg,
        ]

    def build_preview_clip_cmd(self, input_path: str, start: float, end: float, out_path: str):
        start = max(0.0, start)
        end = max(start + 0.2, end)
        duration = min(12.0, end - start)
        return [
            self.ffmpeg, "-y", "-hide_banner",
            "-ss", format_seconds(start),
            "-i", input_path,
            "-t", format_seconds(duration),
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "23",
            "-c:a", "aac",
            "-b:a", "128k",
            "-movflags", "+faststart",
            out_path,
        ]

    def run_with_progress(self, cmd, on_progress, on_log):
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1,
        )
        latest = {}
        for raw in process.stdout:
            line = raw.rstrip("\n")
            on_log(line)
            if "=" in line:
                k, v = line.split("=", 1)
                latest[k.strip()] = v.strip()
                on_progress(dict(latest))
        process.wait()
        if process.returncode != 0:
            raise FFmpegError(f"FFmpeg exited with code {process.returncode}")

    def run_simple(self, cmd):
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        if result.returncode != 0:
            raise FFmpegError(result.stdout.strip() or "FFmpeg failed")
        return result.stdout


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        # Fit to screen — use 80% of screen size, capped at reasonable max
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        win_w = min(1280, int(screen_w * 0.8))
        win_h = min(900, int(screen_h * 0.8))
        x = (screen_w - win_w) // 2
        y = max(0, (screen_h - win_h) // 2 - 30)
        self.geometry(f"{win_w}x{win_h}+{x}+{y}")
        self.minsize(800, 600)

        self.config = load_config()
        self.backend = FFmpegBackend(on_status=lambda msg: self.log_queue.put(("log", msg)))
        self.media_info = None
        self.current_preview_image = None
        self.worker_thread = None
        self.log_queue = queue.Queue()
        self.jobs = []
        self.stop_requested = False

        self._build_variables()
        self._build_ui()
        self._build_menu()
        self._poll_log_queue()

        # Check FFmpeg on startup — auto-downloads if missing
        self._check_ffmpeg_startup()

        # Enable drag-and-drop if tkinterdnd2 is available
        self._setup_drag_drop()

    def _check_ffmpeg_startup(self):
        """Check FFmpeg availability, auto-download if needed, show version."""
        try:
            self.backend.check_tools()
            version = self.backend.get_version()
            self.log(f"✓ {version}")
        except Exception as e:
            self.log(str(e))
            messagebox.showwarning(APP_TITLE, str(e))

    def _setup_drag_drop(self):
        """Enable drag-and-drop file loading (works without extra deps on some platforms)."""
        try:
            # Try tkinterdnd2 if available
            import tkinterdnd2
        except ImportError:
            pass  # Drag-and-drop not available — that's fine

    def _build_menu(self):
        """Build the menu bar with File > Recent Files."""
        menubar = tk.Menu(self)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Open file...", command=self.pick_input, accelerator="Ctrl+O")
        
        # Recent files submenu
        self.recent_menu = tk.Menu(file_menu, tearoff=0)
        self._update_recent_menu()
        file_menu.add_cascade(label="Recent files", menu=self.recent_menu)
        
        file_menu.add_separator()
        file_menu.add_command(label="Check for FFmpeg updates", command=self._update_ffmpeg)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.quit)
        menubar.add_cascade(label="File", menu=file_menu)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="About", command=self._show_about)
        menubar.add_cascade(label="Help", menu=help_menu)

        self.config_menu = menubar
        self["menu"] = menubar
        self.bind_all("<Control-o>", lambda e: self.pick_input())

    def _update_recent_menu(self):
        """Refresh the recent files submenu."""
        self.recent_menu.delete(0, "end")
        recents = self.config.get("recent_files", [])
        if not recents:
            self.recent_menu.add_command(label="(no recent files)", state="disabled")
        else:
            for path in recents:
                display = Path(path).name if len(path) > 60 else path
                self.recent_menu.add_command(
                    label=display,
                    command=lambda p=path: self._open_recent(p)
                )

    def _open_recent(self, path: str):
        """Open a file from the recent files list."""
        if not Path(path).exists():
            messagebox.showerror(APP_TITLE, f"File not found:\n{path}")
            return
        self.input_path_var.set(path)
        self.load_media()

    def _update_ffmpeg(self):
        """Force re-download FFmpeg to get the latest version."""
        def work():
            try:
                # Delete existing to force re-download
                ext = ".exe" if os.name == "nt" else ""
                for name in ("ffmpeg", "ffprobe"):
                    p = FFMPEG_LOCAL_DIR / f"{name}{ext}"
                    p.unlink(missing_ok=True)
                ff, fp = download_ffmpeg(on_status=lambda msg: self.log_queue.put(("log", msg)))
                self.backend.ffmpeg = ff
                self.backend.ffprobe = fp
                version = self.backend.get_version()
                self.log_queue.put(("log", f"✓ FFmpeg updated: {version}"))
                self.after(0, lambda: messagebox.showinfo(APP_TITLE, f"FFmpeg updated.\n{version}"))
            except Exception as e:
                self.log_queue.put(("log", f"Update failed: {e}"))
                self.after(0, lambda: messagebox.showerror(APP_TITLE, str(e)))
        threading.Thread(target=work, daemon=True).start()

    def _show_about(self):
        messagebox.showinfo(APP_TITLE,
            f"{APP_TITLE}\n\n"
            f"A friendly video/audio trimming tool.\n"
            f"FFmpeg is downloaded automatically on first launch.\n\n"
            f"FFmpeg: {self.backend.get_version()}\n"
            f"FFmpeg location: {self.backend.ffmpeg}"
        )

    def _build_variables(self):
        self.input_path_var = tk.StringVar()
        self.output_dir_var = tk.StringVar(value=self.config.get("output_dir", str(Path.home() / "Videos")))
        self.operation_var = tk.StringVar(value="Between")
        self.reencode_var = tk.BooleanVar(value=True)
        self.vcodec_var = tk.StringVar(value="libx264")
        self.acodec_var = tk.StringVar(value="aac")
        self.crf_var = tk.StringVar(value="18")
        self.preset_var = tk.StringVar(value="medium")
        self.abitrate_var = tk.StringVar(value="192k")
        self.extra_args_var = tk.StringVar()
        self.container_var = tk.StringVar(value="mp4")
        self.job_title_var = tk.StringVar(value="Job")

        self.duration_var = tk.StringVar(value="Duration: —")
        self.resolution_var = tk.StringVar(value="Resolution: —")
        self.codec_var = tk.StringVar(value="Codecs: —")
        self.selection_var = tk.StringVar(value="Selection: —")
        self.progress_text_var = tk.StringVar(value="Idle")

        self.start_scale_var = tk.DoubleVar(value=0.0)
        self.end_scale_var = tk.DoubleVar(value=0.0)
        self.preview_scale_var = tk.DoubleVar(value=0.0)

    def _build_ui(self):
        outer = ttk.Frame(self, padding=10)
        outer.pack(fill="both", expand=True)

        top = ttk.Frame(outer)
        top.pack(fill="x")

        ttk.Label(top, text="Input file").grid(row=0, column=0, sticky="w")
        ttk.Entry(top, textvariable=self.input_path_var, width=95).grid(row=0, column=1, sticky="ew", padx=6)
        ttk.Button(top, text="Browse", command=self.pick_input).grid(row=0, column=2, padx=4)
        ttk.Button(top, text="Load", command=self.load_media).grid(row=0, column=3)

        ttk.Label(top, text="Output folder").grid(row=1, column=0, sticky="w", pady=(6,0))
        ttk.Entry(top, textvariable=self.output_dir_var, width=95).grid(row=1, column=1, sticky="ew", padx=6, pady=(6,0))
        ttk.Button(top, text="Browse", command=self.pick_output_dir).grid(row=1, column=2, padx=4, pady=(6,0))

        top.columnconfigure(1, weight=1)

        meta = ttk.LabelFrame(outer, text="Media info", padding=8)
        meta.pack(fill="x", pady=10)
        ttk.Label(meta, textvariable=self.duration_var).grid(row=0, column=0, sticky="w", padx=8)
        ttk.Label(meta, textvariable=self.resolution_var).grid(row=0, column=1, sticky="w", padx=8)
        ttk.Label(meta, textvariable=self.codec_var).grid(row=0, column=2, sticky="w", padx=8)

        center = ttk.Panedwindow(outer, orient="horizontal")
        center.pack(fill="both", expand=True)

        left = ttk.Frame(center, padding=4)
        right = ttk.Frame(center, padding=4)
        center.add(left, weight=3)
        center.add(right, weight=2)

        self._build_timeline_panel(left)
        self._build_queue_panel(right)

        bottom = ttk.LabelFrame(outer, text="Output log", padding=8)
        bottom.pack(fill="both", expand=True, pady=(10,0))

        barrow = ttk.Frame(bottom)
        barrow.pack(fill="x", pady=(0,6))
        self.progressbar = ttk.Progressbar(barrow, maximum=100)
        self.progressbar.pack(side="left", fill="x", expand=True)
        ttk.Label(barrow, textvariable=self.progress_text_var, width=28).pack(side="left", padx=(8,0))

        self.log_text = tk.Text(bottom, wrap="none", height=14)
        self.log_text.pack(fill="both", expand=True)
        self.log_text.configure(state="disabled")

    def _build_timeline_panel(self, parent):
        preview_box = ttk.LabelFrame(parent, text="Timeline trim + preview", padding=8)
        preview_box.pack(fill="both", expand=True)

        canvas_wrap = ttk.Frame(preview_box)
        canvas_wrap.pack(fill="both", expand=False)
        self.preview_label = ttk.Label(canvas_wrap, text="Load a media file to generate previews.", anchor="center")
        self.preview_label.pack(fill="both", expand=True, pady=(0,10))

        self.operation_combo = ttk.Combobox(
            preview_box,
            textvariable=self.operation_var,
            values=["Between", "Before", "After"],
            state="readonly",
            width=12,
        )
        row1 = ttk.Frame(preview_box)
        row1.pack(fill="x", pady=4)
        ttk.Label(row1, text="Operation").pack(side="left")
        self.operation_combo.pack(in_=row1, side="left", padx=(8,16))
        ttk.Label(row1, textvariable=self.selection_var).pack(side="left")

        ttk.Label(preview_box, text="Start").pack(anchor="w")
        self.start_scale = tk.Scale(
            preview_box,
            orient="horizontal",
            resolution=0.1,
            showvalue=False,
            variable=self.start_scale_var,
            command=lambda _=None: self.on_scales_changed("start"),
        )
        self.start_scale.pack(fill="x")

        ttk.Label(preview_box, text="End").pack(anchor="w", pady=(4,0))
        self.end_scale = tk.Scale(
            preview_box,
            orient="horizontal",
            resolution=0.1,
            showvalue=False,
            variable=self.end_scale_var,
            command=lambda _=None: self.on_scales_changed("end"),
        )
        self.end_scale.pack(fill="x")

        ttk.Label(preview_box, text="Preview position").pack(anchor="w", pady=(4,0))
        self.preview_scale = tk.Scale(
            preview_box,
            orient="horizontal",
            resolution=0.1,
            showvalue=False,
            variable=self.preview_scale_var,
            command=lambda _=None: self.update_selection_text(),
        )
        self.preview_scale.pack(fill="x")

        btns = ttk.Frame(preview_box)
        btns.pack(fill="x", pady=8)
        ttk.Button(btns, text="Preview frame", command=self.preview_frame).pack(side="left")
        ttk.Button(btns, text="Preview 12s clip", command=self.preview_clip).pack(side="left", padx=6)
        ttk.Button(btns, text="Set start ← preview", command=self.set_start_from_preview).pack(side="left")
        ttk.Button(btns, text="Set end ← preview", command=self.set_end_from_preview).pack(side="left", padx=6)

        export = ttk.LabelFrame(parent, text="Encoding / export settings", padding=8)
        export.pack(fill="x", pady=10)

        r = 0
        ttk.Label(export, text="Job title").grid(row=r, column=0, sticky="w")
        ttk.Entry(export, textvariable=self.job_title_var, width=22).grid(row=r, column=1, sticky="w", padx=6)
        ttk.Label(export, text="Container").grid(row=r, column=2, sticky="w")
        ttk.Combobox(export, textvariable=self.container_var, values=["mp4", "mkv", "mov"], state="readonly", width=8).grid(row=r, column=3, sticky="w", padx=6)
        ttk.Checkbutton(export, text="Re-encode (recommended for OBS / accurate cuts)", variable=self.reencode_var).grid(row=r, column=4, columnspan=3, sticky="w", padx=(8,0))
        r += 1

        ttk.Label(export, text="Video codec").grid(row=r, column=0, sticky="w", pady=(6,0))
        ttk.Combobox(export, textvariable=self.vcodec_var, values=["libx264", "libx265", "mpeg4"], width=12, state="readonly").grid(row=r, column=1, sticky="w", padx=6, pady=(6,0))
        ttk.Label(export, text="Audio codec").grid(row=r, column=2, sticky="w", pady=(6,0))
        ttk.Combobox(export, textvariable=self.acodec_var, values=["aac", "libmp3lame", "copy"], width=12, state="readonly").grid(row=r, column=3, sticky="w", padx=6, pady=(6,0))
        ttk.Label(export, text="CRF").grid(row=r, column=4, sticky="w", pady=(6,0))
        ttk.Combobox(export, textvariable=self.crf_var, values=["14", "18", "20", "23", "28"], width=8, state="readonly").grid(row=r, column=5, sticky="w", padx=6, pady=(6,0))
        ttk.Label(export, text="Preset").grid(row=r, column=6, sticky="w", pady=(6,0))
        ttk.Combobox(export, textvariable=self.preset_var, values=["ultrafast", "veryfast", "fast", "medium", "slow"], width=12, state="readonly").grid(row=r, column=7, sticky="w", padx=6, pady=(6,0))
        r += 1

        ttk.Label(export, text="Audio bitrate").grid(row=r, column=0, sticky="w", pady=(6,0))
        ttk.Combobox(export, textvariable=self.abitrate_var, values=["96k", "128k", "192k", "256k", "320k"], width=12, state="readonly").grid(row=r, column=1, sticky="w", padx=6, pady=(6,0))
        ttk.Label(export, text="Extra FFmpeg args").grid(row=r, column=2, sticky="w", pady=(6,0))
        ttk.Entry(export, textvariable=self.extra_args_var, width=55).grid(row=r, column=3, columnspan=5, sticky="ew", padx=6, pady=(6,0))

        for c in range(8):
            export.columnconfigure(c, weight=1 if c in (3, 7) else 0)

        actions = ttk.Frame(parent)
        actions.pack(fill="x")
        ttk.Button(actions, text="Add current job to queue", command=self.add_current_job).pack(side="left")
        ttk.Button(actions, text="Run current job now", command=self.run_current_job_now).pack(side="left", padx=6)

    def _build_queue_panel(self, parent):
        queue_box = ttk.LabelFrame(parent, text="Batch processing queue", padding=8)
        queue_box.pack(fill="both", expand=True)

        cols = ("title", "operation", "input", "selection", "output")
        self.tree = ttk.Treeview(queue_box, columns=cols, show="headings", height=16)
        self.tree.heading("title", text="Title")
        self.tree.heading("operation", text="Operation")
        self.tree.heading("input", text="Input")
        self.tree.heading("selection", text="Selection")
        self.tree.heading("output", text="Output")
        self.tree.column("title", width=120, anchor="w")
        self.tree.column("operation", width=80, anchor="w")
        self.tree.column("input", width=180, anchor="w")
        self.tree.column("selection", width=160, anchor="w")
        self.tree.column("output", width=180, anchor="w")
        self.tree.pack(fill="both", expand=True)

        controls = ttk.Frame(queue_box)
        controls.pack(fill="x", pady=(8,0))
        ttk.Button(controls, text="Remove selected", command=self.remove_selected_job).pack(side="left")
        ttk.Button(controls, text="Clear queue", command=self.clear_queue).pack(side="left", padx=6)
        ttk.Button(controls, text="Save queue JSON", command=self.save_queue).pack(side="left")
        ttk.Button(controls, text="Load queue JSON", command=self.load_queue_file).pack(side="left", padx=6)

        run = ttk.Frame(queue_box)
        run.pack(fill="x", pady=(8,0))
        ttk.Button(run, text="Run batch queue", command=self.run_batch_queue).pack(side="left")
        ttk.Button(run, text="Stop after current job", command=self.request_stop).pack(side="left", padx=6)

    def log(self, text: str):
        self.log_queue.put(("log", text))

    def set_progress(self, value: float, label: str):
        self.log_queue.put(("progress", (value, label)))

    def _poll_log_queue(self):
        try:
            while True:
                kind, payload = self.log_queue.get_nowait()
                if kind == "log":
                    self.log_text.configure(state="normal")
                    self.log_text.insert("end", payload + "\n")
                    self.log_text.see("end")
                    self.log_text.configure(state="disabled")
                elif kind == "progress":
                    value, label = payload
                    self.progressbar["value"] = max(0, min(100, value))
                    self.progress_text_var.set(label)
        except queue.Empty:
            pass
        self.after(120, self._poll_log_queue)

    def pick_input(self):
        path = filedialog.askopenfilename(
            title="Choose media file",
            filetypes=[("Media files", " ".join("*" + x for x in VIDEO_EXTS + AUDIO_EXTS)), ("All files", "*.*")]
        )
        if path:
            self.input_path_var.set(path)

    def pick_output_dir(self):
        path = filedialog.askdirectory(title="Choose output folder")
        if path:
            self.output_dir_var.set(path)

    def load_media(self):
        path = self.input_path_var.get().strip()
        if not path:
            messagebox.showerror(APP_TITLE, "Choose an input file first.")
            return
        if not Path(path).exists():
            messagebox.showerror(APP_TITLE, "The input file does not exist.")
            return
        try:
            info = self.backend.probe(path)
        except Exception as e:
            messagebox.showerror(APP_TITLE, str(e))
            return

        self.media_info = info
        dur = max(0.1, info["duration"])
        self.duration_var.set(f"Duration: {format_seconds(dur)}")
        if info["video"]:
            w = info["video"].get("width", "—")
            h = info["video"].get("height", "—")
            vcodec = info["video"].get("codec_name", "—")
        else:
            w, h, vcodec = "—", "—", "—"
        acodec = info["audio"].get("codec_name", "—") if info["audio"] else "—"
        self.resolution_var.set(f"Resolution: {w}×{h}")
        self.codec_var.set(f"Codecs: video {vcodec} / audio {acodec}")

        for scale in (self.start_scale, self.end_scale, self.preview_scale):
            scale.configure(from_=0, to=dur)
        self.start_scale_var.set(0.0)
        self.end_scale_var.set(dur)
        self.preview_scale_var.set(min(dur / 2, 30.0))
        self.job_title_var.set(safe_stem(path))
        self.update_selection_text()
        self.log(f"Loaded media: {path}")

        # Save to recent files
        self.config = add_recent_file(self.config, path)
        self.config["output_dir"] = self.output_dir_var.get()
        save_config(self.config)
        self._update_recent_menu()

    def on_scales_changed(self, changed):
        if not self.media_info:
            return
        start = self.start_scale_var.get()
        end = self.end_scale_var.get()
        dur = self.media_info["duration"]
        if changed == "start" and start > end:
            self.end_scale_var.set(start)
        elif changed == "end" and end < start:
            self.start_scale_var.set(end)
        self.preview_scale_var.set(min(max(self.preview_scale_var.get(), 0.0), dur))
        self.update_selection_text()

    def update_selection_text(self):
        op = self.operation_var.get()
        start = self.start_scale_var.get()
        end = self.end_scale_var.get()
        preview = self.preview_scale_var.get()
        if op == "Between":
            text = f"Selection: {format_seconds(start)} → {format_seconds(end)}"
        elif op == "Before":
            text = f"Selection: 00:00:00.000 → {format_seconds(end)}"
        else:
            text = f"Selection: {format_seconds(start)} → end"
        text += f" | Preview @ {format_seconds(preview)}"
        self.selection_var.set(text)

    def set_start_from_preview(self):
        self.start_scale_var.set(self.preview_scale_var.get())
        self.on_scales_changed("start")

    def set_end_from_preview(self):
        self.end_scale_var.set(self.preview_scale_var.get())
        self.on_scales_changed("end")

    def preview_frame(self):
        if not self.media_info:
            messagebox.showerror(APP_TITLE, "Load a media file first.")
            return
        temp_dir = Path(tempfile.gettempdir()) / "ffmpeg_pro_studio_v2"
        temp_dir.mkdir(parents=True, exist_ok=True)
        out_jpg = str(temp_dir / "preview_frame.jpg")
        t = self.preview_scale_var.get()
        cmd = self.backend.build_preview_frame_cmd(self.input_path_var.get(), t, out_jpg)

        def work():
            try:
                self.set_progress(0, "Generating preview frame...")
                self.backend.run_simple(cmd)
                pil_img = Image.open(out_jpg)
                pil_img.thumbnail((720, 405))
                img = ImageTk.PhotoImage(pil_img)
                self.current_preview_image = img
                self.after(0, lambda: self.preview_label.configure(image=img, text=""))
                self.set_progress(100, f"Preview frame @ {format_seconds(t)}")
                self.log(f"Preview frame created: {out_jpg}")
            except Exception as e:
                self.set_progress(0, "Idle")
                self.log(str(e))
                self.after(0, lambda: messagebox.showerror(APP_TITLE, str(e)))

        threading.Thread(target=work, daemon=True).start()

    def preview_clip(self):
        if not self.media_info:
            messagebox.showerror(APP_TITLE, "Load a media file first.")
            return
        temp_dir = Path(tempfile.gettempdir()) / "ffmpeg_pro_studio_v2"
        temp_dir.mkdir(parents=True, exist_ok=True)
        start = self.start_scale_var.get()
        end = self.end_scale_var.get()
        if self.operation_var.get() == "Before":
            start, end = 0.0, min(12.0, self.end_scale_var.get())
        elif self.operation_var.get() == "After":
            start = self.start_scale_var.get()
            end = min(self.media_info["duration"], start + 12.0)
        elif end - start <= 0.2:
            end = min(self.media_info["duration"], start + 12.0)
        out_path = str(temp_dir / "preview_clip.mp4")
        cmd = self.backend.build_preview_clip_cmd(self.input_path_var.get(), start, end, out_path)

        def work():
            try:
                self.set_progress(0, "Creating preview clip...")
                self.backend.run_simple(cmd)
                self.set_progress(100, "Opening preview clip...")
                self.log(f"Preview clip created: {out_path}")
                self.open_with_default_app(out_path)
            except Exception as e:
                self.set_progress(0, "Idle")
                self.log(str(e))
                self.after(0, lambda: messagebox.showerror(APP_TITLE, str(e)))

        threading.Thread(target=work, daemon=True).start()

    def open_with_default_app(self, path: str):
        try:
            if sys.platform.startswith("win"):
                os.startfile(path)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception as e:
            self.log(f"Could not open {path}: {e}")

    def build_job_from_ui(self) -> Job:
        if not self.media_info:
            raise FFmpegError("Load a media file first.")
        input_path = self.input_path_var.get().strip()
        output_dir = self.output_dir_var.get().strip()
        if not input_path or not Path(input_path).exists():
            raise FFmpegError("Input file is missing.")
        if not output_dir:
            raise FFmpegError("Output folder is missing.")
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        op = self.operation_var.get()
        start = self.start_scale_var.get()
        end = self.end_scale_var.get()
        duration = self.media_info["duration"]

        if op == "Between" and end <= start:
            raise FFmpegError("End time must be greater than start time.")
        if op == "Before" and end <= 0:
            raise FFmpegError("End time must be greater than zero.")
        if op == "After" and start >= duration:
            raise FFmpegError("Start time must be less than the media duration.")

        return Job(
            input_path=input_path,
            output_dir=output_dir,
            operation=op,
            start_time=start,
            end_time=end,
            duration=duration,
            reencode=self.reencode_var.get(),
            vcodec=self.vcodec_var.get(),
            acodec=self.acodec_var.get(),
            crf=self.crf_var.get(),
            preset=self.preset_var.get(),
            abitrate=self.abitrate_var.get(),
            extra_args=self.extra_args_var.get(),
            container=self.container_var.get(),
            title=self.job_title_var.get().strip() or safe_stem(input_path),
        )

    def selection_summary(self, job: Job) -> str:
        if job.operation == "Between":
            return f"{format_seconds(job.start_time)} → {format_seconds(job.end_time)}"
        if job.operation == "Before":
            return f"00:00:00.000 → {format_seconds(job.end_time)}"
        return f"{format_seconds(job.start_time)} → end"

    def add_current_job(self):
        try:
            job = self.build_job_from_ui()
        except Exception as e:
            messagebox.showerror(APP_TITLE, str(e))
            return
        self.jobs.append(job)
        out_path = self.backend.build_output_path(job)
        self.tree.insert(
            "",
            "end",
            values=(
                job.title,
                job.operation,
                Path(job.input_path).name,
                self.selection_summary(job),
                Path(out_path).name,
            ),
        )
        self.log(f"Queued job: {job.title}")

    def remove_selected_job(self):
        selected = self.tree.selection()
        if not selected:
            return
        indices = [self.tree.index(item) for item in selected]
        for item in selected:
            self.tree.delete(item)
        for idx in sorted(indices, reverse=True):
            del self.jobs[idx]
        self.log("Removed selected job(s) from queue.")

    def clear_queue(self):
        self.jobs.clear()
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.log("Queue cleared.")

    def save_queue(self):
        if not self.jobs:
            messagebox.showinfo(APP_TITLE, "Queue is empty.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON", "*.json")],
            title="Save queue"
        )
        if not path:
            return
        with open(path, "w", encoding="utf-8") as f:
            json.dump([asdict(j) for j in self.jobs], f, indent=2)
        self.log(f"Saved queue: {path}")

    def load_queue_file(self):
        path = filedialog.askopenfilename(filetypes=[("JSON", "*.json")], title="Load queue")
        if not path:
            return
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.clear_queue()
        for item in data:
            job = Job(**item)
            self.jobs.append(job)
            out_path = self.backend.build_output_path(job)
            self.tree.insert(
                "",
                "end",
                values=(
                    job.title,
                    job.operation,
                    Path(job.input_path).name,
                    self.selection_summary(job),
                    Path(out_path).name,
                ),
            )
        self.log(f"Loaded queue: {path}")

    def request_stop(self):
        self.stop_requested = True
        self.log("Stop requested. The app will stop after the current job finishes.")

    def run_current_job_now(self):
        try:
            job = self.build_job_from_ui()
        except Exception as e:
            messagebox.showerror(APP_TITLE, str(e))
            return
        self._start_worker([job])

    def run_batch_queue(self):
        if not self.jobs:
            messagebox.showinfo(APP_TITLE, "Queue is empty.")
            return
        self._start_worker(list(self.jobs))

    def _start_worker(self, jobs):
        if self.worker_thread and self.worker_thread.is_alive():
            messagebox.showwarning(APP_TITLE, "A job is already running.")
            return
        self.stop_requested = False
        self.worker_thread = threading.Thread(target=self._run_jobs, args=(jobs,), daemon=True)
        self.worker_thread.start()

    def _run_jobs(self, jobs):
        total_jobs = len(jobs)
        for idx, job in enumerate(jobs, start=1):
            out_path = self.backend.build_output_path(job)
            cmd = self.backend.build_trim_cmd(job, out_path)
            self.log("")
            self.log("=" * 80)
            self.log(f"Starting job {idx}/{total_jobs}: {job.title}")
            self.log(shell_join(cmd))

            expected = (
                max(0.01, job.end_time - job.start_time)
                if job.operation == "Between"
                else max(0.01, job.end_time)
                if job.operation == "Before"
                else max(0.01, job.duration - job.start_time)
            )

            def on_log(line):
                self.log(line)

            def on_progress(data):
                # FFmpeg progress output: out_time_us is microseconds,
                # out_time_ms is also microseconds (misleading name in FFmpeg).
                out_us = data.get("out_time_us") or data.get("out_time_ms")
                pct = 0.0
                if out_us is not None:
                    try:
                        micro = float(out_us)
                        seconds = micro / 1_000_000.0
                        pct = min(100.0, (seconds / expected) * 100.0)
                    except Exception:
                        pct = 0.0
                label = f"Job {idx}/{total_jobs}: {job.title} ({pct:.1f}%)"
                self.set_progress(pct, label)

            try:
                self.backend.run_with_progress(cmd, on_progress, on_log)
                self.set_progress(100, f"Finished {job.title}")
                self.log(f"Output: {out_path}")
            except Exception as e:
                self.log(f"ERROR: {e}")
                self.set_progress(0, "Failed")
                self.after(0, lambda err=str(e): messagebox.showerror(APP_TITLE, err))
                return

            if self.stop_requested:
                self.log("Stopping after current job, as requested.")
                break

        self.set_progress(100, "All done")

def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
