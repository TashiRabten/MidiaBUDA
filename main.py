"""MediaBUDA — PyQt6 Entry Point."""
import os
import sys

# Ensure the workspace root is on sys.path so 'APP' package is importable
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

from APP.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("MediaBUDA")
    app.setOrganizationName("MediaBUDA")

    # Set application icon (use .ico for Windows taskbar)
    icon_path = os.path.join(os.path.dirname(__file__), "icons", "pramana.ico")
    if not os.path.exists(icon_path):
        icon_path = os.path.join(os.path.dirname(__file__), "icons", "BUDA.png")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
