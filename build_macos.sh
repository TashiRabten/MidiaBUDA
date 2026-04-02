#!/bin/bash
# Build MediaBUDA (PyQt6) as standalone .app for macOS
# Run from the TradutorBUDA root directory:
#   cd ~/APPS/TradutorBUDA
#   bash APP/build_macos.sh
# Requires: pip install pyinstaller pyqt6 pillow

echo "Building MediaBUDA..."
pyinstaller --onefile --windowed \
    --name "MediaBUDA" \
    --icon "APP/icons/pramana.icns" \
    --add-data "APP/icons:APP/icons" \
    --add-data "APP/ffmpeg_pro_studio_v2_pillow.py:APP" \
    --add-data "APP/main_window.py:APP" \
    --add-data "APP/preview_panel.py:APP" \
    --add-data "APP/timeline_scrubber.py:APP" \
    --add-data "APP/operation_tabs.py:APP" \
    --add-data "APP/export_settings.py:APP" \
    --add-data "APP/batch_queue.py:APP" \
    --add-data "APP/worker_thread.py:APP" \
    --add-data "APP/ui_colors.py:APP" \
    --add-data "APP/autoupdater.py:APP" \
    --hidden-import PIL \
    --hidden-import PyQt6 \
    --hidden-import PyQt6.QtCore \
    --hidden-import PyQt6.QtGui \
    --hidden-import PyQt6.QtWidgets \
    APP/main.py

echo ""
echo "Build complete! Output: dist/MediaBUDA.app"
echo "FFmpeg is downloaded automatically on first launch."
