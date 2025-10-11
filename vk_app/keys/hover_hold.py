"""Hover-sensitive key implementation."""
from __future__ import annotations

from typing import Dict, Optional

from PyQt6.QtCore import QPoint, QPointF, Qt
from PyQt6.QtGui import QColor, QFont, QMouseEvent, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QMenu

from ..models import KeyDefinition
from .base import VirtualKeyWindow


class HoverHoldKeyWindow(VirtualKeyWindow):
    SIZE = 160

    def __init__(self, definition: KeyDefinition, keyboard) -> None:
        super().__init__(definition, keyboard)
        self.setFixedSize(self.SIZE, self.SIZE)
        # Enable hover tracking so we receive mouseMoveEvent updates even when no
        # button is pressed. Without this the directional areas would never
        # detect the cursor entering them, so the configured press-hold
        # shortcuts would not trigger.
        self.setMouseTracking(True)
        self._active_region: Optional[str] = None
        self._active_combo = None
        self._paths = self._build_paths()

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
