"""UDI XML 解析包。

这里显式导入子模块，一是提供统一入口，
二是让 PyInstaller 把这个包当成常规包（而非命名空间包）来收集子模块，
否则打包后会出现 No module named 'udi_parser.source' 的错误。
"""

from . import models, detect, source, parse_bill, parse_relation, flatten, validate, crosscheck

__all__ = [
    "models",
    "detect",
    "source",
    "parse_bill",
    "parse_relation",
    "flatten",
    "validate",
    "crosscheck",
]
