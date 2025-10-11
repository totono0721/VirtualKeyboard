"""Virtual keyboard overlay for Windows."""
from __future__ import annotations

import json
import os
import sys
import ctypes
from ctypes import wintypes
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from PyQt6.QtCore import QPoint, QPointF, QRect, Qt, QTimer
from PyQt6.QtGui import (
    QAction,
    QColor,
    QFont,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
)
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)


if sys.platform != "win32":
    raise SystemExit("This application must be run on Windows.")


user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

if not hasattr(wintypes, "ULONG_PTR"):
    wintypes.ULONG_PTR = ctypes.c_size_t

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
user32.GetForegroundWindow.restype = wintypes.HWND
user32.IsChild.argtypes = (wintypes.HWND, wintypes.HWND)
user32.IsChild.restype = wintypes.BOOL
user32.SetForegroundWindow.argtypes = (wintypes.HWND,)
user32.SetForegroundWindow.restype = wintypes.BOOL
user32.keybd_event.argtypes = (
    wintypes.BYTE,
    wintypes.BYTE,
    wintypes.DWORD,
    wintypes.ULONG_PTR,
)
user32.keybd_event.restype = None
kernel32.GetCurrentThreadId.restype = wintypes.DWORD


@dataclass
class KeyDefinition:
    label: str
    sequence: str
    locked: bool = False
    position: QPoint = field(default_factory=lambda: QPoint(50, 50))
    kind: str = "normal"
    config: Dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, object]:
        return {
            "label": self.label,
            "sequence": self.sequence,
            "locked": self.locked,
            "x": int(self.position.x()),
            "y": int(self.position.y()),
            "kind": self.kind,
            "config": self.config,
        }

    @staticmethod
    def from_dict(payload: Dict[str, object]) -> "KeyDefinition":
        point = QPoint(int(payload.get("x", 50)), int(payload.get("y", 50)))
        kind = str(payload.get("kind", "normal"))
        config_payload = payload.get("config", {})
        config = dict(config_payload) if isinstance(config_payload, dict) else {}
        return KeyDefinition(
            label=str(payload.get("label", "?")),
            sequence=str(payload.get("sequence", "A")),
            locked=bool(payload.get("locked", False)),
            position=point,
            kind=kind,
            config=config,
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

        vk, modifiers = self._parse_sequence(sequence)
        events: List[Tuple[int, bool]] = []
        for mod in modifiers:
            events.append((mod, False))
        events.append((vk, False))
        events.append((vk, True))
        for mod in reversed(modifiers):
            events.append((mod, True))
        self._send_events(events)

    def press_hold(self, sequence: str) -> Optional[Tuple[int, Tuple[int, ...]]]:
        sequence = sequence.strip()
        if not sequence:
            return None
        vk, modifiers = self._parse_sequence(sequence)
        events: List[Tuple[int, bool]] = []
        for mod in modifiers:
            events.append((mod, False))
        events.append((vk, False))
        self._send_events(events)
        return vk, tuple(modifiers)

    def release_hold(self, combination: Tuple[int, Tuple[int, ...]]) -> None:
        vk, modifiers = combination
        events: List[Tuple[int, bool]] = [(vk, True)]
        for mod in reversed(modifiers):
            events.append((mod, True))
        self._send_events(events)

    def _parse_sequence(self, sequence: str) -> Tuple[int, List[int]]:
        parts = [chunk.strip() for chunk in sequence.split("+") if chunk.strip()]
        if not parts:
            raise ValueError("Empty sequence")

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
        return base_vk, modifiers

    def _send_events(self, events: Sequence[Tuple[int, bool]]) -> None:
        if not events:
            return

        inputs = [self._create_input(vk, is_keyup) for vk, is_keyup in events]
        array_type = INPUT * len(inputs)
        input_array = array_type(*inputs)
        ctypes.set_last_error(0)
        sent = user32.SendInput(len(inputs), input_array, ctypes.sizeof(INPUT))
        if sent == len(inputs):
            return

        error_code = ctypes.get_last_error()
        if self._fallback_keybd_event(events):
            return

        if error_code:
            raise ctypes.WinError(error_code)
        raise OSError("SendInput failed without extended error information")

    def _create_input(self, vk: int, *, is_keyup: bool) -> INPUT:
        flags = 0x0002 if is_keyup else 0x0000
        keyboard_input = KEYBDINPUT(wVk=vk, wScan=0, dwFlags=flags, time=0, dwExtraInfo=0)
        input_union = INPUT._INPUTUNION()
        input_union.ki = keyboard_input
        return INPUT(type=1, _iu=input_union)

    def _resolve_modifier(self, token: str) -> Optional[int]:
        return self.MODIFIERS.get(token.upper())

    def _fallback_keybd_event(self, events: Sequence[Tuple[int, bool]]) -> bool:
        try:
            for vk, is_keyup in events:
                flag = 0x0002 if is_keyup else 0x0000
                user32.keybd_event(vk, 0, flag, 0)
            return True
        except Exception:
            return False

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


class VirtualKeyWindow(QWidget):
    SIZE = 80
    BORDER_RADIUS = 8

    def __init__(self, definition: KeyDefinition, keyboard: "KeyboardWindow") -> None:
        super().__init__(None)
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
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
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

    def on_activation(self) -> None:
        self.keyboard.handle_key_trigger(self)

    def on_edit_mode_changed(self) -> None:
        # Subclasses may override to react when edit mode toggles
        pass

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
            self.on_activation()
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
            self.keyboard.notify_key_changed(self)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton and self.drag_active:
            self.drag_active = False
            self.keyboard.notify_key_changed(self)
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
            self.keyboard.notify_key_changed(self)
        elif action == delete_action:
            self.keyboard.remove_key(self)

    def _prompt_for_label(self) -> None:
        label, ok = QInputDialog.getText(self, "设置按键", "显示文本:", text=self.definition.label)
        if ok and label:
            self.definition.label = label
            self.update()
            self.keyboard.notify_key_changed(self)
        sequence, ok = QInputDialog.getText(
            self,
            "设置按键",
            "发送内容 (例如: A, ctrl+alt+L, Enter):",
            text=self.definition.sequence,
        )
        if ok and sequence:
            self.definition.sequence = sequence
            self.keyboard.notify_key_changed(self)


class HoverHoldKeyWindow(VirtualKeyWindow):
    HOVER_REGIONS = ("up", "right", "down", "left", "center")

    def __init__(self, definition: KeyDefinition, keyboard: "KeyboardWindow") -> None:
        super().__init__(definition, keyboard)
        self.setFixedSize(self.SIZE * 2, self.SIZE * 2)
        self.setMouseTracking(True)
        self.definition.kind = "hover_hold"
        config = dict(self.definition.config)
        config.setdefault("up", "W")
        config.setdefault("down", "S")
        config.setdefault("left", "A")
        config.setdefault("right", "D")
        config.setdefault("center_label", self.definition.label)
        self.definition.config = config
        self._active_region: Optional[str] = None
        self._active_combo: Optional[Tuple[int, Tuple[int, ...]]] = None
        self._paths = self._build_paths()

    def _build_paths(self) -> Dict[str, QPainterPath]:
        width = float(self.width())
        height = float(self.height())
        inset = self.SIZE / 2
        center_rect = QRect(int(inset), int(inset), int(width - inset * 2), int(height - inset * 2))
        left = float(center_rect.left())
        top = float(center_rect.top())
        right = left + float(center_rect.width())
        bottom = top + float(center_rect.height())

        def polygon(points: Sequence[Tuple[float, float]]) -> QPainterPath:
            path = QPainterPath()
            if not points:
                return path
            first = points[0]
            path.moveTo(first[0], first[1])
            for x, y in points[1:]:
                path.lineTo(x, y)
            path.closeSubpath()
            return path

        paths: Dict[str, QPainterPath] = {}
        paths["center"] = polygon(
            [
                (left, top),
                (right, top),
                (right, bottom),
                (left, bottom),
            ]
        )
        paths["up"] = polygon(
            [
                (0.0, 0.0),
                (width, 0.0),
                (right, top),
                (left, top),
            ]
        )
        paths["down"] = polygon(
            [
                (left, bottom),
                (right, bottom),
                (width, height),
                (0.0, height),
            ]
        )
        paths["left"] = polygon(
            [
                (0.0, 0.0),
                (left, top),
                (left, bottom),
                (0.0, height),
            ]
        )
        paths["right"] = polygon(
            [
                (right, top),
                (width, 0.0),
                (width, height),
                (right, bottom),
            ]
        )
        return paths

    def on_activation(self) -> None:
        # Hover-based key does not trigger on click.
        pass

    def on_edit_mode_changed(self) -> None:
        self._release_active_combination()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(self._border_color, 2))

        colors = {
            "up": QColor("#2c7fb8"),
            "down": QColor("#41ab5d"),
            "left": QColor("#f03b20"),
            "right": QColor("#9e9ac8"),
            "center": QColor(0, 0, 0, 180),
        }

        highlight = QColor("#ffaa00")
        for region, path in self._paths.items():
            fill_color = colors.get(region, QColor("#5f5f5f"))
            if region == self._active_region:
                fill_color = highlight
            painter.setBrush(fill_color)
            painter.drawPath(path)

        painter.setPen(QColor("white"))
        font = QFont(self._font)
        font.setPointSize(18)
        painter.setFont(font)
        center_label = str(self.definition.config.get("center_label", self.definition.label))
        painter.drawText(self._paths["center"].boundingRect(), Qt.AlignmentFlag.AlignCenter, center_label)

        direction_labels = {
            "up": "↑",
            "down": "↓",
            "left": "←",
            "right": "→",
        }
        for region, label in direction_labels.items():
            if region not in self._paths:
                continue
            painter.drawText(
                self._paths[region].boundingRect(),
                Qt.AlignmentFlag.AlignCenter,
                label,
            )

    def mousePressEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton and self.keyboard.edit_mode and not self.definition.locked:
            self.drag_active = True
            self.drag_offset = event.position().toPoint()
            event.accept()
            return
        if event.button() == Qt.MouseButton.LeftButton and not self.keyboard.edit_mode:
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        super().mouseMoveEvent(event)
        if self.keyboard.edit_mode:
            self._set_active_region(None)
            return
        region = self._resolve_region(event.position())
        self._set_active_region(region)

    def contextMenuEvent(self, event) -> None:  # type: ignore[override]
        menu = QMenu(self)
        edit_action = menu.addAction("在配置窗口中编辑…")
        lock_text = "取消锁定" if self.definition.locked else "锁定按键"
        lock_action = menu.addAction(lock_text)
        menu.addSeparator()
        delete_action = menu.addAction("删除")
        action = menu.exec(event.globalPos())
        if action == edit_action and self.keyboard.config_panel:
            self.keyboard.config_panel.focus_on_widget(self)
        elif action == lock_action:
            self.definition.locked = not self.definition.locked
            self.update_style()
            self.keyboard.notify_key_changed(self)
        elif action == delete_action:
            self.keyboard.remove_key(self)

    def enterEvent(self, event) -> None:  # type: ignore[override]
        if not self.keyboard.edit_mode:
            region = self._resolve_region(event.position())
            self._set_active_region(region)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # type: ignore[override]
        self._set_active_region(None)
        super().leaveEvent(event)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self._release_active_combination()
        super().closeEvent(event)

    def _resolve_region(self, position: QPointF) -> Optional[str]:
        for region, path in self._paths.items():
            if path.contains(position):
                return region
        return None

    def _set_active_region(self, region: Optional[str]) -> None:
        if region == self._active_region:
            return
        self._release_active_combination()
        if region in {"up", "down", "left", "right"}:
            sequence = str(self.definition.config.get(region, "")).strip()
            if sequence:
                try:
                    combo = self.keyboard.key_sender.press_hold(sequence)
                except Exception:
                    combo = None
                if combo:
                    self._active_combo = combo
                    self._active_region = region
        else:
            self._active_region = region
        self.update()

    def _release_active_combination(self) -> None:
        if self._active_combo:
            try:
                self.keyboard.key_sender.release_hold(self._active_combo)
            finally:
                self._active_combo = None
        self._active_region = None
        self.update()

