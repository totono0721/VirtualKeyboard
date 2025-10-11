# 虚拟按键面板 (Virtual Keyboard)

一个基于 PyQt6 的 Windows 虚拟按键工具，可以在桌面上创建一个或多个自定义虚拟按键，保持目标应用的焦点并向其发送键盘输入。

## 功能特性
- ⚙️ **可配置按键**：通过菜单新建按键，自定义显示文本与发送的按键序列（支持 `Ctrl`/`Alt`/`Shift` 组合）。
- 🪟 **独立悬浮键窗**：每个按键都是单独的半透明无边框窗口，不包含关闭/最小化等系统控件，只显示按键本身。
- 🎯 **保持焦点**：点击虚拟按键时会自动恢复之前处于前台的窗口，确保输入发送到目标程序。
- 📌 **锁定与编辑模式**：`Ctrl+E` 切换编辑模式。编辑模式下可拖动未锁定的按键；锁定后的按键在任意模式下位置固定，仅改变为蓝色描边。
- 🧲 **吸附与对齐**：拖动按键靠近其他按键边缘时会自动吸附，便于快速排布。
- 💾 **布局持久化**：启动时自动读取 `layout.json`，关闭或执行“保存布局”时写回当前布局，可自由加载/保存不同文件。
- 🪟 **置顶窗口**：管理面板和各个按键窗口保持置顶，便于与全屏/窗口化应用搭配使用。

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

首次运行会在项目目录生成空的 `layout.json`。如果没有任何按键，可使用菜单“布局 → 新增按键”创建。

## 使用说明
### 编辑与移动
- 使用 `Ctrl+E` 或菜单中的“切换编辑模式”进入编辑模式。
- 编辑模式下，未锁定的按键可直接拖动；靠近其他按键约 15 像素范围内会自动吸附。
- 右键按键可以单独“锁定按键”，锁定后描边变为蓝色，位置固定。

### 自定义按键
- 在按键窗口上右键选择“设置按键显示/输出…”。
- “显示文本”用于按钮上的文字；“发送内容”可以填写：
  - 单字符（如 `a`, `1`, `?`）。大小写会根据当前键盘布局自动补齐 `Shift`。
  - 特殊键名称（`Enter`, `Esc`, `Tab`, `Space`, `Backspace`, `Delete`, `Home`, `End`, `PageUp`, `PageDown`, `Up`, `Down`, `Left`, `Right`）。
  - 组合键（例如 `Ctrl+Alt+L`、`Shift+Enter`）。

### 保存与加载
- `Ctrl+S` 保存当前布局到 `layout.json`。
- `Ctrl+O` 从任意 JSON 文件加载布局，可创建多套布局。
- 关闭程序时会自动保存到当前使用的布局文件。

## 编译/打包建议
该项目为 Python 脚本，可使用 [PyInstaller](https://pyinstaller.org/) 进行打包：
```powershell
pyinstaller --noconfirm --noconsole --name VirtualKeyPad virtual_keyboard.py
```
打包后会在 `dist/VirtualKeyPad/` 下生成可执行文件，记得将 `layout.json` 放在同级目录以启用默认布局。

## 疑难解答
- 程序只能在 Windows 上运行；在其他平台会直接退出。
- 某些安全策略较严格的程序（如游戏防作弊）可能屏蔽 `SendInput`，此时虚拟按键无效。
- 如果遇到 "SendInput failed" 或错误 5，请尝试以管理员身份运行本程序，或确保目标窗口未以更高权限运行。程序会回退到旧版 `keybd_event`，但在高完整性窗口中仍可能失败。
- 如果需要在多显示器或高 DPI 环境下使用，程序已调用 `SetProcessDPIAware`，如仍出现缩放问题，可尝试在可执行文件属性中手动设置高 DPI 覆盖选项。

更多开发笔记与后续扩展方向请参见 [`AGENTS.md`](AGENTS.md)。
