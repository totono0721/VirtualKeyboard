"""Application bootstrap helpers."""
from __future__ import annotations

import sys

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from .keyboard_window import KeyboardWindow
from .winapi import kernel32


def main() -> int:
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    if hasattr(kernel32, "SetProcessDPIAware"):
        try:
            kernel32.SetProcessDPIAware()
        except Exception:
            pass
    app = QApplication(sys.argv)
    window = KeyboardWindow()
    window.resize(400, 200)
    window.show()
    return app.exec()