class KeyboardWindow(QMainWindow):
    SNAP_DISTANCE = 15

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("虚拟按键面板")
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, False)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.key_sender = KeySender()
        self.focus_keeper = FocusKeeper(self)
        self.edit_mode = False
        self.toggle_edit_action: Optional[QAction] = None
        self.keys: List[VirtualKeyWindow] = []
        self.layout_path = os.path.join(os.path.dirname(__file__), "layout.json")
        self.config_panel: Optional["ConfigurationPanel"] = None

        self._setup_actions()
        self.config_panel = ConfigurationPanel(self)
        self.setCentralWidget(self.config_panel)
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

    # endregion

    def add_key(self) -> None:
        index = len(self.keys)
        position = QPoint(50 + (index % 5) * 90, 50 + (index // 5) * 90)
        definition = KeyDefinition(label="A", sequence="A", position=position)
        self._create_key_widget(definition)

    def add_toggle_key(self) -> None:
        position = QPoint(50, 50)
        definition = KeyDefinition(
            label="配置", sequence="", position=position, kind="toggle_config"
        )
        self._create_key_widget(definition)

    def add_hover_hold_key(self) -> None:
        position = QPoint(50, 50)
        definition = KeyDefinition(
            label="方向控制",
            sequence="",
            position=position,
            kind="hover_hold",
            config={
                "up": "W",
                "down": "S",
                "left": "A",
                "right": "D",
                "center_label": "移动",
            },
        )
        self._create_key_widget(definition)

    def remove_key(self, widget: VirtualKeyWindow) -> None:
        if widget in self.keys:
            self.keys.remove(widget)
            self.focus_keeper.unregister_widget(widget)
            widget.close()
            widget.deleteLater()
            if self.config_panel:
                self.config_panel.refresh_keys()

    def toggle_edit_mode(self, checked: Optional[bool] = None) -> None:
        if checked is None:
            self.edit_mode = not self.edit_mode
        else:
            self.edit_mode = checked
        if self.toggle_edit_action:
            self.toggle_edit_action.setChecked(self.edit_mode)
        if self.config_panel:
            self.config_panel.update_edit_mode(self.edit_mode)
        mode_message = "编辑模式：拖动按键以重新排布" if self.edit_mode else "按键模式：点击发送"
        self.statusBar().showMessage(mode_message)
        for widget in self.keys:
            widget.update_style()
            widget.on_edit_mode_changed()

    def handle_key_trigger(self, widget: VirtualKeyWindow) -> None:
        if widget.definition.kind == "toggle_config":
            self.toggle_configuration_visibility()
            return
        try:
            self.focus_keeper.restore_focus()
            self.key_sender.send_sequence(widget.definition.sequence)
        except OSError as exc:  # pragma: no cover
            if getattr(exc, "winerror", None) == 5:
                message = "权限不足：请以管理员身份运行或确保目标窗口未提升权限。"
            else:
                message = str(exc)
            QMessageBox.critical(self, "发送失败", message)

    def toggle_configuration_visibility(self) -> None:
        if self.isVisible():
            self.hide()
        else:
            self.show()
            self.raise_()
            self.activateWindow()

    def notify_key_changed(self, widget: VirtualKeyWindow) -> None:
        if self.config_panel:
            self.config_panel.update_widget(widget)

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
            self._create_key_widget(definition, refresh=False)
        if self.config_panel:
            self.config_panel.refresh_keys()

    # endregion

    def snap_position(self, moving: VirtualKeyWindow, proposed: QPoint) -> QPoint:
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
        for widget in list(self.keys):
            self.focus_keeper.unregister_widget(widget)
            widget.close()
        self.keys.clear()
        super().closeEvent(event)

    def _create_key_widget(
        self, definition: KeyDefinition, *, refresh: bool = True
    ) -> VirtualKeyWindow:
        kind = definition.kind or "normal"
        if kind == "hover_hold":
            widget = HoverHoldKeyWindow(definition, self)
        else:
            widget = VirtualKeyWindow(definition, self)
        widget.move(definition.position)
        widget.show()
        widget.raise_()
        self.keys.append(widget)
        if refresh and self.config_panel:
            self.config_panel.refresh_keys(select=widget)
        return widget


class ConfigurationPanel(QWidget):
    EMPTY_INDEX = 0
    NORMAL_INDEX = 1
    TOGGLE_INDEX = 2
    HOVER_INDEX = 3

    def __init__(self, keyboard: KeyboardWindow) -> None:
        super().__init__(keyboard)
        self.keyboard = keyboard
        self.selected_widget: Optional[VirtualKeyWindow] = None
        self._loading = False

        layout = QVBoxLayout(self)

        operations_layout = QHBoxLayout()
        self.add_button = QPushButton("新增按键 (Ctrl+N)")
        self.add_button.clicked.connect(self.keyboard.add_key)
        operations_layout.addWidget(self.add_button)

        self.toggle_edit_button = QPushButton("切换编辑模式 (Ctrl+E)")
        self.toggle_edit_button.setCheckable(True)
        self.toggle_edit_button.clicked.connect(self.keyboard.toggle_edit_mode)
        operations_layout.addWidget(self.toggle_edit_button)

        self.save_button = QPushButton("保存布局 (Ctrl+S)")
        self.save_button.clicked.connect(self.keyboard.save_layout)
        operations_layout.addWidget(self.save_button)

        self.load_button = QPushButton("加载布局 (Ctrl+O)")
        self.load_button.clicked.connect(self.keyboard.load_layout_from_dialog)
        operations_layout.addWidget(self.load_button)

        operations_layout.addStretch(1)
        layout.addLayout(operations_layout)

        special_layout = QHBoxLayout()
        self.add_toggle_button = QPushButton("添加配置切换按键")
        self.add_toggle_button.clicked.connect(self.keyboard.add_toggle_key)
        special_layout.addWidget(self.add_toggle_button)

        self.add_hover_button = QPushButton("添加悬停长按按键")
        self.add_hover_button.clicked.connect(self.keyboard.add_hover_hold_key)
        special_layout.addWidget(self.add_hover_button)

        special_layout.addStretch(1)
        layout.addLayout(special_layout)

        self.list_widget = QListWidget()
        self.list_widget.currentItemChanged.connect(self._on_current_item_changed)
        layout.addWidget(self.list_widget, stretch=1)

        self.detail_group = QGroupBox("按键配置")
        detail_layout = QVBoxLayout()
        self.form_stack = QStackedWidget()

        self.empty_page = QWidget()
        self.form_stack.addWidget(self.empty_page)

        self.normal_page = QWidget()
        normal_form = QFormLayout(self.normal_page)
        self.normal_label_edit = QLineEdit()
        self.normal_label_edit.textChanged.connect(self._on_normal_label_changed)
        normal_form.addRow("显示文本", self.normal_label_edit)
        self.normal_sequence_edit = QLineEdit()
        self.normal_sequence_edit.textChanged.connect(self._on_normal_sequence_changed)
        normal_form.addRow("输出内容", self.normal_sequence_edit)
        self.normal_x_spin = self._create_spin_box()
        self.normal_x_spin.valueChanged.connect(self._on_normal_position_changed)
        normal_form.addRow("X 坐标", self.normal_x_spin)
        self.normal_y_spin = self._create_spin_box()
        self.normal_y_spin.valueChanged.connect(self._on_normal_position_changed)
        normal_form.addRow("Y 坐标", self.normal_y_spin)
        self.normal_locked = QCheckBox("锁定该按键")
        self.normal_locked.toggled.connect(self._on_normal_locked_changed)
        normal_form.addRow("锁定", self.normal_locked)
        self.form_stack.addWidget(self.normal_page)

        self.toggle_page = QWidget()
        toggle_form = QFormLayout(self.toggle_page)
        self.toggle_label_edit = QLineEdit()
        self.toggle_label_edit.textChanged.connect(self._on_toggle_label_changed)
        toggle_form.addRow("显示文本", self.toggle_label_edit)
        self.toggle_x_spin = self._create_spin_box()
        self.toggle_x_spin.valueChanged.connect(self._on_toggle_position_changed)
        toggle_form.addRow("X 坐标", self.toggle_x_spin)
        self.toggle_y_spin = self._create_spin_box()
        self.toggle_y_spin.valueChanged.connect(self._on_toggle_position_changed)
        toggle_form.addRow("Y 坐标", self.toggle_y_spin)
        self.toggle_locked = QCheckBox("锁定该按键")
        self.toggle_locked.toggled.connect(self._on_toggle_locked_changed)
        toggle_form.addRow("锁定", self.toggle_locked)
        self.form_stack.addWidget(self.toggle_page)

        self.hover_page = QWidget()
        hover_form = QFormLayout(self.hover_page)
        self.hover_name_edit = QLineEdit()
        self.hover_name_edit.textChanged.connect(self._on_hover_name_changed)
        hover_form.addRow("名称", self.hover_name_edit)
        self.hover_center_label_edit = QLineEdit()
        self.hover_center_label_edit.textChanged.connect(self._on_hover_center_label_changed)
        hover_form.addRow("中心显示文本", self.hover_center_label_edit)
        self.hover_up_edit = QLineEdit()
        self.hover_up_edit.textChanged.connect(lambda text: self._on_hover_sequence_changed("up", text))
        hover_form.addRow("上方输出", self.hover_up_edit)
        self.hover_down_edit = QLineEdit()
        self.hover_down_edit.textChanged.connect(lambda text: self._on_hover_sequence_changed("down", text))
        hover_form.addRow("下方输出", self.hover_down_edit)
        self.hover_left_edit = QLineEdit()
        self.hover_left_edit.textChanged.connect(lambda text: self._on_hover_sequence_changed("left", text))
        hover_form.addRow("左侧输出", self.hover_left_edit)
        self.hover_right_edit = QLineEdit()
        self.hover_right_edit.textChanged.connect(lambda text: self._on_hover_sequence_changed("right", text))
        hover_form.addRow("右侧输出", self.hover_right_edit)
        self.hover_x_spin = self._create_spin_box()
        self.hover_x_spin.valueChanged.connect(self._on_hover_position_changed)
        hover_form.addRow("X 坐标", self.hover_x_spin)
        self.hover_y_spin = self._create_spin_box()
        self.hover_y_spin.valueChanged.connect(self._on_hover_position_changed)
        hover_form.addRow("Y 坐标", self.hover_y_spin)
        self.hover_locked = QCheckBox("锁定该按键")
        self.hover_locked.toggled.connect(self._on_hover_locked_changed)
        hover_form.addRow("锁定", self.hover_locked)
        self.form_stack.addWidget(self.hover_page)

        detail_layout.addWidget(self.form_stack)
        self.detail_group.setLayout(detail_layout)
        layout.addWidget(self.detail_group)

        self.refresh_keys()
        self.update_edit_mode(self.keyboard.edit_mode)
        self._show_empty_form()

    def _create_spin_box(self) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(-10000, 10000)
        spin.setSingleStep(5)
        return spin

    def refresh_keys(self, select: Optional[VirtualKeyWindow] = None) -> None:
        target = select or self.selected_widget
        self._loading = True
        self.list_widget.blockSignals(True)
        self.list_widget.clear()
        matched_item = None
        for widget in self.keyboard.keys:
            item_text = self._describe_widget(widget)
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, widget)
            self.list_widget.addItem(item)
            if widget is target:
                matched_item = item
        if matched_item:
            matched_item.setSelected(True)
            self.list_widget.setCurrentItem(matched_item)
        else:
            self.list_widget.setCurrentRow(-1)
        self.list_widget.blockSignals(False)
        self._loading = False
        self._on_current_item_changed(self.list_widget.currentItem(), None)

    def update_widget(self, widget: VirtualKeyWindow) -> None:
        self._loading = True
        for index in range(self.list_widget.count()):
            item = self.list_widget.item(index)
            if item.data(Qt.ItemDataRole.UserRole) is widget:
                item.setText(self._describe_widget(widget))
                break
        self._loading = False
        if widget is self.selected_widget:
            self._load_widget(widget)

    def update_edit_mode(self, edit_mode: bool) -> None:
        self.toggle_edit_button.blockSignals(True)
        self.toggle_edit_button.setChecked(edit_mode)
        self.toggle_edit_button.blockSignals(False)

    def focus_on_widget(self, widget: VirtualKeyWindow) -> None:
        self.refresh_keys(select=widget)
        self.list_widget.setFocus()

    def _show_empty_form(self) -> None:
        self.form_stack.setCurrentIndex(self.EMPTY_INDEX)
        self.detail_group.setTitle("按键配置")

    def _on_current_item_changed(self, current, previous) -> None:
        if self._loading:
            return
        widget = None
        if current:
            widget = current.data(Qt.ItemDataRole.UserRole)
        self.selected_widget = widget
        if widget:
            self._load_widget(widget)
        else:
            self._show_empty_form()

    def _load_widget(self, widget: VirtualKeyWindow) -> None:
        self._loading = True
        kind = widget.definition.kind or "normal"
        self.detail_group.setTitle(f"按键配置 - {self._kind_display(kind)}")
        position = widget.definition.position
        if kind == "hover_hold":
            self.form_stack.setCurrentIndex(self.HOVER_INDEX)
            self.hover_name_edit.setText(widget.definition.label)
            center_label = str(widget.definition.config.get("center_label", widget.definition.label))
            self.hover_center_label_edit.setText(center_label)
            self.hover_up_edit.setText(str(widget.definition.config.get("up", "")))
            self.hover_down_edit.setText(str(widget.definition.config.get("down", "")))
            self.hover_left_edit.setText(str(widget.definition.config.get("left", "")))
            self.hover_right_edit.setText(str(widget.definition.config.get("right", "")))
            self.hover_x_spin.setValue(int(position.x()))
            self.hover_y_spin.setValue(int(position.y()))
            self.hover_locked.setChecked(widget.definition.locked)
        elif kind == "toggle_config":
            self.form_stack.setCurrentIndex(self.TOGGLE_INDEX)
            self.toggle_label_edit.setText(widget.definition.label)
            self.toggle_x_spin.setValue(int(position.x()))
            self.toggle_y_spin.setValue(int(position.y()))
            self.toggle_locked.setChecked(widget.definition.locked)
        else:
            self.form_stack.setCurrentIndex(self.NORMAL_INDEX)
            self.normal_label_edit.setText(widget.definition.label)
            self.normal_sequence_edit.setText(widget.definition.sequence)
            self.normal_x_spin.setValue(int(position.x()))
            self.normal_y_spin.setValue(int(position.y()))
            self.normal_locked.setChecked(widget.definition.locked)
        self._loading = False

    def _describe_widget(self, widget: VirtualKeyWindow) -> str:
        kind = widget.definition.kind or "normal"
        label = widget.definition.label or "(未命名)"
        return f"{label} - {self._kind_display(kind)}"

    def _kind_display(self, kind: str) -> str:
        mapping = {
            "normal": "普通按键",
            "toggle_config": "配置窗口切换",
            "hover_hold": "悬停长按",
        }
        return mapping.get(kind, kind)

    def _on_normal_label_changed(self, text: str) -> None:
        if self._loading or not self.selected_widget:
            return
        self.selected_widget.definition.label = text
        self.selected_widget.update()
        self.keyboard.notify_key_changed(self.selected_widget)

    def _on_normal_sequence_changed(self, text: str) -> None:
        if self._loading or not self.selected_widget:
            return
        self.selected_widget.definition.sequence = text
        self.keyboard.notify_key_changed(self.selected_widget)

    def _on_normal_position_changed(self, value: int) -> None:
        if self._loading or not self.selected_widget:
            return
        point = QPoint(self.normal_x_spin.value(), self.normal_y_spin.value())
        self._apply_position(point)

    def _on_normal_locked_changed(self, checked: bool) -> None:
        if self._loading or not self.selected_widget:
            return
        self.selected_widget.definition.locked = checked
        self.selected_widget.update_style()
        self.keyboard.notify_key_changed(self.selected_widget)

    def _on_toggle_label_changed(self, text: str) -> None:
        if self._loading or not self.selected_widget:
            return
        self.selected_widget.definition.label = text
        self.selected_widget.update()
        self.keyboard.notify_key_changed(self.selected_widget)

    def _on_toggle_position_changed(self, value: int) -> None:
        if self._loading or not self.selected_widget:
            return
        point = QPoint(self.toggle_x_spin.value(), self.toggle_y_spin.value())
        self._apply_position(point)

    def _on_toggle_locked_changed(self, checked: bool) -> None:
        if self._loading or not self.selected_widget:
            return
        self.selected_widget.definition.locked = checked
        self.selected_widget.update_style()
        self.keyboard.notify_key_changed(self.selected_widget)

    def _on_hover_name_changed(self, text: str) -> None:
        if self._loading or not self.selected_widget:
            return
        self.selected_widget.definition.label = text
        self.selected_widget.update()
        self.keyboard.notify_key_changed(self.selected_widget)

    def _on_hover_center_label_changed(self, text: str) -> None:
        if self._loading or not self.selected_widget:
            return
        self.selected_widget.definition.config["center_label"] = text
        self.selected_widget.update()
        self.keyboard.notify_key_changed(self.selected_widget)

    def _on_hover_sequence_changed(self, direction: str, text: str) -> None:
        if self._loading or not self.selected_widget:
            return
        self.selected_widget.definition.config[direction] = text
        self.keyboard.notify_key_changed(self.selected_widget)

    def _on_hover_position_changed(self, value: int) -> None:
        if self._loading or not self.selected_widget:
            return
        point = QPoint(self.hover_x_spin.value(), self.hover_y_spin.value())
        self._apply_position(point)

    def _on_hover_locked_changed(self, checked: bool) -> None:
        if self._loading or not self.selected_widget:
            return
        self.selected_widget.definition.locked = checked
        self.selected_widget.update_style()
        self.keyboard.notify_key_changed(self.selected_widget)

    def _apply_position(self, point: QPoint) -> None:
        if not self.selected_widget:
            return
        sanitized = QPoint(int(point.x()), int(point.y()))
        self.selected_widget.definition.position = sanitized
        self.selected_widget.move(sanitized)
        self.keyboard.notify_key_changed(self.selected_widget)


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
