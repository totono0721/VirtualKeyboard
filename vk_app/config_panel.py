"""Configuration panel for managing virtual keys."""
from __future__ import annotations

from functools import partial
from typing import Callable, Optional, TYPE_CHECKING

from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QLineEdit,
    QMessageBox,
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

    ACTIVATION_OPTIONS = [
        ("按下触发一次", VirtualKeyWindow.ACTIVATION_CLICK_ONCE),
        ("按下保持按住", VirtualKeyWindow.ACTIVATION_CLICK_HOLD),
        ("悬停保持按住", VirtualKeyWindow.ACTIVATION_HOVER_HOLD),
        ("悬停触发一次", VirtualKeyWindow.ACTIVATION_HOVER_ONCE),
    ]

    HOLD_OPTIONS = [
        ("持续按住", VirtualKeyWindow.HOLD_BEHAVIOR_TRUE),
        ("定期重复按下", VirtualKeyWindow.HOLD_BEHAVIOR_REPEAT),
    ]

    HOLD_ACTIVATION_MODES = {
        VirtualKeyWindow.ACTIVATION_CLICK_HOLD,
        VirtualKeyWindow.ACTIVATION_HOVER_HOLD,
    }

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

        self.toggle_edit_button = QPushButton("拖动调整模式 (自动启用)")
        self.toggle_edit_button.setCheckable(True)
        self.toggle_edit_button.clicked.connect(self.keyboard.toggle_edit_mode)
        operations_layout.addWidget(self.toggle_edit_button)

        self.save_button = QPushButton("保存布局 (Ctrl+S)")
        self.save_button.clicked.connect(self.keyboard.save_layout)
        operations_layout.addWidget(self.save_button)

        self.load_button = QPushButton("加载布局 (Ctrl+O)")
        self.load_button.clicked.connect(self.keyboard.load_layout_from_dialog)
        operations_layout.addWidget(self.load_button)

        self.exit_button = QPushButton("退出程序")
        self.exit_button.clicked.connect(self.keyboard.request_exit)
        operations_layout.addWidget(self.exit_button)

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
        controls_layout = QHBoxLayout()
        self.hide_button = QPushButton("隐藏该按键")
        self.hide_button.clicked.connect(self._on_toggle_hidden)
        controls_layout.addWidget(self.hide_button)
        self.delete_button = QPushButton("删除该按键")
        self.delete_button.clicked.connect(self._on_delete_selected)
        controls_layout.addWidget(self.delete_button)
        controls_layout.addStretch(1)
        detail_layout.addLayout(controls_layout)
        self.form_stack = QStackedWidget()

        self.empty_page = QWidget()
        self.form_stack.addWidget(self.empty_page)

        self.normal_page = QWidget()
        normal_form = QFormLayout(self.normal_page)
        self.normal_label_edit = QLineEdit()
        self.normal_label_edit.textChanged.connect(self._on_normal_label_changed)
        normal_form.addRow("显示文本", self.normal_label_edit)
        self.normal_sequence_edit = QLineEdit()
        self._bind_sequence_field(
            self.normal_sequence_edit,
            getter=self._get_current_normal_sequence,
            setter=self._set_normal_sequence,
        )
        normal_form.addRow("输出内容", self.normal_sequence_edit)
        self.normal_activation_combo = self._create_activation_combo()
        self.normal_activation_combo.currentIndexChanged.connect(
            self._on_normal_activation_changed
        )
        normal_form.addRow("触发方式", self.normal_activation_combo)
        self.normal_hold_combo = self._create_hold_combo()
        self.normal_hold_combo.currentIndexChanged.connect(self._on_normal_hold_behavior_changed)
        normal_form.addRow("长按行为", self.normal_hold_combo)
        self.normal_repeat_spin = self._create_repeat_spin()
        self.normal_repeat_spin.valueChanged.connect(self._on_normal_repeat_interval_changed)
        normal_form.addRow("重复间隔 (毫秒)", self.normal_repeat_spin)
        self.normal_auto_hide_check = QCheckBox("在配置窗口隐藏时自动隐去")
        self.normal_auto_hide_check.toggled.connect(self._on_normal_auto_hide_changed)
        normal_form.addRow("自动隐去", self.normal_auto_hide_check)
        self.normal_auto_hide_delay = self._create_auto_hide_spin()
        self.normal_auto_hide_delay.valueChanged.connect(self._on_normal_auto_hide_delay_changed)
        normal_form.addRow("隐去延迟 (毫秒)", self.normal_auto_hide_delay)
        self.normal_auto_hide_opacity = self._create_opacity_spin()
        self.normal_auto_hide_opacity.valueChanged.connect(
            self._on_normal_auto_hide_opacity_changed
        )
        normal_form.addRow("隐去后不透明度 (%)", self.normal_auto_hide_opacity)
        self.normal_x_spin = self._create_spin_box()
        self.normal_x_spin.valueChanged.connect(self._on_normal_position_changed)
        normal_form.addRow("X 坐标", self.normal_x_spin)
        self.normal_y_spin = self._create_spin_box()
        self.normal_y_spin.valueChanged.connect(self._on_normal_position_changed)
        normal_form.addRow("Y 坐标", self.normal_y_spin)
        self.normal_locked = QCheckBox("禁止拖动该按键")
        self.normal_locked.toggled.connect(self._on_normal_locked_changed)
        normal_form.addRow("拖动锁定", self.normal_locked)
        self.form_stack.addWidget(self.normal_page)

        self.toggle_page = QWidget()
        toggle_form = QFormLayout(self.toggle_page)
        self.toggle_label_edit = QLineEdit()
        self.toggle_label_edit.textChanged.connect(self._on_toggle_label_changed)
        toggle_form.addRow("显示文本", self.toggle_label_edit)
        self.toggle_activation_combo = self._create_activation_combo()
        self.toggle_activation_combo.currentIndexChanged.connect(
            self._on_toggle_activation_changed
        )
        toggle_form.addRow("触发方式", self.toggle_activation_combo)
        self.toggle_hold_combo = self._create_hold_combo()
        self.toggle_hold_combo.currentIndexChanged.connect(self._on_toggle_hold_behavior_changed)
        toggle_form.addRow("长按行为", self.toggle_hold_combo)
        self.toggle_repeat_spin = self._create_repeat_spin()
        self.toggle_repeat_spin.valueChanged.connect(self._on_toggle_repeat_interval_changed)
        toggle_form.addRow("重复间隔 (毫秒)", self.toggle_repeat_spin)
        self.toggle_auto_hide_check = QCheckBox("在配置窗口隐藏时自动隐去")
        self.toggle_auto_hide_check.toggled.connect(self._on_toggle_auto_hide_changed)
        toggle_form.addRow("自动隐去", self.toggle_auto_hide_check)
        self.toggle_auto_hide_delay = self._create_auto_hide_spin()
        self.toggle_auto_hide_delay.valueChanged.connect(self._on_toggle_auto_hide_delay_changed)
        toggle_form.addRow("隐去延迟 (毫秒)", self.toggle_auto_hide_delay)
        self.toggle_auto_hide_opacity = self._create_opacity_spin()
        self.toggle_auto_hide_opacity.valueChanged.connect(
            self._on_toggle_auto_hide_opacity_changed
        )
        toggle_form.addRow("隐去后不透明度 (%)", self.toggle_auto_hide_opacity)
        self.toggle_x_spin = self._create_spin_box()
        self.toggle_x_spin.valueChanged.connect(self._on_toggle_position_changed)
        toggle_form.addRow("X 坐标", self.toggle_x_spin)
        self.toggle_y_spin = self._create_spin_box()
        self.toggle_y_spin.valueChanged.connect(self._on_toggle_position_changed)
        toggle_form.addRow("Y 坐标", self.toggle_y_spin)
        self.toggle_locked = QCheckBox("禁止拖动该按键")
        self.toggle_locked.toggled.connect(self._on_toggle_locked_changed)
        toggle_form.addRow("拖动锁定", self.toggle_locked)
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
        self._bind_sequence_field(
            self.hover_up_edit,
            getter=partial(self._get_hover_sequence, "up"),
            setter=partial(self._set_hover_sequence, "up"),
        )
        hover_form.addRow("上方输出", self.hover_up_edit)
        self.hover_down_edit = QLineEdit()
        self._bind_sequence_field(
            self.hover_down_edit,
            getter=partial(self._get_hover_sequence, "down"),
            setter=partial(self._set_hover_sequence, "down"),
        )
        hover_form.addRow("下方输出", self.hover_down_edit)
        self.hover_left_edit = QLineEdit()
        self._bind_sequence_field(
            self.hover_left_edit,
            getter=partial(self._get_hover_sequence, "left"),
            setter=partial(self._set_hover_sequence, "left"),
        )
        hover_form.addRow("左侧输出", self.hover_left_edit)
        self.hover_right_edit = QLineEdit()
        self._bind_sequence_field(
            self.hover_right_edit,
            getter=partial(self._get_hover_sequence, "right"),
            setter=partial(self._set_hover_sequence, "right"),
        )
        hover_form.addRow("右侧输出", self.hover_right_edit)
        self.hover_activation_combo = self._create_activation_combo()
        self.hover_activation_combo.currentIndexChanged.connect(
            self._on_hover_activation_changed
        )
        hover_form.addRow("触发方式", self.hover_activation_combo)
        self.hover_hold_combo = self._create_hold_combo()
        self.hover_hold_combo.currentIndexChanged.connect(self._on_hover_hold_behavior_changed)
        hover_form.addRow("长按行为", self.hover_hold_combo)
        self.hover_repeat_spin = self._create_repeat_spin()
        self.hover_repeat_spin.valueChanged.connect(self._on_hover_repeat_interval_changed)
        hover_form.addRow("重复间隔 (毫秒)", self.hover_repeat_spin)
        self.hover_auto_hide_check = QCheckBox("在配置窗口隐藏时自动隐去")
        self.hover_auto_hide_check.toggled.connect(self._on_hover_auto_hide_changed)
        hover_form.addRow("自动隐去", self.hover_auto_hide_check)
        self.hover_auto_hide_delay = self._create_auto_hide_spin()
        self.hover_auto_hide_delay.valueChanged.connect(self._on_hover_auto_hide_delay_changed)
        hover_form.addRow("隐去延迟 (毫秒)", self.hover_auto_hide_delay)
        self.hover_auto_hide_opacity = self._create_opacity_spin()
        self.hover_auto_hide_opacity.valueChanged.connect(
            self._on_hover_auto_hide_opacity_changed
        )
        hover_form.addRow("隐去后不透明度 (%)", self.hover_auto_hide_opacity)
        self.hover_x_spin = self._create_spin_box()
        self.hover_x_spin.valueChanged.connect(self._on_hover_position_changed)
        hover_form.addRow("X 坐标", self.hover_x_spin)
        self.hover_y_spin = self._create_spin_box()
        self.hover_y_spin.valueChanged.connect(self._on_hover_position_changed)
        hover_form.addRow("Y 坐标", self.hover_y_spin)
        self.hover_locked = QCheckBox("禁止拖动该按键")
        self.hover_locked.toggled.connect(self._on_hover_locked_changed)
        hover_form.addRow("拖动锁定", self.hover_locked)
        self.form_stack.addWidget(self.hover_page)

        detail_layout.addWidget(self.form_stack)
        self.detail_group.setLayout(detail_layout)
        layout.addWidget(self.detail_group)

        self.refresh_keys()
        self.update_edit_mode(self.keyboard.edit_mode)
        self.update_toggle_button_state()
        self.update_hover_button_state()
        self._show_empty_form()
        self._update_control_buttons()

    def _create_spin_box(self) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(-10000, 10000)
        spin.setSingleStep(5)
        return spin

    def _create_activation_combo(self) -> QComboBox:
        combo = QComboBox()
        for label, value in self.ACTIVATION_OPTIONS:
            combo.addItem(label, value)
        return combo

    def _create_hold_combo(self) -> QComboBox:
        combo = QComboBox()
        for label, value in self.HOLD_OPTIONS:
            combo.addItem(label, value)
        return combo

    def _create_repeat_spin(self) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(10, 5000)
        spin.setSingleStep(50)
        return spin

    def _create_auto_hide_spin(self) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(500, 600000)
        spin.setSingleStep(500)
        return spin

    def _create_opacity_spin(self) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(0, 100)
        spin.setSingleStep(5)
        spin.setSuffix(" %")
        return spin

    def _bind_sequence_field(
        self,
        line_edit: QLineEdit,
        *,
        getter: Callable[[], str],
        setter: Callable[[str], None],
    ) -> None:
        line_edit.setProperty("_last_valid_sequence", "")
        line_edit.editingFinished.connect(
            lambda le=line_edit, get=getter, set_value=setter: self._commit_sequence_field(
                le, get, set_value
            )
        )

    def _commit_sequence_field(
        self,
        line_edit: QLineEdit,
        getter: Callable[[], str],
        setter: Callable[[str], None],
    ) -> None:
        if self._loading or not self.selected_widget:
            return

        raw_text = line_edit.text()
        text = raw_text.strip()
        current_value = getter() or ""
        fallback = line_edit.property("_last_valid_sequence")
        fallback_text = fallback if isinstance(fallback, str) else current_value

        if not text:
            if current_value:
                setter("")
                self.keyboard.notify_key_changed(self.selected_widget)
            if raw_text:
                self._set_line_edit_text(line_edit, "")
            line_edit.setProperty("_last_valid_sequence", "")
            return

        if raw_text.rstrip().endswith("+"):
            self._show_sequence_error("请在“+”后继续填写按键。")
            if raw_text != fallback_text:
                self._set_line_edit_text(line_edit, fallback_text)
            if current_value != fallback_text:
                setter(fallback_text)
                self.keyboard.notify_key_changed(self.selected_widget)
            line_edit.setProperty("_last_valid_sequence", fallback_text)
            return

        try:
            normalized = self.keyboard.key_sender.normalize_sequence(text)
        except ValueError as exc:  # pragma: no cover - UI feedback path
            self._show_sequence_error(str(exc))
            if raw_text != fallback_text:
                self._set_line_edit_text(line_edit, fallback_text)
            if current_value != fallback_text:
                setter(fallback_text)
                self.keyboard.notify_key_changed(self.selected_widget)
            line_edit.setProperty("_last_valid_sequence", fallback_text)
            return

        if normalized != raw_text:
            self._set_line_edit_text(line_edit, normalized)
        if current_value != normalized:
            setter(normalized)
            self.keyboard.notify_key_changed(self.selected_widget)
        line_edit.setProperty("_last_valid_sequence", normalized)

    def _set_line_edit_text(self, line_edit: QLineEdit, text: str) -> None:
        previous = line_edit.blockSignals(True)
        line_edit.setText(text)
        line_edit.setCursorPosition(len(text))
        line_edit.blockSignals(previous)

    def _initialize_sequence_field(self, line_edit: QLineEdit, value: Optional[str]) -> None:
        raw_text = value if isinstance(value, str) else (str(value) if value else "")
        text = raw_text.strip()
        if not text:
            self._set_line_edit_text(line_edit, "")
            line_edit.setProperty("_last_valid_sequence", "")
            return
        try:
            normalized = self.keyboard.key_sender.normalize_sequence(text)
        except ValueError:
            self._set_line_edit_text(line_edit, raw_text)
            line_edit.setProperty("_last_valid_sequence", "")
            return
        self._set_line_edit_text(line_edit, normalized)
        line_edit.setProperty("_last_valid_sequence", normalized)

    def _show_sequence_error(self, detail: str) -> None:
        QMessageBox.warning(self, "无效输出内容", f"无法解析输入：{detail}")

    def _get_current_normal_sequence(self) -> str:
        if not self.selected_widget:
            return ""
        return self.selected_widget.definition.sequence or ""

    def _set_normal_sequence(self, value: str) -> None:
        if not self.selected_widget:
            return
        self.selected_widget.definition.sequence = value

    def _get_hover_sequence(self, direction: str) -> str:
        if not self.selected_widget:
            return ""
        raw = self.selected_widget.definition.config.get(direction, "")
        return str(raw) if raw is not None else ""

    def _set_hover_sequence(self, direction: str, value: str) -> None:
        if not self.selected_widget:
            return
        self.selected_widget.definition.config[direction] = value

    def _select_combo_value(self, combo: QComboBox, value: str) -> None:
        for index in range(combo.count()):
            if combo.itemData(index) == value:
                combo.setCurrentIndex(index)
                return
        if combo.count():
            combo.setCurrentIndex(0)

    def _update_hold_widgets(self, activation_combo: QComboBox, hold_combo: QComboBox, repeat_spin: QSpinBox) -> None:
        mode = activation_combo.currentData()
        hold_enabled = mode in self.HOLD_ACTIVATION_MODES
        hold_combo.setEnabled(hold_enabled)
        repeat_spin.setEnabled(
            hold_enabled and hold_combo.currentData() == VirtualKeyWindow.HOLD_BEHAVIOR_REPEAT
        )

    def _read_repeat_interval(self, widget: VirtualKeyWindow) -> int:
        raw = widget.definition.config.get(
            "repeat_interval_ms", VirtualKeyWindow.DEFAULT_REPEAT_INTERVAL_MS
        )
        try:
            value = int(raw)
        except (TypeError, ValueError):
            value = VirtualKeyWindow.DEFAULT_REPEAT_INTERVAL_MS
        return max(10, value)

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
        self._update_control_buttons()

    def update_edit_mode(self, edit_mode: bool) -> None:
        self.toggle_edit_button.blockSignals(True)
        self.toggle_edit_button.setChecked(edit_mode)
        self.toggle_edit_button.blockSignals(False)
        self.toggle_edit_button.setEnabled(self.keyboard.configuration_visible())

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
            self._update_control_buttons()
            return
        self._load_widget(self.selected_widget)
        self._update_control_buttons()

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
        self._initialize_sequence_field(
            self.normal_sequence_edit, widget.definition.sequence
        )
        position = widget.definition.position
        self.normal_x_spin.setValue(int(position.x()))
        self.normal_y_spin.setValue(int(position.y()))
        self.normal_locked.setChecked(widget.definition.locked)
        activation = str(
            widget.definition.config.get(
                "activation_mode", VirtualKeyWindow.ACTIVATION_CLICK_ONCE
            )
        )
        hold_behavior = str(
            widget.definition.config.get("hold_behavior", VirtualKeyWindow.HOLD_BEHAVIOR_TRUE)
        )
        self._select_combo_value(self.normal_activation_combo, activation)
        self._select_combo_value(self.normal_hold_combo, hold_behavior)
        self.normal_repeat_spin.setValue(self._read_repeat_interval(widget))
        auto_enabled = bool(widget.definition.config.get("auto_fade_enabled", False))
        self.normal_auto_hide_check.setChecked(auto_enabled)
        self.normal_auto_hide_delay.setValue(self._read_auto_hide_delay(widget))
        self.normal_auto_hide_opacity.setValue(self._read_auto_hide_opacity(widget))
        self._update_auto_hide_widgets(
            self.normal_auto_hide_check,
            self.normal_auto_hide_delay,
            self.normal_auto_hide_opacity,
        )
        self._update_hold_widgets(
            self.normal_activation_combo, self.normal_hold_combo, self.normal_repeat_spin
        )

    def _load_toggle_widget(self, widget: VirtualKeyWindow) -> None:
        self.form_stack.setCurrentIndex(self.TOGGLE_INDEX)
        self.toggle_label_edit.setText(widget.definition.label)
        position = widget.definition.position
        self.toggle_x_spin.setValue(int(position.x()))
        self.toggle_y_spin.setValue(int(position.y()))
        self.toggle_locked.setChecked(widget.definition.locked)
        activation = str(
            widget.definition.config.get(
                "activation_mode", VirtualKeyWindow.ACTIVATION_CLICK_ONCE
            )
        )
        hold_behavior = str(
            widget.definition.config.get("hold_behavior", VirtualKeyWindow.HOLD_BEHAVIOR_TRUE)
        )
        self._select_combo_value(self.toggle_activation_combo, activation)
        self._select_combo_value(self.toggle_hold_combo, hold_behavior)
        self.toggle_repeat_spin.setValue(self._read_repeat_interval(widget))
        auto_enabled = bool(widget.definition.config.get("auto_fade_enabled", False))
        self.toggle_auto_hide_check.setChecked(auto_enabled)
        self.toggle_auto_hide_delay.setValue(self._read_auto_hide_delay(widget))
        self.toggle_auto_hide_opacity.setValue(self._read_auto_hide_opacity(widget))
        self._update_auto_hide_widgets(
            self.toggle_auto_hide_check,
            self.toggle_auto_hide_delay,
            self.toggle_auto_hide_opacity,
        )
        self._update_hold_widgets(
            self.toggle_activation_combo, self.toggle_hold_combo, self.toggle_repeat_spin
        )

    def _load_hover_widget(self, widget: VirtualKeyWindow) -> None:
        self.form_stack.setCurrentIndex(self.HOVER_INDEX)
        self.hover_name_edit.setText(widget.definition.label)
        self.hover_center_label_edit.setText(
            str(widget.definition.config.get("center_label", widget.definition.label))
        )
        self._initialize_sequence_field(
            self.hover_up_edit, widget.definition.config.get("up", "")
        )
        self._initialize_sequence_field(
            self.hover_down_edit, widget.definition.config.get("down", "")
        )
        self._initialize_sequence_field(
            self.hover_left_edit, widget.definition.config.get("left", "")
        )
        self._initialize_sequence_field(
            self.hover_right_edit, widget.definition.config.get("right", "")
        )
        position = widget.definition.position
        self.hover_x_spin.setValue(int(position.x()))
        self.hover_y_spin.setValue(int(position.y()))
        self.hover_locked.setChecked(widget.definition.locked)
        activation = str(
            widget.definition.config.get(
                "activation_mode", VirtualKeyWindow.ACTIVATION_HOVER_HOLD
            )
        )
        hold_behavior = str(
            widget.definition.config.get("hold_behavior", VirtualKeyWindow.HOLD_BEHAVIOR_TRUE)
        )
        self._select_combo_value(self.hover_activation_combo, activation)
        self._select_combo_value(self.hover_hold_combo, hold_behavior)
        self.hover_repeat_spin.setValue(self._read_repeat_interval(widget))
        auto_enabled = bool(widget.definition.config.get("auto_fade_enabled", False))
        self.hover_auto_hide_check.setChecked(auto_enabled)
        self.hover_auto_hide_delay.setValue(self._read_auto_hide_delay(widget))
        self.hover_auto_hide_opacity.setValue(self._read_auto_hide_opacity(widget))
        self._update_auto_hide_widgets(
            self.hover_auto_hide_check,
            self.hover_auto_hide_delay,
            self.hover_auto_hide_opacity,
        )
        self._update_hold_widgets(
            self.hover_activation_combo, self.hover_hold_combo, self.hover_repeat_spin
        )

    def _describe_widget(self, widget: VirtualKeyWindow) -> str:
        kind = widget.definition.kind or "normal"
        label = widget.definition.label or "(未命名)"
        status = []
        if widget.definition.config.get("hidden"):
            status.append("隐藏")
        if widget.definition.config.get("auto_fade_enabled"):
            status.append("自动隐去")
        suffix = f" [{'，'.join(status)}]" if status else ""
        return f"{label} - {self._kind_display(kind)}{suffix}"

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

    def _on_normal_activation_changed(self, index: int) -> None:
        if self._loading or not self.selected_widget:
            return
        mode = str(self.normal_activation_combo.currentData())
        self.selected_widget.definition.config["activation_mode"] = mode
        self._update_hold_widgets(
            self.normal_activation_combo, self.normal_hold_combo, self.normal_repeat_spin
        )
        self.keyboard.notify_key_changed(self.selected_widget)

    def _on_normal_hold_behavior_changed(self, index: int) -> None:
        if self._loading or not self.selected_widget:
            return
        behavior = str(self.normal_hold_combo.currentData())
        self.selected_widget.definition.config["hold_behavior"] = behavior
        self._update_hold_widgets(
            self.normal_activation_combo, self.normal_hold_combo, self.normal_repeat_spin
        )
        self.keyboard.notify_key_changed(self.selected_widget)

    def _on_normal_repeat_interval_changed(self, value: int) -> None:
        if self._loading or not self.selected_widget:
            return
        self.selected_widget.definition.config["repeat_interval_ms"] = int(value)
        self.keyboard.notify_key_changed(self.selected_widget)

    def _on_normal_auto_hide_changed(self, checked: bool) -> None:
        if self._loading or not self.selected_widget:
            return
        self.selected_widget.definition.config["auto_fade_enabled"] = bool(checked)
        self._update_auto_hide_widgets(
            self.normal_auto_hide_check,
            self.normal_auto_hide_delay,
            self.normal_auto_hide_opacity,
        )
        self.keyboard.notify_key_changed(self.selected_widget)

    def _on_normal_auto_hide_delay_changed(self, value: int) -> None:
        if self._loading or not self.selected_widget:
            return
        self.selected_widget.definition.config["auto_fade_delay_ms"] = int(value)
        self.keyboard.notify_key_changed(self.selected_widget)

    def _on_normal_auto_hide_opacity_changed(self, value: int) -> None:
        if self._loading or not self.selected_widget:
            return
        self.selected_widget.definition.config["auto_fade_min_opacity"] = int(value)
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

    def _on_toggle_activation_changed(self, index: int) -> None:
        if self._loading or not self.selected_widget:
            return
        mode = str(self.toggle_activation_combo.currentData())
        self.selected_widget.definition.config["activation_mode"] = mode
        self._update_hold_widgets(
            self.toggle_activation_combo, self.toggle_hold_combo, self.toggle_repeat_spin
        )
        self.keyboard.notify_key_changed(self.selected_widget)

    def _on_toggle_hold_behavior_changed(self, index: int) -> None:
        if self._loading or not self.selected_widget:
            return
        behavior = str(self.toggle_hold_combo.currentData())
        self.selected_widget.definition.config["hold_behavior"] = behavior
        self._update_hold_widgets(
            self.toggle_activation_combo, self.toggle_hold_combo, self.toggle_repeat_spin
        )
        self.keyboard.notify_key_changed(self.selected_widget)

    def _on_toggle_repeat_interval_changed(self, value: int) -> None:
        if self._loading or not self.selected_widget:
            return
        self.selected_widget.definition.config["repeat_interval_ms"] = int(value)
        self.keyboard.notify_key_changed(self.selected_widget)

    def _on_toggle_auto_hide_changed(self, checked: bool) -> None:
        if self._loading or not self.selected_widget:
            return
        self.selected_widget.definition.config["auto_fade_enabled"] = bool(checked)
        self._update_auto_hide_widgets(
            self.toggle_auto_hide_check,
            self.toggle_auto_hide_delay,
            self.toggle_auto_hide_opacity,
        )
        self.keyboard.notify_key_changed(self.selected_widget)

    def _on_toggle_auto_hide_delay_changed(self, value: int) -> None:
        if self._loading or not self.selected_widget:
            return
        self.selected_widget.definition.config["auto_fade_delay_ms"] = int(value)
        self.keyboard.notify_key_changed(self.selected_widget)

    def _on_toggle_auto_hide_opacity_changed(self, value: int) -> None:
        if self._loading or not self.selected_widget:
            return
        self.selected_widget.definition.config["auto_fade_min_opacity"] = int(value)
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

    def _on_hover_activation_changed(self, index: int) -> None:
        if self._loading or not self.selected_widget:
            return
        mode = str(self.hover_activation_combo.currentData())
        self.selected_widget.definition.config["activation_mode"] = mode
        self._update_hold_widgets(
            self.hover_activation_combo, self.hover_hold_combo, self.hover_repeat_spin
        )
        self.keyboard.notify_key_changed(self.selected_widget)

    def _on_hover_hold_behavior_changed(self, index: int) -> None:
        if self._loading or not self.selected_widget:
            return
        behavior = str(self.hover_hold_combo.currentData())
        self.selected_widget.definition.config["hold_behavior"] = behavior
        self._update_hold_widgets(
            self.hover_activation_combo, self.hover_hold_combo, self.hover_repeat_spin
        )
        self.keyboard.notify_key_changed(self.selected_widget)

    def _on_hover_repeat_interval_changed(self, value: int) -> None:
        if self._loading or not self.selected_widget:
            return
        self.selected_widget.definition.config["repeat_interval_ms"] = int(value)
        self.keyboard.notify_key_changed(self.selected_widget)

    def _on_hover_auto_hide_changed(self, checked: bool) -> None:
        if self._loading or not self.selected_widget:
            return
        self.selected_widget.definition.config["auto_fade_enabled"] = bool(checked)
        self._update_auto_hide_widgets(
            self.hover_auto_hide_check,
            self.hover_auto_hide_delay,
            self.hover_auto_hide_opacity,
        )
        self.keyboard.notify_key_changed(self.selected_widget)

    def _on_hover_auto_hide_delay_changed(self, value: int) -> None:
        if self._loading or not self.selected_widget:
            return
        self.selected_widget.definition.config["auto_fade_delay_ms"] = int(value)
        self.keyboard.notify_key_changed(self.selected_widget)

    def _on_hover_auto_hide_opacity_changed(self, value: int) -> None:
        if self._loading or not self.selected_widget:
            return
        self.selected_widget.definition.config["auto_fade_min_opacity"] = int(value)
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

    def _on_delete_selected(self) -> None:
        if not self.selected_widget:
            return
        self.keyboard.remove_key(self.selected_widget)
        self.selected_widget = None
        self._update_control_buttons()

    def _on_toggle_hidden(self) -> None:
        if not self.selected_widget:
            return
        hidden = bool(self.selected_widget.definition.config.get("hidden", False))
        self.selected_widget.set_manual_hidden(not hidden)
        self.keyboard.notify_key_changed(self.selected_widget)
        self._update_control_buttons()

    def _update_auto_hide_widgets(self, checkbox: QCheckBox, *widgets) -> None:
        for widget in widgets:
            widget.setEnabled(checkbox.isChecked())

    def _read_auto_hide_delay(self, widget: VirtualKeyWindow) -> int:
        raw = widget.definition.config.get(
            "auto_fade_delay_ms", VirtualKeyWindow.DEFAULT_AUTO_FADE_DELAY_MS
        )
        try:
            value = int(raw)
        except (TypeError, ValueError):
            value = VirtualKeyWindow.DEFAULT_AUTO_FADE_DELAY_MS
        return max(500, value)

    def _read_auto_hide_opacity(self, widget: VirtualKeyWindow) -> int:
        raw = widget.definition.config.get(
            "auto_fade_min_opacity", int(VirtualKeyWindow.FADE_MIN_OPACITY * 100)
        )
        try:
            value = float(raw)
        except (TypeError, ValueError):
            value = VirtualKeyWindow.FADE_MIN_OPACITY * 100
        return int(max(0.0, min(100.0, value)))

    def _update_control_buttons(self) -> None:
        has_selection = self.selected_widget is not None
        self.delete_button.setEnabled(has_selection)
        self.hide_button.setEnabled(has_selection)
        if not has_selection:
            self.hide_button.setText("隐藏该按键")
            return
        hidden = bool(self.selected_widget.definition.config.get("hidden", False))
        self.hide_button.setText("显示该按键" if hidden else "隐藏该按键")
