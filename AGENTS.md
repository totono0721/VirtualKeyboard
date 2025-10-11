# Development Notes

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
