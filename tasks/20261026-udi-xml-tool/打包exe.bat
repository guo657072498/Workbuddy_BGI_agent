@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo ============================================
echo   打包 UDI XML 转 Excel 工具为免安装 exe
echo ============================================
echo.

REM 用带 tkinter 的 Python 3.14
set PY=py -3.14
%PY% -c "import tkinter" >nul 2>&1
if errorlevel 1 (
    echo [错误] 找不到带 tkinter 的 Python 3.14
    pause
    exit /b 1
)

for %%M in (pyinstaller tkinterdnd2) do (
    %PY% -c "import %%M" >nul 2>&1
    if errorlevel 1 (
        echo 正在安装 %%M ...
        %PY% -m pip install %%M
    )
)

echo 正在清理旧产物...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo.
echo 正在打包（约需 1 分钟）...
%PY% -m PyInstaller --noconfirm --clean udi_tool.spec

if errorlevel 1 (
    echo.
    echo [失败] 打包出错，请查看上面的信息
    pause
    exit /b 1
)

echo.
if exist "dist\UDI转换工具.exe" (
    echo [成功] 产物：dist\UDI转换工具.exe
    for %%A in ("dist\UDI转换工具.exe") do echo        大小：%%~zA 字节
    echo.
    echo 这是单个 exe 文件，可直接发给用户，无需安装、无需 Python。
) else (
    echo [失败] 没有生成 exe
)

echo.
pause
