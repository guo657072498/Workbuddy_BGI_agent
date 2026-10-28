"""主数据：产品（DI码 → 成品名称/规格）与法人（机构编码 → 机构名称）。

存储为一个 Excel 文件，用户可以直接用 Excel 打开查看和修改。
运行时位置：exe（或源码）同目录的 `主数据\\` 下。
内置种子：打包时随 exe 带一份，首次启动自动写入磁盘，之后绝不覆盖。

显式 import 所有子模块，避免 PyInstaller 漏收（同 udi_parser/__init__.py 的做法）。
"""

from . import importing, store  # noqa: F401
from .store import (  # noqa: F401
    KIND_CORP,
    KIND_PRODUCT,
    CorpIndex,
    MasterDataError,
    ProductIndex,
    data_dir,
    ensure_seeded,
    load_indexes,
    load_rows,
    save_rows,
)

__all__ = [
    "importing",
    "store",
    "KIND_PRODUCT",
    "KIND_CORP",
    "ProductIndex",
    "CorpIndex",
    "MasterDataError",
    "data_dir",
    "ensure_seeded",
    "load_indexes",
    "load_rows",
    "save_rows",
]

# dialog 只在有图形界面时才导入（打包时由 spec 的 hiddenimports 显式收集）
try:
    from . import dialog  # noqa: F401
    from .dialog import MasterDataWindow  # noqa: F401
    __all__.append("dialog")
except Exception:  # pragma: no cover - 无 tkinter 环境（如纯命令行）
    dialog = None
    MasterDataWindow = None
