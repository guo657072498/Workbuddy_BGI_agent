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

REM ============================================================
REM  版本号：升版时改这一行。
REM  规则见项目根目录 AGENTS.md 的「交付物版本管理」
REM  主版本=输出格式不兼容 / 次版本=新增能力 / 修订=只修 bug
REM  产出后记得在 VERSIONS.md 追加一行，并把旧版留在 releases\
REM ============================================================
set VER=v2.0.0

echo 正在清理旧产物...
if exist build rmdir /s /q build

REM PyInstaller 按 spec 产出不带版本号的名字，打完再改名。
REM 注意：绝不静默覆盖 dist 里已有的 exe —— 先归档再替换。
if not exist releases mkdir releases

echo.
echo 正在打包 %VER%（约需 1 分钟）...
%PY% -m PyInstaller --noconfirm --clean udi_tool.spec

if errorlevel 1 (
    echo.
    echo [失败] 打包出错，请查看上面的信息
    pause
    exit /b 1
)

if not exist "dist\UDI转换工具.exe" (
    echo [失败] 没有生成 exe
    pause
    exit /b 1
)

set TARGET=dist\UDI转换工具-%VER%.exe

REM 目标已存在 = 同版本号要产出不同内容，视为违规，直接停下
if exist "%TARGET%" (
    echo.
    echo [中止] %TARGET% 已存在。
    echo        同一版本号不允许对应两份不同的文件，请先把 VER 改成新的版本号。
    del /q "dist\UDI转换工具.exe"
    pause
    exit /b 1
)

REM 把 dist 里其余待版本的旧 exe 先归档（带旧版本号），再删掉裸名文件
for %%F in ("dist\UDI转换工具-v*.exe") do (
    if not exist "releases\%%~nxF" (
        echo 归档旧版：%%~nxF -^> releases\
        copy /y "dist\%%~nxF" "releases\%%~nxF" >nul
    )
    del /q "dist\%%~nxF"
)

move /y "dist\UDI转换工具.exe" "%TARGET%" >nul

echo.
echo [成功] 产物：%TARGET%
for %%A in ("%TARGET%") do echo        大小：%%~zA 字节
echo.
echo 这是单个 exe 文件，可直接发给用户，无需安装、无需 Python。
echo.
echo [待办] 1. 往 releases\ 放一份 %VER%
echo        2. 在 VERSIONS.md 追加一行
echo        3. 更新 README.md 的交付物路径
copy /y "%TARGET%" "releases\" >nul
echo        已自动完成第 1 步。

echo.
echo 正在用 samples 做自检...
if exist "dist\_selftest" rmdir /s /q "dist\_selftest"
set UDI_SELFTEST=%~dp0dist\_selftest
set UDI_SELFTEST_IN=%~dp0samples\销售出库单_样例.xml;%~dp0samples\销售出库单_无DN号.xml;%~dp0samples\生产入库单_样例.xml
"%~dp0%TARGET%"

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
