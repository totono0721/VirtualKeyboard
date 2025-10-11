@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
pushd "%SCRIPT_DIR%" >nul

where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] 未检测到可用的 Python 解释器，请先安装 Python 3.10 或更高版本。
    popd >nul
    endlocal
    exit /b 1
)

set "VENV_DIR=%SCRIPT_DIR%.venv"

if not exist "%VENV_DIR%\Scripts\python.exe" (
    echo [INFO] 正在创建虚拟环境: %VENV_DIR%
    python -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo [ERROR] 虚拟环境创建失败。
        popd >nul
        endlocal
        exit /b 1
    )
) else (
    echo [INFO] 已检测到虚拟环境，跳过创建步骤。
)

call "%VENV_DIR%\Scripts\activate.bat"
if errorlevel 1 (
    echo [ERROR] 虚拟环境激活失败。
    popd >nul
    endlocal
    exit /b 1
)

echo [INFO] 正在更新 pip...
python -m pip install --upgrade pip
if errorlevel 1 goto :pip_fail

echo [INFO] 正在安装依赖...
python -m pip install -r requirements.txt
if errorlevel 1 goto :pip_fail

echo [INFO] 依赖安装完成。
popd >nul
endlocal
exit /b 0

:pip_fail
echo [ERROR] 依赖安装失败，请检查上方日志。
popd >nul
endlocal
exit /b 1
