from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("MeshCore Tracker")
    app.setOrganizationName("MeshCore Tracker")

    window = MainWindow()
    window.resize(1400, 850)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
