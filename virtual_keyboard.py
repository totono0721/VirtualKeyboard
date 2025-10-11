"""Virtual keyboard overlay for Windows."""
from __future__ import annotations

import json
import os
import sys
import ctypes
from ctypes import wintypes
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from PyQt6.QtCore import QPoint, QRect, Qt, QTimer
from PyQt6.QtGui import QAction, QColor, QFont, QMouseEvent, QPainter, QPen
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QInputDialog,
    QMainWindow,
    QMenu,
    QMessageBox,
    QWidget,
)


if sys.platform != "win32":
    raise SystemExit("This application must be run on Windows.")


user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", wintypes.ULONG_PTR),
    ]


class INPUT(ctypes.Structure):
    class _INPUTUNION(ctypes.Union):
        _fields_ = [("ki", KEYBDINPUT)]

    _anonymous_ = ("_iu",)
    _fields_ = [("type", wintypes.DWORD), ("_iu", _INPUTUNION)]


# Ensure SendInput prototype is declared only once.
user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
user32.SendInput.restype = wintypes.UINT
user32.AttachThreadInput.argtypes = (wintypes.DWORD, wintypes.DWORD, wintypes.BOOL)
user32.AttachThreadInput.restype = wintypes.BOOL
user32.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
user32.GetWindowThreadProcessId.restype = wintypes.DWORD


@dataclass
class KeyDefinition:
    label: str
    sequence: str
    locked: bool = False
    position: QPoint = field(default_factory=lambda: QPoint(50, 50))

    def to_dict(self) -> Dict[str, object]:
        return {
            "label": self.label,
            "sequence": self.sequence,
            "locked": self.locked,
            "x": int(self.position.x()),
            "y": int(self.position.y()),
        }

    @staticmethod
    def from_dict(payload: Dict[str, object]) -> "KeyDefinition":
        point = QPoint(int(payload.get("x", 50)), int(payload.get("y", 50)))
        return KeyDefinition(
            label=str(payload.get("label", "?")),
            sequence=str(payload.get("sequence", "A")),
            locked=bool(payload.get("locked", False)),
            position=point,
        )


class KeySender:
    """Wraps Win32 SendInput for character and modifier combinations."""

    MODIFIERS: Dict[str, int] = {
        "SHIFT": 0x10,
        "CTRL": 0x11,
        "ALT": 0x12,
    }

    NAMED_KEYS: Dict[str, int] = {
        "ENTER": 0x0D,
        "ESC": 0x1B,
        "TAB": 0x09,
        "SPACE": 0x20,
        "BACKSPACE": 0x08,
        "UP": 0x26,
        "DOWN": 0x28,
        "LEFT": 0x25,
        "RIGHT": 0x27,
        "DELETE": 0x2E,
        "HOME": 0x24,
        "END": 0x23,
        "PAGEUP": 0x21,
        "PAGEDOWN": 0x22,
    }

    def __init__(self) -> None:
        self._cached_layout = user32.GetKeyboardLayout(0)

    def send_sequence(self, sequence: str) -> None:
        sequence = sequence.strip()
        if not sequence:
            return

        parts = [chunk.strip() for chunk in sequence.split("+") if chunk.strip()]
        if not parts:
            return

        modifiers: List[int] = []
        base_part = parts[-1]
        for part in parts[:-1]:
            vk = self._resolve_modifier(part)
            if vk:
                modifiers.append(vk)
            else:
                raise ValueError(f"Unknown modifier: {part}")

        base_vk, implicit_mods = self._resolve_key(base_part)
        for vk in implicit_mods:
            if vk not in modifiers:
                modifiers.append(vk)

        self._press_combination(modifiers, base_vk)

    def _press_combination(self, modifiers: Sequence[int], vk: int) -> None:
        inputs: List[INPUT] = []
        for mod in modifiers:
            inputs.append(self._create_input(mod, is_keyup=False))
        inputs.append(self._create_input(vk, is_keyup=False))
        inputs.append(self._create_input(vk, is_keyup=True))
        for mod in reversed(modifiers):
            inputs.append(self._create_input(mod, is_keyup=True))

        array_type = INPUT * len(inputs)
        sent = user32.SendInput(len(inputs), array_type(*inputs), ctypes.sizeof(INPUT))
        if sent != len(inputs):
            raise OSError("SendInput failed")

    def _create_input(self, vk: int, *, is_keyup: bool) -> INPUT:
        flags = 0x0002 if is_keyup else 0x0000
        keyboard_input = KEYBDINPUT(wVk=vk, wScan=0, dwFlags=flags, time=0, dwExtraInfo=0)
        input_union = INPUT._INPUTUNION()
        input_union.ki = keyboard_input
        return INPUT(type=1, _iu=input_union)

    def _resolve_modifier(self, token: str) -> Optional[int]:
        return self.MODIFIERS.get(token.upper())

    def _resolve_key(self, token: str) -> Tuple[int, List[int]]:
        token_upper = token.upper()
        if token_upper in self.NAMED_KEYS:
            return self.NAMED_KEYS[token_upper], []

        if len(token) == 1:
            vk_scan = user32.VkKeyScanExW(ord(token), self._cached_layout)
            if vk_scan == -1:
                raise ValueError(f"Unsupported key: {token}")
            vk = vk_scan & 0xFF
            required_mods: List[int] = []
            if vk_scan & 0x0100:
                required_mods.append(self.MODIFIERS["SHIFT"])
            if vk_scan & 0x0200:
                required_mods.append(self.MODIFIERS["CTRL"])
            if vk_scan & 0x0400:
                required_mods.append(self.MODIFIERS["ALT"])
            return vk, required_mods

        raise ValueError(f"Unsupported key token: {token}")


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
        target_thread = user32.GetWindowThreadProcessId(self._foreground_hwnd, ctypes.byref(pid))
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


