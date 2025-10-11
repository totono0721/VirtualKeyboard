# 虚拟按键面板 (Virtual Keyboard)

一个基于 PyQt6 的 Windows 虚拟按键工具，可以在桌面上创建多种自定义虚拟按键。通过配置面板即可管理按键属性、保存/加载布局，并在点击或悬停时向前台应用发送键盘输入。

## 功能特性
- ⚙️ **可配置按键**：在配置面板或菜单中新建按键，自定义显示文本与发送的按键序列（支持 `Ctrl`/`Alt`/`Shift` 组合）。
- 🪟 **配置面板切换键**：可生成一个虚拟按键用于显示/隐藏配置窗口，方便在游戏或全屏应用中快速开关设置界面。
- 🧭 **悬停长按键**：提供 2×2 布局的特殊按键，上下左右四个梯形区域在鼠标悬停时持续触发对应快捷键，中间区域保持静默，可用于模拟方向键或移动操作。
- 🎯 **焦点保持**：触发虚拟按键后自动恢复目标窗口焦点，确保按键事件发送到正确的应用。
- 📌 **锁定与编辑模式**：`Ctrl+E` 切换编辑模式。编辑模式下拖动未锁定的按键，锁定后描边变为蓝色且无法移动。
- 🧲 **吸附与对齐**：拖动按键靠近其他按键时会自动吸附，便于快速排布。
- 💾 **布局持久化**：读取/保存 `layout.json` 描述文件，可快速切换不同布局方案。

## 项目结构
```
virtual_keyboard.py   # 程序入口，仅负责平台检查与调用 vk_app.main()
vk_app/
├── app.py            # QApplication 初始化
├── config_panel.py   # 配置面板 UI 及事件处理
├── focus.py          # 焦点跟踪与恢复
├── input_sender.py   # SendInput 封装与按键序列解析
├── keyboard_window.py# 主窗口与按键管理逻辑
├── models.py         # KeyDefinition 数据模型
├── winapi.py         # Win32 结构体/函数声明
└── keys/             # 不同类型的虚拟按键组件
    ├── base.py       # 普通按键实现
    └── hover_hold.py # 悬停长按键
```

添加新的按键类型时，需要在 `vk_app/keys/` 目录创建对应组件，并在 `KeyboardWindow._create_key_widget` 及配置面板中注册，详见 [`AGENTS.md`](AGENTS.md) 中的流程说明。

## 环境要求
- Windows 10/11
- Python 3.10 或更高版本

## 安装步骤
1. 安装依赖：
   ```powershell
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```
2. 运行程序：
   ```powershell
   python virtual_keyboard.py
   ```

首次运行会在项目目录生成空的 `layout.json`。如果没有任何按键，可使用配置面板左上角的“新增按键”或“添加悬停长按按键”等按钮创建。

## 使用说明
### 配置面板
- 面板中列出了所有虚拟按键，可选择任意按键查看/编辑详细信息。
- “锁定”选项可禁止拖动；坐标既可在面板中输入，也可在编辑模式下直接拖动按键窗口。
- 特殊按键拥有独立的配置项，例如悬停长按键可以分别设置上下左右四个方向的快捷键文本。

### 键位操作
- 左键点击普通按键会发送配置好的按键序列。
- 悬停长按键无需点击，鼠标停留在对应区域即会持续按下配置快捷键，移出后自动释放。
- 配置面板切换键可在任意布局中添加，点击后在显示/隐藏配置窗口之间切换。

### 保存与加载
- `Ctrl+S` 保存当前布局到 `layout.json`（或最近一次从文件对话框选择的路径）。
- `Ctrl+O` 从 JSON 布局文件加载，便于维护多套配置。
- 关闭程序时会自动保存当前布局。

## 打包建议
该项目可使用 [PyInstaller](https://pyinstaller.org/) 打包：
```powershell
pyinstaller --noconfirm --noconsole --name VirtualKeyPad virtual_keyboard.py
```
打包后请将 `layout.json` 与可执行文件放在同一目录，以启用默认布局读取。

## 疑难解答
- 程序只能在 Windows 上运行；在其他平台会直接退出。
- 某些具有反作弊或高权限保护的程序可能屏蔽 `SendInput`，此时虚拟按键无效。
- 如遇到 "SendInput failed" 或错误 5，请以管理员身份运行本程序，或确保目标窗口未以更高权限运行。程序会尝试回退到 `keybd_event`。
- 多显示器与高 DPI 环境下默认启用 `SetProcessDPIAware`，若仍有缩放问题可在可执行文件属性中配置 DPI 设置。

更多开发笔记与扩展说明请参见 [`AGENTS.md`](AGENTS.md)。
