@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
pushd "%SCRIPT_DIR%" >nul

set "VENV_DIR=%SCRIPT_DIR%.venv"

if not exist "%VENV_DIR%\Scripts\python.exe" (
    echo [INFO] 未检测到虚拟环境，正在执行 install.bat...
    call "%SCRIPT_DIR%install.bat"
    if errorlevel 1 (
        echo [ERROR] install.bat 执行失败，无法启动程序。
        popd >nul
        endlocal
        exit /b 1
    )
)

call "%VENV_DIR%\Scripts\activate.bat"
if errorlevel 1 (
    echo [ERROR] 虚拟环境激活失败。
    popd >nul
    endlocal
    exit /b 1
)

python virtual_keyboard.py %*
set "EXIT_CODE=%ERRORLEVEL%"

popd >nul
endlocal
exit /b %EXIT_CODE%
