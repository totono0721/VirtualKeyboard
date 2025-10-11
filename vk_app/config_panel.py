"""Configuration panel for managing virtual keys."""
from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .keys import VirtualKeyWindow

if TYPE_CHECKING:  # pragma: no cover
    from .keyboard_window import KeyboardWindow


class ConfigurationPanel(QWidget):
    EMPTY_INDEX = 0
    NORMAL_INDEX = 1
    TOGGLE_INDEX = 2
    HOVER_INDEX = 3

    def __init__(self, keyboard: "KeyboardWindow") -> None:
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
        self.hover_down_edit.textChanged.connect(
            lambda text: self._on_hover_sequence_changed("down", text)
        )
        hover_form.addRow("下方输出", self.hover_down_edit)
        self.hover_left_edit = QLineEdit()
        self.hover_left_edit.textChanged.connect(
            lambda text: self._on_hover_sequence_changed("left", text)
        )
        hover_form.addRow("左侧输出", self.hover_left_edit)
        self.hover_right_edit = QLineEdit()
        self.hover_right_edit.textChanged.connect(
            lambda text: self._on_hover_sequence_changed("right", text)
        )
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
        self.update_toggle_button_state()
        self.update_hover_button_state()
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
        self.selected_widget = current.data(Qt.ItemDataRole.UserRole) if current else None
        if not self.selected_widget:
            self._show_empty_form()
            return
        self._load_widget(self.selected_widget)

    def _load_widget(self, widget: VirtualKeyWindow) -> None:
        self._loading = True
        kind = widget.definition.kind or "normal"
        if kind == "toggle_config":
            self._load_toggle_widget(widget)
        elif kind == "hover_hold":
            self._load_hover_widget(widget)
        else:
            self._load_normal_widget(widget)
        self.detail_group.setTitle(self._describe_widget(widget))
        self._loading = False

    def _load_normal_widget(self, widget: VirtualKeyWindow) -> None:
        self.form_stack.setCurrentIndex(self.NORMAL_INDEX)
        self.normal_label_edit.setText(widget.definition.label)
        self.normal_sequence_edit.setText(widget.definition.sequence)
        position = widget.definition.position
        self.normal_x_spin.setValue(int(position.x()))
        self.normal_y_spin.setValue(int(position.y()))
        self.normal_locked.setChecked(widget.definition.locked)

    def _load_toggle_widget(self, widget: VirtualKeyWindow) -> None:
        self.form_stack.setCurrentIndex(self.TOGGLE_INDEX)
        self.toggle_label_edit.setText(widget.definition.label)
        position = widget.definition.position
        self.toggle_x_spin.setValue(int(position.x()))
        self.toggle_y_spin.setValue(int(position.y()))
        self.toggle_locked.setChecked(widget.definition.locked)

    def _load_hover_widget(self, widget: VirtualKeyWindow) -> None:
        self.form_stack.setCurrentIndex(self.HOVER_INDEX)
        self.hover_name_edit.setText(widget.definition.label)
        self.hover_center_label_edit.setText(
            str(widget.definition.config.get("center_label", widget.definition.label))
        )
        self.hover_up_edit.setText(str(widget.definition.config.get("up", "")))
        self.hover_down_edit.setText(str(widget.definition.config.get("down", "")))
        self.hover_left_edit.setText(str(widget.definition.config.get("left", "")))
        self.hover_right_edit.setText(str(widget.definition.config.get("right", "")))
        position = widget.definition.position
        self.hover_x_spin.setValue(int(position.x()))
        self.hover_y_spin.setValue(int(position.y()))
        self.hover_locked.setChecked(widget.definition.locked)

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

    def update_toggle_button_state(self) -> None:
        self.add_toggle_button.setEnabled(self.keyboard.toggle_key_available())

    def update_hover_button_state(self) -> None:
        self.add_hover_button.setEnabled(self.keyboard.hover_key_available())
