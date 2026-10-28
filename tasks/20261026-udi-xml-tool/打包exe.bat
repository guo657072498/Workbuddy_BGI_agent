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

for %%M in (pyinstaller tkinterdnd2 openpyxl) do (
    %PY% -c "import %%M" >nul 2>&1
    if errorlevel 1 (
        echo 正在安装 %%M ...
        %PY% -m pip install %%M
    )
)

echo 正在清理旧产物...
if exist build rmdir /s /q build
REM 只删 exe，不删整个 dist —— dist 里还可能有用户跑出来的结果目录
if exist "dist\UDI转换工具.exe" del /q "dist\UDI转换工具.exe"

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
    pause
    exit /b 1
)

echo.
echo 正在用 samples 做自检...
if exist "dist\_selftest" rmdir /s /q "dist\_selftest"
set UDI_SELFTEST=%~dp0dist\_selftest
set UDI_SELFTEST_IN=%~dp0samples\销售出库单_样例.xml;%~dp0samples\销售出库单_无DN号.xml;%~dp0samples\生产入库单_样例.xml
"dist\UDI转换工具.exe"

if exist "dist\_selftest\_selftest.log" (
    echo.
    findstr /C:"[FAIL]" "dist\_selftest\_selftest.log" >nul 2>&1
    if errorlevel 1 (
        echo [自检通过] 详见 dist\_selftest\_selftest.log
    ) else (
        echo [自检失败] 请查看 dist\_selftest\_selftest.log
        type "dist\_selftest\_selftest.log"
    )
) else (
    echo [!] 没有生成自检日志，exe 可能没能启动，请手动双击试一次
)

echo.
pause
