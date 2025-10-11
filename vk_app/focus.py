"""Utility to restore window focus after triggering a key."""
from __future__ import annotations

from typing import List, Optional

from ctypes import byref

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QMainWindow, QWidget

from .winapi import kernel32, user32, wintypes


class FocusKeeper:
    """Tracks and restores the previously focused window."""

    def __init__(self, main_window: QMainWindow, poll_interval_ms: int = 200) -> None:
        self._main_hwnd = int(main_window.winId())
        self._tracked_hwnds: List[int] = [self._main_hwnd]
        self._foreground_hwnd: Optional[int] = None
        self._timer = QTimer(main_window)
        self._timer.timeout.connect(self._update_foreground)
        self._timer.start(poll_interval_ms)

    def register_widget(self, widget: QWidget) -> None:
        hwnd = int(widget.winId())
        if hwnd not in self._tracked_hwnds:
            self._tracked_hwnds.append(hwnd)

    def unregister_widget(self, widget: QWidget) -> None:
        try:
            hwnd = int(widget.winId())
        except Exception:
            hwnd = 0
        if hwnd in self._tracked_hwnds:
            self._tracked_hwnds.remove(hwnd)

    def restore_focus(self) -> None:
        if not self._foreground_hwnd:
            return
        pid = wintypes.DWORD()
        target_thread = user32.GetWindowThreadProcessId(self._foreground_hwnd, byref(pid))
        current_thread = kernel32.GetCurrentThreadId()
        attached = False
        if target_thread and target_thread != current_thread:
            attached = bool(user32.AttachThreadInput(current_thread, target_thread, True))
        user32.SetForegroundWindow(self._foreground_hwnd)
        if attached:
            user32.AttachThreadInput(current_thread, target_thread, False)

    def _update_foreground(self) -> None:
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return
        if hwnd in self._tracked_hwnds:
            return
        if any(user32.IsChild(hwnd, tracked) for tracked in self._tracked_hwnds):
            return
        self._foreground_hwnd = hwnd
