# Development Notes
## Module Overview
- `virtual_keyboard.py` 只负责入口，初始化时会调用 `vk_app.main()`。
- `vk_app/` 目录按照职责拆分：
  - `winapi.py`：封装 `SendInput`/`AttachThreadInput` 等 Win32 结构与函数。
  - `input_sender.py`：负责按键解析与输入事件发送。
  - `focus.py`：跟踪并恢复前台窗口焦点。
  - `models.py`：定义 `KeyDefinition` 及序列化逻辑。
  - `keys/`：包含所有虚拟按键窗口实现（普通按键、悬停长按等）。
  - `config_panel.py`：配置面板 UI 及按键信息编辑逻辑。
  - `keyboard_window.py`：主窗口，负责管理按键、布局读写等。
  - `app.py`：应用引导，创建 `QApplication` 并启动主窗口。

## Adding a New Key Type
1. 在 `vk_app/keys/` 下新增子类，继承 `VirtualKeyWindow`。可覆写 `on_activation`、鼠标事件或 `paintEvent` 等行为。
2. 在 `vk_app/keys/__init__.py` 中导出新类，便于其他模块引用。
3. 修改 `KeyboardWindow._create_key_widget`，根据 `KeyDefinition.kind` 返回对应的新按键类实例，并在必要时提供默认 `KeyDefinition.config`。
4. 若需要在配置面板中可视化配置参数：
   - 在 `ConfigurationPanel` 中为新类型新增表单页或控件。
   - 在 `_load_*` 与 `_on_*` 事件处理器中同步 `KeyDefinition` 的字段。
5. 更新默认布局或创建按键的入口（例如 `KeyboardWindow.add_<type>_key`）以便用户在 UI 中添加该类型。

## Known Limitations / Future Hooks
- 本项目只在 Windows 10/11 环境下运行，容器中无法直接测试。发送按键使用 Win32 `SendInput`，目前仅支持简单按键以及 `Ctrl`/`Alt`/`Shift` 的组合。
- `FocusKeeper` 利用轮询记录当前活动窗口。对具有自定义焦点管理的程序可能需要额外的 `AttachThreadInput` 处理。
- 吸附逻辑是基于部件外边界的简单阈值比较，后续可以扩展为网格或磁吸到屏幕边缘。
- 当前保存文件写到程序目录下的 `layout.json`，未来可以加入多方案管理或者云同步。
- UI 采用 PyQt6，如需改成 C++/Rust 实现，可复用 `layout.json` 文件格式。
- 遇到部分窗口发送失败时，程序会回退调用 `keybd_event`。若错误代码为 5（Access Denied），需要提示用户提升权限。

## Coding Style
- 使用类型注解（`typing`）提高可读性。
- UI 相关的字符串常量集中定义在类属性内，便于后续国际化。