class VirtualKeyWidget(QFrame):
    SIZE = 80
    BORDER_RADIUS = 8

    def __init__(self, definition: KeyDefinition, keyboard: "KeyboardWindow") -> None:
        super().__init__(keyboard.canvas)
        self.definition = definition
        self.keyboard = keyboard
        self.drag_active = False
        self.drag_offset = QPoint()
        self._border_color = QColor("#8f8f8f")
        self._font = QFont()
        self._font.setPointSize(16)
        self._font.setBold(True)
        self.setFixedSize(self.SIZE, self.SIZE)
        self.move(definition.position)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.update_style()
        keyboard.focus_keeper.register_widget(self)

    # region Styling & State
    def update_style(self) -> None:
        if self.definition.locked:
            color = "#3daee9"
        elif self.keyboard.edit_mode:
            color = "#ffaa00"
        else:
            color = "#8f8f8f"
        self._border_color = QColor(color)
        self.update()

    # endregion

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(1, 1, -1, -1)

        painter.setBrush(QColor(0, 0, 0, 160))
        painter.setPen(QPen(self._border_color, 2))
        painter.drawRoundedRect(rect, self.BORDER_RADIUS, self.BORDER_RADIUS)

        painter.setPen(QColor("white"))
        painter.setFont(self._font)
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.definition.label)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton and self.keyboard.edit_mode and not self.definition.locked:
            self.drag_active = True
            self.drag_offset = event.position().toPoint()
            event.accept()
            return
        if event.button() == Qt.MouseButton.LeftButton and not self.keyboard.edit_mode:
            self.keyboard.handle_key_trigger(self)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        if self.drag_active:
            delta = event.position().toPoint() - self.drag_offset
            new_pos = self.pos() + delta
            snapped = self.keyboard.snap_position(self, new_pos)
            self.move(snapped)
            self.definition.position = snapped
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton and self.drag_active:
            self.drag_active = False
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event) -> None:  # type: ignore[override]
        menu = QMenu(self)
        rename_action = menu.addAction("设置按键显示/输出…")
        lock_action_text = "取消锁定" if self.definition.locked else "锁定按键"
        lock_action = menu.addAction(lock_action_text)
        menu.addSeparator()
        delete_action = menu.addAction("删除")
        action = menu.exec(event.globalPos())
        if action == rename_action:
            self._prompt_for_label()
        elif action == lock_action:
            self.definition.locked = not self.definition.locked
            self.update_style()
        elif action == delete_action:
            self.keyboard.remove_key(self)

    def _prompt_for_label(self) -> None:
        label, ok = QInputDialog.getText(self, "设置按键", "显示文本:", text=self.definition.label)
        if ok and label:
            self.definition.label = label
            self.update()
        sequence, ok = QInputDialog.getText(
            self,
            "设置按键",
            "发送内容 (例如: A, ctrl+alt+L, Enter):",
            text=self.definition.sequence,
        )
        if ok and sequence:
            self.definition.sequence = sequence


class CanvasWidget(QWidget):
    def __init__(self, parent: "KeyboardWindow") -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(parent.show_background_menu)


