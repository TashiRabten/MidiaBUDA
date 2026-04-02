# FFmpeg Pro Studio — Full Rewrite Spec

## Vision
A complete, user-friendly video/audio editor GUI wrapping FFmpeg. Think "HandBrake meets DaVinci Resolve Lite" — powerful but approachable for naive users.

## Architecture
- Python 3.12 + tkinter (or consider PyQt6 for richer widgets)
- FFmpeg auto-downloaded on first launch (already implemented)
- Single .exe via PyInstaller
- Config persisted in ~/.ffmpeg_pro_studio/

## Layout (Professional App Style)

```
┌─────────────────────────────────────────────────────────────┐
│ Menu Bar: File | Edit | Tools | Help                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│              EMBEDDED VIDEO PREVIEW                         │
│           (resizes with window, NOT a popup)                │
│              Shows current frame inline                     │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│ ◄──────────[====TIMELINE SCRUBBER====]──────────► 00:05:23  │
│ [|◄] [►] [►|]  Start: [00:01:00]  End: [00:03:30]         │
├──────────────────────┬──────────────────────────────────────┤
│  OPERATION TABS      │  OUTPUT SETTINGS                     │
│  ┌─────────────────┐ │  Format: [mp4 ▼]                    │
│  │ ✂ Trim          │ │  Video: [H.264 ▼] CRF: [18 ▼]      │
│  │ 🔄 Convert      │ │  Audio: [AAC ▼] Bitrate: [192k ▼]   │
│  │ 🔗 Merge        │ │  Preset: [medium ▼]                 │
│  │ 🎵 Extract Audio│ │  Resolution: [Original ▼]            │
│  │ 📦 Compress     │ │  [Export] [Add to Queue]             │
│  │ 🖼 Screenshots  │ │                                      │
│  │ 📐 Resize/Crop  │ │                                      │
│  └─────────────────┘ │                                      │
├──────────────────────┴──────────────────────────────────────┤
│ BATCH QUEUE                                                 │
│ [Job 1: Trim video.mp4 00:01-00:03] [✓ Done]              │
│ [Job 2: Convert audio.wav → mp3]    [⏳ Running 45%]       │
│ [Run All] [Stop] [Clear]                                    │
├─────────────────────────────────────────────────────────────┤
│ LOG: FFmpeg output (collapsible)                            │
└─────────────────────────────────────────────────────────────┘
```

## Operations (Tabs)

### 1. Trim (✂)
- Visual timeline with start/end markers
- Preview frame at any position (inline, not popup)
- Between / Before / After modes
- Frame-accurate or keyframe-based cutting

### 2. Convert (🔄)
- Input any format → output any format
- Presets: "Web (MP4 H.264)", "Archive (MKV H.265)", "Mobile", "GIF"
- Audio-only conversion (MP3, AAC, FLAC, WAV)
- Subtitle extraction/embedding

### 3. Merge (🔗)
- Drag files to reorder
- Concatenate multiple clips
- Crossfade option

### 4. Extract Audio (🎵)
- One-click extract audio from video
- Choose format (MP3, WAV, FLAC, AAC)
- Bitrate selection

### 5. Compress (📦)
- Target file size slider ("Make it under 25MB for Discord")
- Quality presets (High / Medium / Low / Custom)
- Two-pass encoding for accurate size targeting

### 6. Screenshots (🖼)
- Extract frame at current position
- Extract frames at interval (every N seconds)
- Contact sheet / thumbnail grid

### 7. Resize/Crop (📐)
- Common presets: 1080p, 720p, 480p, Instagram Square, TikTok 9:16
- Custom resolution
- Crop with visual preview
- Rotate/flip

## User-Friendly Features

### First Launch
- Auto-download FFmpeg with progress bar
- Welcome dialog explaining what the app does
- Sample video to try with (optional)

### File Handling
- Drag-and-drop files onto the window
- Recent files in File menu
- Double-click to open associated files
- Output folder remembered between sessions

### Preview
- EMBEDDED in the main window (Canvas widget with PIL)
- Resizes proportionally with the window
- Scrub through video by dragging timeline
- Frame-by-frame step buttons

### Progress
- Per-job progress bar with percentage and ETA
- Overall batch progress
- Estimated time remaining
- Cancel button per job

### Error Handling
- Friendly error messages (not raw FFmpeg output)
- "FFmpeg says:" expandable section for technical details
- Suggestions for common errors (codec not supported, etc.)

## Technical Notes

### Embedded Preview
Use PIL to decode frames extracted by FFmpeg, display in a tkinter Canvas:
```python
# Extract frame → temp jpg → PIL.Image → ImageTk.PhotoImage → Canvas
cmd = [ffmpeg, "-ss", time, "-i", input, "-frames:v", "1", "-q:v", "2", temp.jpg]
img = Image.open(temp.jpg)
img.thumbnail((canvas_width, canvas_height))  # fit to canvas
photo = ImageTk.PhotoImage(img)
canvas.create_image(0, 0, anchor="nw", image=photo)
```

### Timeline Scrubber
- tk.Scale widget with custom styling
- Or Canvas-based custom widget for more control
- Shows timecode at cursor position

### Dependencies
- Python 3.12+
- Pillow (PIL) — image handling
- tkinter — GUI (built into Python)
- FFmpeg — auto-downloaded

### Build
- PyInstaller --onefile --windowed
- Windows: .exe
- macOS: .app via py2app or PyInstaller
