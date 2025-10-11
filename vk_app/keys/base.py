"""Base virtual key widget implementation."""
from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtGui import QColor, QFont, QMouseEvent, QPainter, QPen
from PyQt6.QtWidgets import QInputDialog, QMenu, QWidget

from ..models import KeyDefinition

if TYPE_CHECKING:  # pragma: no cover - avoids circular import at runtime.
    from ..keyboard_window import KeyboardWindow


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
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self.keyboard.edit_mode
            and not self.definition.locked
        ):
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

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self.keyboard.focus_keeper.unregister_widget(self)
        super().closeEvent(event)

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
        if ok:
            self.definition.sequence = sequence
            self.keyboard.notify_key_changed(self)

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"VirtualKeyWindow(label={self.definition.label!r}, kind={self.definition.kind!r})"