class KeyboardWindow(QMainWindow):
    SNAP_DISTANCE = 15

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("虚拟按键面板")
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, False)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)

        self.canvas = CanvasWidget(self)
        self.setCentralWidget(self.canvas)

        self.key_sender = KeySender()
        self.focus_keeper = FocusKeeper(self)
        self.edit_mode = False
        self.toggle_edit_action: Optional[QAction] = None
        self.keys: List[VirtualKeyWidget] = []
        self.layout_path = os.path.join(os.path.dirname(__file__), "layout.json")

        self._setup_actions()
        self._load_layout()

    # region Actions & Menus
    def _setup_actions(self) -> None:
        menubar = self.menuBar()
        layout_menu = menubar.addMenu("布局")

        add_action = QAction("新增按键", self)
        add_action.setShortcut("Ctrl+N")
        add_action.triggered.connect(self.add_key)
        layout_menu.addAction(add_action)

        toggle_edit_action = QAction("切换编辑模式", self)
        toggle_edit_action.setShortcut("Ctrl+E")
        toggle_edit_action.setCheckable(True)
        toggle_edit_action.triggered.connect(self.toggle_edit_mode)
        layout_menu.addAction(toggle_edit_action)
        self.toggle_edit_action = toggle_edit_action

        save_action = QAction("保存布局", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self.save_layout)
        layout_menu.addAction(save_action)

        load_action = QAction("加载布局", self)
        load_action.setShortcut("Ctrl+O")
        load_action.triggered.connect(self.load_layout_from_dialog)
        layout_menu.addAction(load_action)

        layout_menu.addSeparator()
        exit_action = QAction("退出", self)
        exit_action.triggered.connect(self.close)
        layout_menu.addAction(exit_action)

        self.statusBar().showMessage("按 Ctrl+E 进入编辑模式，Ctrl+N 新建按键")

    def show_background_menu(self, pos: QPoint) -> None:
        global_pos = self.canvas.mapToGlobal(pos)
        menu = QMenu(self)
        add_action = menu.addAction("新增按键")
        toggle_action = menu.addAction("切换编辑模式")
        action = menu.exec(global_pos)
        if action == add_action:
            self.add_key()
        elif action == toggle_action:
            self.toggle_edit_mode(not self.edit_mode)

    # endregion

    def add_key(self) -> None:
        index = len(self.keys)
        position = QPoint(50 + (index % 5) * 90, 50 + (index // 5) * 90)
        definition = KeyDefinition(label="A", sequence="A", position=position)
        widget = VirtualKeyWidget(definition, self)
        widget.show()
        self.keys.append(widget)

    def remove_key(self, widget: VirtualKeyWidget) -> None:
        if widget in self.keys:
            self.keys.remove(widget)
            self.focus_keeper.unregister_widget(widget)
            widget.setParent(None)
            widget.deleteLater()

    def toggle_edit_mode(self, checked: Optional[bool] = None) -> None:
        if checked is None:
            self.edit_mode = not self.edit_mode
        else:
            self.edit_mode = checked
        if self.toggle_edit_action:
            self.toggle_edit_action.setChecked(self.edit_mode)
        mode_message = "编辑模式：拖动按键以重新排布" if self.edit_mode else "按键模式：点击发送"
        self.statusBar().showMessage(mode_message)
        for widget in self.keys:
            widget.update_style()

    def handle_key_trigger(self, widget: VirtualKeyWidget) -> None:
        try:
            self.focus_keeper.restore_focus()
            self.key_sender.send_sequence(widget.definition.sequence)
        except Exception as exc:  # pragma: no cover
            QMessageBox.critical(self, "发送失败", str(exc))

    # region Layout persistence
    def save_layout(self) -> None:
        payload = [widget.definition.to_dict() for widget in self.keys]
        try:
            with open(self.layout_path, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
            self.statusBar().showMessage(f"布局已保存: {self.layout_path}")
        except OSError as exc:
            QMessageBox.critical(self, "保存失败", str(exc))

    def load_layout_from_dialog(self) -> None:
        directory = os.path.dirname(self.layout_path)
        path, _ = QFileDialog.getOpenFileName(self, "选择布局文件", directory, "JSON (*.json)")
        if path:
            self.layout_path = path
            self._load_layout()

    def _load_layout(self) -> None:
        if not os.path.exists(self.layout_path):
            return
        try:
            with open(self.layout_path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            QMessageBox.warning(self, "加载失败", f"无法读取布局: {exc}")
            return

        for widget in list(self.keys):
            self.remove_key(widget)

        for item in payload:
            definition = KeyDefinition.from_dict(item)
            widget = VirtualKeyWidget(definition, self)
            widget.show()
            self.keys.append(widget)

    # endregion

    def snap_position(self, moving: VirtualKeyWidget, proposed: QPoint) -> QPoint:
        snapped = QPoint(proposed)
        moving_rect = QRect(snapped, moving.size())
        for widget in self.keys:
            if widget is moving:
                continue
            rect = widget.geometry()
            # Horizontal snapping
            if abs(moving_rect.left() - rect.right()) <= self.SNAP_DISTANCE:
                snapped.setX(rect.right())
            elif abs(moving_rect.right() - rect.left()) <= self.SNAP_DISTANCE:
                snapped.setX(rect.left() - moving_rect.width())
            elif abs(moving_rect.left() - rect.left()) <= self.SNAP_DISTANCE:
                snapped.setX(rect.left())
            elif abs(moving_rect.right() - rect.right()) <= self.SNAP_DISTANCE:
                snapped.setX(rect.right() - moving_rect.width())

            # Vertical snapping
            if abs(moving_rect.top() - rect.bottom()) <= self.SNAP_DISTANCE:
                snapped.setY(rect.bottom())
            elif abs(moving_rect.bottom() - rect.top()) <= self.SNAP_DISTANCE:
                snapped.setY(rect.top() - moving_rect.height())
            elif abs(moving_rect.top() - rect.top()) <= self.SNAP_DISTANCE:
                snapped.setY(rect.top())
            elif abs(moving_rect.bottom() - rect.bottom()) <= self.SNAP_DISTANCE:
                snapped.setY(rect.bottom() - moving_rect.height())

            moving_rect.moveTo(snapped)
        return snapped

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self.save_layout()
        super().closeEvent(event)


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


if __name__ == "__main__":
    raise SystemExit(main())
