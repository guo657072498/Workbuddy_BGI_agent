# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置：单文件、无控制台窗口、全量收集本项目模块。"""

import os

block_cipher = None

# 本项目所有模块显式列出，避免 PyInstaller 漏收（此前漏了 udi_parser.source）
PROJECT_MODULES = [
    "converter",
    "config.columns",
    "masterdata.store",
    "masterdata.importing",
    "masterdata.dialog",
    "udi_parser.models",
    "udi_parser.detect",
    "udi_parser.source",
    "udi_parser.parse_bill",
    "udi_parser.parse_relation",
    "udi_parser.flatten",
    "udi_parser.validate",
    "udi_parser.crosscheck",
    "xlsx.writer",
    "xlsx.verify",
]

EXCLUDES = [
    "PIL", "matplotlib", "numpy", "pandas", "lxml", "scipy", "pytest",
    "setuptools", "pip", "wheel", "IPython", "notebook", "jupyter",
    "sqlite3", "pydoc_data", "unittest", "pdb", "doctest",
]

# 主数据内置种子：首次启动时写到 exe 同目录的「主数据」下
# 注意：Analysis(datas=...) 的 2 元组顺序是 (源文件, 目标目录)，且目标目录
#       末尾要带斜杠，否则 PyInstaller 会拼成 "...xlsx\products.xlsx" 这种坏路径。
#       a.datas.append(...) 才是 (目标路径, 源路径, "DATA") 三元组。两者不能混。
_SEED_FILES = ["data/masterdata/products.xlsx", "data/masterdata/corps.xlsx"]
_DATAS = []
for _src in _SEED_FILES:
    if not os.path.isfile(_src):
        raise SystemExit(f"[打包中止] 缺少内置主数据种子：{_src}")
    _DATAS.append((_src, "data/masterdata/"))

a = Analysis(
    ["gui.py"],
    pathex=[],
    binaries=[],
    datas=_DATAS,
    hiddenimports=PROJECT_MODULES,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=EXCLUDES,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# 把 tkinterdnd2 自带的 tkdnd 二进制和 tcl 脚本收进来（拖拽功能依赖）
# 注意：PyInstaller 6.x 的 datas 需要 3 元组 (目标目录, 源路径, 类型)
try:
    import tkinterdnd2
    _dnd_dir = os.path.dirname(tkinterdnd2.__file__)
    for _root, _dirs, _files in os.walk(_dnd_dir):
        for _f in _files:
            if _f.endswith((".py", ".pyc")):
                continue
            _src = os.path.join(_root, _f)
            _rel = os.path.relpath(_root, os.path.dirname(_dnd_dir))
            a.datas.append((os.path.join(_rel, _f), _src, "DATA"))
except Exception as _e:
    print("收集 tkinterdnd2 失败：", _e)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="UDI转换工具",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
