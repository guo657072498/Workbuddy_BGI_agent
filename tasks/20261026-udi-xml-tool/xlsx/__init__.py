"""Excel 写出与自检。"""

from .writer import write_workbook, write_openpyxl, write_stdlib, _coerce, TEXT
from .verify import verify_file, VerifyResult
