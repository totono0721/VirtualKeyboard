"""Main window hosting the virtual keyboard and configuration panel."""
from __future__ import annotations

import json
import os
from typing import List, Optional

from PyQt6.QtCore import QPoint, QRect, Qt
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QFileDialog,
    QMainWindow,
    QMessageBox,
)

from .config_panel import ConfigurationPanel
from .focus import FocusKeeper
from .input_sender import KeySender
from .keys import HoverHoldKeyWindow, VirtualKeyWindow
from .models import KeyDefinition


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
        self.layout_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "layout.json"))
        self.config_panel: Optional[ConfigurationPanel] = None

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

    # region Key management
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
            widget.close()
            widget.deleteLater()
            if self.config_panel:
                self.config_panel.refresh_keys()
                self.config_panel.update_toggle_button_state()
                self.config_panel.update_hover_button_state()

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

    def toggle_edit_mode(self) -> None:
        self.edit_mode = not self.edit_mode
        if self.toggle_edit_action:
            self.toggle_edit_action.blockSignals(True)
            self.toggle_edit_action.setChecked(self.edit_mode)
            self.toggle_edit_action.blockSignals(False)
        for widget in self.keys:
            widget.on_edit_mode_changed()
            widget.update_style()
        if self.config_panel:
            self.config_panel.update_edit_mode(self.edit_mode)

    def toggle_key_available(self) -> bool:
        return True

    def hover_key_available(self) -> bool:
        return True

    # endregion

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
            self.config_panel.update_toggle_button_state()
            self.config_panel.update_hover_button_state()

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
            self.config_panel.update_toggle_button_state()
            self.config_panel.update_hover_button_state()
        return widget
