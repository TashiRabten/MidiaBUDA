# FFmpeg Pro Studio — Requirements

## Project Overview
A complete, user-friendly video/audio editor GUI wrapping FFmpeg. Built with Python 3.12 + PyQt6. Packages as standalone .exe (Windows) and .app (macOS).

## Environment
- Python: `D:\envs\python312\python.exe`
- Dependencies: PyQt6, Pillow
- FFmpeg: auto-downloaded to `~/.ffmpeg_pro_studio/` on first launch
- Build: PyInstaller --onefile --windowed
- Spec: `APP/FFMPEG_STUDIO_SPEC.md`
- Existing backend code: `APP/ffmpeg_pro_studio_v2_pillow.py` (FFmpegBackend class, Job dataclass, download_ffmpeg, config helpers — reuse as-is, replace only the tkinter UI)

## Functional Requirements

### FR-1: FFmpeg Auto-Management
- Auto-download FFmpeg on first launch if not on PATH
- Store in `~/.ffmpeg_pro_studio/ffmpeg[.exe]` and `ffprobe[.exe]`
- Menu option to force-update to latest build
- Show version in About dialog and startup log
- Windows: download from BtbN GitHub releases
- macOS: download from evermeet.cx

### FR-2: File Loading
- Browse button + text field for input file
- Drag-and-drop files onto the window
- Recent files menu (last 10, persisted in config.json)
- Ctrl+O keyboard shortcut
- Auto-load on double-click from recent files
- Support: .mp4, .mkv, .mov, .avi, .webm, .flv, .m4v, .ts, .mts, .mp3, .wav, .m4a, .aac, .flac, .ogg, .opus

### FR-3: Media Info Display
- Duration (HH:MM:SS.mmm)
- Resolution (WxH)
- Video codec name
- Audio codec name
- File size
- Bitrate

### FR-4: Embedded Video Preview
- Preview panel embedded in main window (NOT a popup)
- Resizes proportionally with window
- Extract frame at any position via FFmpeg → PIL → QPixmap
- Frame-by-frame step buttons (|◄ ► ►|)
- Scrub through video by dragging timeline slider

### FR-5: Timeline Scrubber
- Horizontal slider showing full duration
- Start marker (draggable)
- End marker (draggable)
- Preview position indicator
- Timecode display at cursor
- "Set start from preview" / "Set end from preview" buttons

### FR-6: Operation Tabs
Each tab is a different FFmpeg operation:

#### Tab 1: Trim (✂)
- Between / Before / After modes
- Uses start/end markers from timeline
- Re-encode or stream copy option

#### Tab 2: Convert (🔄)
- Input any format → output any format
- Presets: "Web (MP4 H.264)", "Archive (MKV H.265)", "Mobile", "GIF"
- Audio-only conversion (MP3, AAC, FLAC, WAV)

#### Tab 3: Merge (🔗)
- Add multiple files to merge list
- Drag to reorder
- Concatenate clips

#### Tab 4: Extract Audio (🎵)
- One-click extract audio from video
- Choose format (MP3, WAV, FLAC, AAC)
- Bitrate selection

#### Tab 5: Compress (📦)
- Target file size slider ("Make it under 25MB")
- Quality presets (High / Medium / Low / Custom)
- Two-pass encoding for accurate size targeting

#### Tab 6: Screenshots (🖼)
- Extract frame at current position
- Extract frames at interval (every N seconds)
- Contact sheet / thumbnail grid

#### Tab 7: Resize/Crop (📐)
- Presets: 1080p, 720p, 480p, Instagram Square, TikTok 9:16
- Custom resolution
- Rotate/flip

### FR-7: Export Settings
- Video codec: libx264, libx265, mpeg4
- Audio codec: aac, libmp3lame, copy
- CRF: 14, 18, 20, 23, 28
- Preset: ultrafast, veryfast, fast, medium, slow
- Audio bitrate: 96k, 128k, 192k, 256k, 320k
- Container: mp4, mkv, mov
- Extra FFmpeg args field
- Output folder selection (remembered between sessions)

### FR-8: Batch Queue
- Add jobs to queue from any tab
- Queue table showing: title, operation, input, selection, output
- Remove selected / Clear queue
- Save queue as JSON / Load queue from JSON
- Run batch queue with per-job progress
- Stop after current job button

### FR-9: Progress & Logging
- Per-job progress bar with percentage
- Overall batch progress
- Estimated time remaining
- Collapsible log panel showing FFmpeg output
- Friendly error messages with expandable technical details

### FR-10: Configuration Persistence
- Recent files list (max 10)
- Last output directory
- Last used settings per tab
- Window size and position
- Stored in `~/.ffmpeg_pro_studio/config.json`

## Non-Functional Requirements

### NFR-1: Startup Time
- App window visible within 2 seconds
- FFmpeg download (first launch only) shows progress dialog

### NFR-2: Responsiveness
- All FFmpeg operations run in background threads
- UI never freezes during encoding
- Cancel button responsive within 1 second

### NFR-3: Cross-Platform
- Windows 10/11 (primary)
- macOS 12+ (secondary)
- Single codebase, platform-specific only for FFmpeg download URLs and file paths

### NFR-4: Package Size
- .exe under 50MB (excluding FFmpeg)
- FFmpeg downloaded separately (~90MB Windows, ~30MB macOS)

### NFR-5: Error Recovery
- Graceful handling of corrupt/unsupported media files
- FFmpeg process crash doesn't crash the app
- Network failure during FFmpeg download shows retry option
