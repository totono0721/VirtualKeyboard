"""Base virtual key widget implementation."""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from PyQt6.QtCore import QPoint, Qt, QTimer
from PyQt6.QtGui import QColor, QFont, QMouseEvent, QPainter, QPen
from PyQt6.QtWidgets import QInputDialog, QMenu, QWidget

from ..models import KeyDefinition

if TYPE_CHECKING:  # pragma: no cover - avoids circular import at runtime.
    from ..keyboard_window import KeyboardWindow


class VirtualKeyWindow(QWidget):
    SIZE = 80
    BORDER_RADIUS = 8
    ACTIVATION_CLICK_ONCE = "click_once"
    ACTIVATION_CLICK_HOLD = "click_hold"
    ACTIVATION_HOVER_HOLD = "hover_hold"
    ACTIVATION_HOVER_ONCE = "hover_once"

    HOLD_BEHAVIOR_TRUE = "true_hold"
    HOLD_BEHAVIOR_REPEAT = "repeat"

    DEFAULT_REPEAT_INTERVAL_MS = 180
    DEFAULT_AUTO_FADE_DELAY_MS = 4000
    FADE_STEP = 0.08
    FADE_INTERVAL_MS = 60
    FADE_MIN_OPACITY = 0.12

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
        self._hold_sequence: Optional[str] = None
        self._hold_combo: Optional[tuple[int, tuple[int, ...]]] = None
        self._repeat_timer = QTimer(self)
        self._repeat_timer.setSingleShot(False)
        self._repeat_timer.timeout.connect(self._handle_repeat_timeout)
        self._flash_timer = QTimer(self)
        self._flash_timer.setSingleShot(True)
        self._flash_timer.timeout.connect(self._clear_flash_if_idle)
        self._idle_timer = QTimer(self)
        self._idle_timer.setSingleShot(True)
        self._idle_timer.timeout.connect(self._begin_auto_fade)
        self._fade_timer = QTimer(self)
        self._fade_timer.setInterval(self.FADE_INTERVAL_MS)
        self._fade_timer.setSingleShot(False)
        self._fade_timer.timeout.connect(self._advance_fade)
        self._active_visual = False
        self._hover_triggered = False
        self._toggle_hold_active = False
        self._configuration_visible = True
        self._fade_target = 1.0
        self.update_style()
        self._ensure_activation_defaults()
        self._apply_activation_config()
        self._apply_visibility_config()
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
        self._stop_hold_sequence()

    def on_definition_changed(self) -> None:
        self._ensure_activation_defaults()
        self._apply_activation_config()
        self._apply_visibility_config()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(1, 1, -1, -1)

        fill = QColor(0, 0, 0, 210 if self._active_visual else 160)
        border = QColor(self._border_color)
        if self._active_visual:
            border = border.lighter(140)
        painter.setBrush(fill)
        painter.setPen(QPen(border, 3 if self._active_visual else 2))
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
            self._register_activity()
            mode = self._activation_mode()
            if mode in {self.ACTIVATION_CLICK_ONCE, self.ACTIVATION_HOVER_ONCE}:
                self._trigger_default_once()
            elif mode in {self.ACTIVATION_CLICK_HOLD, self.ACTIVATION_HOVER_HOLD}:
                self._begin_default_hold()
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
        if (
            event.button() == Qt.MouseButton.LeftButton
            and not self.keyboard.edit_mode
            and self._activation_mode() in {self.ACTIVATION_CLICK_HOLD, self.ACTIVATION_HOVER_HOLD}
        ):
            self._stop_hold_sequence()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def enterEvent(self, event) -> None:  # type: ignore[override]
        if not self.keyboard.edit_mode:
            self._register_activity()
            self._handle_hover_enter()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # type: ignore[override]
        self._handle_hover_leave()
        super().leaveEvent(event)

    def contextMenuEvent(self, event) -> None:  # type: ignore[override]
        menu = QMenu(self)
        rename_action = menu.addAction("设置按键显示/输出…")
        lock_action_text = "允许拖动" if self.definition.locked else "禁止拖动"
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
        self._stop_hold_sequence()
        self._idle_timer.stop()
        self._fade_timer.stop()
        self.keyboard.focus_keeper.unregister_widget(self)
        super().closeEvent(event)

    # region Activation configuration & helpers
    def _activation_mode(self) -> str:
        value = str(self.definition.config.get("activation_mode", self.ACTIVATION_CLICK_ONCE))
        if value not in {
            self.ACTIVATION_CLICK_ONCE,
            self.ACTIVATION_CLICK_HOLD,
            self.ACTIVATION_HOVER_HOLD,
            self.ACTIVATION_HOVER_ONCE,
        }:
            value = self.ACTIVATION_CLICK_ONCE
        return value

    def _hold_behavior(self) -> str:
        value = str(self.definition.config.get("hold_behavior", self.HOLD_BEHAVIOR_TRUE))
        if value not in {self.HOLD_BEHAVIOR_TRUE, self.HOLD_BEHAVIOR_REPEAT}:
            value = self.HOLD_BEHAVIOR_TRUE
        return value

    def _repeat_interval_ms(self) -> int:
        raw_value = self.definition.config.get("repeat_interval_ms", self.DEFAULT_REPEAT_INTERVAL_MS)
        try:
            interval = int(raw_value)
        except (TypeError, ValueError):
            interval = self.DEFAULT_REPEAT_INTERVAL_MS
        return max(10, interval)

    def _apply_activation_config(self) -> None:
        mode = self._activation_mode()
        requires_tracking = mode in {self.ACTIVATION_HOVER_HOLD, self.ACTIVATION_HOVER_ONCE}
        self.setMouseTracking(requires_tracking)
        if mode != self.ACTIVATION_HOVER_ONCE:
            self._hover_triggered = False
        if mode not in {self.ACTIVATION_CLICK_HOLD, self.ACTIVATION_HOVER_HOLD}:
            self._stop_hold_sequence()
        self._apply_visibility_config()

    def _handle_hover_enter(self) -> None:
        mode = self._activation_mode()
        if mode == self.ACTIVATION_HOVER_ONCE:
            if not self._hover_triggered:
                self._hover_triggered = True
                self._trigger_default_once()
        elif mode == self.ACTIVATION_HOVER_HOLD:
            if not self._hold_sequence and not self._toggle_hold_active:
                self._hover_triggered = True
                self._begin_default_hold()
        if not self.keyboard.edit_mode:
            self._register_activity()

    def _handle_hover_leave(self) -> None:
        mode = self._activation_mode()
        if mode == self.ACTIVATION_HOVER_ONCE:
            self._hover_triggered = False
        elif mode == self.ACTIVATION_HOVER_HOLD:
            self._hover_triggered = False
            self._stop_hold_sequence()
        if not self.keyboard.edit_mode:
            self._schedule_idle_check()

    def _trigger_default_once(self) -> None:
        if self.definition.kind == "toggle_config":
            self.keyboard.toggle_configuration_visibility()
            self._flash_activation_feedback()
            return
        self._trigger_sequence_once(self.definition.sequence)

    def _begin_default_hold(self) -> None:
        if self.definition.kind == "toggle_config":
            self._toggle_hold_active = True
            self._flash_timer.stop()
            self._active_visual = True
            self.update()
            self._trigger_default_once()
            if self._hold_behavior() == self.HOLD_BEHAVIOR_REPEAT:
                interval = self._repeat_interval_ms()
                if interval > 0:
                    self._repeat_timer.start(interval)
            return
        self._toggle_hold_active = False
        self._start_hold_sequence(self.definition.sequence)

    def _trigger_sequence_once(self, sequence: str) -> None:
        if self._send_sequence_once(sequence):
            self._flash_activation_feedback()
            self._register_activity()

    def _send_sequence_once(self, sequence: str) -> bool:
        text = sequence.strip()
        if not text:
            return False
        self.keyboard.send_sequence_once(text)
        return True

    def _start_hold_sequence(self, sequence: str) -> None:
        text = sequence.strip()
        if not text:
            return
        self._stop_hold_sequence()
        if self._hold_behavior() == self.HOLD_BEHAVIOR_REPEAT:
            if self._send_sequence_once(text):
                self._hold_sequence = text
                interval = self._repeat_interval_ms()
                if interval > 0:
                    self._repeat_timer.start(interval)
                self._active_visual = True
                self.update()
        else:
            combo = self.keyboard.start_sequence_hold(text)
            if combo:
                self._hold_sequence = text
                self._hold_combo = combo
                self._active_visual = True
                self.update()
        if self._hold_sequence:
            self._register_activity()

    def _stop_hold_sequence(self) -> None:
        if self._repeat_timer.isActive():
            self._repeat_timer.stop()
        if self._hold_combo:
            self.keyboard.stop_sequence_hold(self._hold_combo)
        self._hold_combo = None
        self._hold_sequence = None
        if self._toggle_hold_active:
            self._toggle_hold_active = False
        self._flash_timer.stop()
        self._active_visual = False
        self.update()
        self._schedule_idle_check()

    def _handle_repeat_timeout(self) -> None:
        if self._toggle_hold_active and self.definition.kind == "toggle_config":
            self.keyboard.toggle_configuration_visibility()
            return
        if self._hold_sequence:
            if self._send_sequence_once(self._hold_sequence):
                self._register_activity()

    def _flash_activation_feedback(self, region: Optional[str] = None) -> None:
        if self._hold_sequence or self._toggle_hold_active:
            return
        self._active_visual = True
        self.update()
        self._flash_timer.start(160)
        self._register_activity()

    def _clear_flash_if_idle(self) -> None:
        if self._hold_sequence or self._toggle_hold_active:
            return
        self._active_visual = False
        self.update()
        self._schedule_idle_check()

    def on_configuration_visibility_changed(self, visible: bool) -> None:
        self._configuration_visible = visible
        if visible:
            self._fade_timer.stop()
            self._idle_timer.stop()
            if not self._manual_hidden():
                self._fade_target = 1.0
                self._set_opacity(1.0)
        else:
            self._schedule_idle_check()

    def set_manual_hidden(self, hidden: bool) -> None:
        self.definition.config["hidden"] = bool(hidden)
        self._apply_visibility_config()

    # region Visibility management
    def _manual_hidden(self) -> bool:
        return bool(self.definition.config.get("hidden", False))

    def _auto_fade_enabled(self) -> bool:
        return bool(self.definition.config.get("auto_fade_enabled", False))

    def _auto_fade_delay(self) -> int:
        raw = self.definition.config.get(
            "auto_fade_delay_ms", self.DEFAULT_AUTO_FADE_DELAY_MS
        )
        try:
            value = int(raw)
        except (TypeError, ValueError):
            value = self.DEFAULT_AUTO_FADE_DELAY_MS
        return max(500, value)

    def _ensure_activation_defaults(self) -> None:
        config = self.definition.config
        if "activation_mode" not in config:
            config["activation_mode"] = self.ACTIVATION_CLICK_ONCE
        if "hold_behavior" not in config:
            config["hold_behavior"] = self.HOLD_BEHAVIOR_TRUE
        if "repeat_interval_ms" not in config:
            config["repeat_interval_ms"] = self.DEFAULT_REPEAT_INTERVAL_MS
        if "hidden" not in config:
            config["hidden"] = False
        if "auto_fade_enabled" not in config:
            config["auto_fade_enabled"] = False
        if "auto_fade_delay_ms" not in config:
            config["auto_fade_delay_ms"] = self.DEFAULT_AUTO_FADE_DELAY_MS
        if "auto_fade_min_opacity" not in config:
            config["auto_fade_min_opacity"] = int(self.FADE_MIN_OPACITY * 100)

    def _apply_visibility_config(self) -> None:
        if self._manual_hidden():
            self._fade_timer.stop()
            self._idle_timer.stop()
            self.hide()
            self._fade_target = 0.0
            self._set_opacity(0.0)
            return
        if not self.isVisible():
            self.show()
        self._fade_timer.stop()
        self._fade_target = 1.0
        self._set_opacity(1.0)
        if not self._configuration_visible and self._auto_fade_enabled():
            self._schedule_idle_check()
        else:
            self._idle_timer.stop()

    def _register_activity(self) -> None:
        if self._manual_hidden():
            return
        if not self.isVisible():
            self.show()
        self._fade_target = 1.0
        if self.windowOpacity() < 0.99:
            self._fade_timer.start()
        else:
            self._fade_timer.stop()
            self._set_opacity(1.0)
        self._idle_timer.stop()
        if self._hold_sequence or self._toggle_hold_active:
            return
        self._schedule_idle_check()

    def _schedule_idle_check(self) -> None:
        if self._manual_hidden():
            return
        if self._configuration_visible:
            self._idle_timer.stop()
            return
        if not self._auto_fade_enabled():
            self._idle_timer.stop()
            return
        delay = self._auto_fade_delay()
        self._idle_timer.start(delay)

    def _begin_auto_fade(self) -> None:
        if self._manual_hidden():
            return
        target = self._auto_fade_min_opacity()
        self._fade_target = target
        if self.windowOpacity() <= target + 0.02:
            self._set_opacity(target)
            return
        self._fade_timer.start()

    def _advance_fade(self) -> None:
        if self._manual_hidden():
            self._fade_timer.stop()
            return
        current = self.windowOpacity()
        target = self._fade_target
        if abs(current - target) <= 0.02:
            self._set_opacity(target)
            if target <= self._auto_fade_min_opacity() + 0.01:
                self._fade_timer.stop()
            return
        if current < target:
            new_value = min(target, current + self.FADE_STEP)
        else:
            new_value = max(target, current - self.FADE_STEP)
        self._set_opacity(new_value)
        if (
            abs(new_value - target) <= 0.02
            and target <= self._auto_fade_min_opacity() + 0.01
        ):
            self._fade_timer.stop()

    def _set_opacity(self, value: float) -> None:
        bounded = max(0.0, min(1.0, value))
        if abs(self.windowOpacity() - bounded) > 0.005:
            self.setWindowOpacity(bounded)
        else:
            self.setWindowOpacity(bounded)

    # endregion

    # endregion

    def _auto_fade_min_opacity(self) -> float:
        raw = self.definition.config.get(
            "auto_fade_min_opacity", int(self.FADE_MIN_OPACITY * 100)
        )
        try:
            value = float(raw)
        except (TypeError, ValueError):
            value = self.FADE_MIN_OPACITY * 100
        value = max(0.0, min(100.0, value))
        return value / 100.0

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
