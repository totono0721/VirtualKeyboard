"""Hover-sensitive key implementation."""
from __future__ import annotations

from typing import Dict, Optional

from PyQt6.QtCore import QEvent, QPoint, QPointF, Qt
from PyQt6.QtGui import (
    QColor,
    QFont,
    QHoverEvent,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
)
from PyQt6.QtWidgets import QMenu

from ..models import KeyDefinition
from .base import VirtualKeyWindow


class HoverHoldKeyWindow(VirtualKeyWindow):
    SIZE = 160

    def __init__(self, definition: KeyDefinition, keyboard) -> None:
        definition.config.setdefault("activation_mode", self.ACTIVATION_HOVER_HOLD)
        definition.config.setdefault("hold_behavior", self.HOLD_BEHAVIOR_TRUE)
        definition.config.setdefault("repeat_interval_ms", self.DEFAULT_REPEAT_INTERVAL_MS)
        super().__init__(definition, keyboard)
        self.setFixedSize(self.SIZE, self.SIZE)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setMouseTracking(True)
        self._paths = self._build_paths()
        self._highlight_region: Optional[str] = None
        self._engaged_region: Optional[str] = None
        self._hover_once_region: Optional[str] = None

    def _build_paths(self) -> Dict[str, QPainterPath]:
        paths: Dict[str, QPainterPath] = {}
        width = float(self.width())
        height = float(self.height())
        margin = 10.0
        center_size = min(width, height) / 2.5
        left = margin
        right = width - margin
        top = margin
        bottom = height - margin
        cx = width / 2.0
        cy = height / 2.0

        def polygon(points: list[tuple[float, float]]) -> QPainterPath:
            path = QPainterPath()
            if not points:
                return path
            first = points[0]
            path.moveTo(*first)
            for point in points[1:]:
                path.lineTo(*point)
            path.closeSubpath()
            return path

        paths["center"] = polygon(
            [
                (cx - center_size / 2, cy - center_size / 2),
                (cx + center_size / 2, cy - center_size / 2),
                (cx + center_size / 2, cy + center_size / 2),
                (cx - center_size / 2, cy + center_size / 2),
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

    def on_definition_changed(self) -> None:
        super().on_definition_changed()
        self.setMouseTracking(True)
        self._hover_once_region = None
        self._update_region_highlight(None)

    def _handle_hover_enter(self) -> None:
        # Region-aware hover handling is managed via _handle_pointer_update.
        return

    def _handle_hover_leave(self) -> None:
        self._hover_once_region = None
        self._stop_region_hold()

    def on_edit_mode_changed(self) -> None:
        super().on_edit_mode_changed()
        self._engaged_region = None
        self._hover_once_region = None
        self._update_region_highlight(None)

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        border_color = QColor(self._border_color)
        if self._highlight_region:
            border_color = border_color.lighter(135)
        painter.setPen(QPen(border_color, 3 if self._highlight_region else 2))

        colors = {
            "up": QColor("#2c7fb8"),
            "down": QColor("#41ab5d"),
            "left": QColor("#f03b20"),
            "right": QColor("#9e9ac8"),
            "center": QColor(0, 0, 0, 180),
        }

        lighten_factor = 120
        for region, path in self._paths.items():
            fill_color = colors.get(region, QColor("#5f5f5f"))
            if region == self._highlight_region:
                fill_color = QColor(fill_color).lighter(lighten_factor)
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
            region = self._resolve_region(event.position())
            if region:
                self._register_activity()
            self._handle_region_activation(region, from_hover=False)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        super().mouseMoveEvent(event)
        if self.keyboard.edit_mode:
            self._update_region_highlight(None)
            return
        self._handle_pointer_update(event.position(), from_hover=True)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton and not self.keyboard.edit_mode:
            if self._activation_mode() in {self.ACTIVATION_CLICK_HOLD, self.ACTIVATION_HOVER_HOLD}:
                self._stop_region_hold()
            event.accept()
            return
        super().mouseReleaseEvent(event)

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
        self._update_region_highlight(None)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # type: ignore[override]
        self._hover_once_region = None
        self._update_region_highlight(None)
        super().leaveEvent(event)

    def event(self, event):  # type: ignore[override]
        if isinstance(event, QHoverEvent) and not self.keyboard.edit_mode:
            if event.type() in (QEvent.Type.HoverEnter, QEvent.Type.HoverMove):
                self._handle_pointer_update(event.position(), from_hover=True)
                return True
            if event.type() == QEvent.Type.HoverLeave:
                self._hover_once_region = None
                self._update_region_highlight(None)
                self._stop_region_hold()
                return True
        return super().event(event)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self._stop_region_hold()
        super().closeEvent(event)

    def _resolve_region(self, position: QPointF) -> Optional[str]:
        for region, path in self._paths.items():
            if path.contains(position):
                return region
        return None

    def _handle_pointer_update(self, position: QPointF, *, from_hover: bool) -> None:
        region = self._resolve_region(position)
        self._update_region_highlight(region)
        if region and not self.keyboard.edit_mode:
            self._register_activity()
        if from_hover:
            mode = self._activation_mode()
            if mode == self.ACTIVATION_HOVER_HOLD:
                self._handle_region_activation(region, from_hover=True)
            elif mode == self.ACTIVATION_HOVER_ONCE:
                self._trigger_region_once(region, from_hover=True)

    def _handle_region_activation(self, region: Optional[str], *, from_hover: bool) -> None:
        mode = self._activation_mode()
        if mode in {self.ACTIVATION_CLICK_ONCE, self.ACTIVATION_HOVER_ONCE}:
            self._trigger_region_once(region, from_hover=from_hover)
        elif mode in {self.ACTIVATION_CLICK_HOLD, self.ACTIVATION_HOVER_HOLD}:
            if region in {"up", "down", "left", "right"}:
                self._start_region_hold(region)
            else:
                self._stop_region_hold()
        else:
            self._update_region_highlight(region)

    def _update_region_highlight(self, region: Optional[str]) -> None:
        if region == self._highlight_region:
            return
        self._highlight_region = region
        self.update()

    def _trigger_region_once(self, region: Optional[str], *, from_hover: bool) -> None:
        if region not in {"up", "down", "left", "right"}:
            if not from_hover:
                self._stop_region_hold()
            return
        if from_hover and self._hover_once_region == region:
            return
        sequence = str(self.definition.config.get(region, "")).strip()
        if not sequence:
            return
        if from_hover:
            self._hover_once_region = region
        else:
            self._hover_once_region = None
        if self._send_sequence_once(sequence):
            self._flash_activation_feedback()
            self._register_activity()

    def _start_region_hold(self, region: Optional[str]) -> None:
        if region not in {"up", "down", "left", "right"}:
            self._stop_region_hold()
            return
        sequence = str(self.definition.config.get(region, "")).strip()
        if not sequence:
            self._stop_region_hold()
            return
        if self._engaged_region == region and self._hold_sequence == sequence:
            return
        self._stop_region_hold()
        self._start_hold_sequence(sequence)
        if self._hold_sequence == sequence:
            self._engaged_region = region

    def _stop_region_hold(self) -> None:
        self._engaged_region = None
        self._hover_once_region = None
        self._stop_hold_sequence()
