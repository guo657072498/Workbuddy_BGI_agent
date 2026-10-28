"""主数据的读写与查表。

设计要点：
1. 磁盘用 xlsx，用户可直接用 Excel 打开查看/修改，不需要额外工具。
2. 内置种子随 exe 打包，首次启动写入磁盘；磁盘已有数据时**绝不覆盖**。
3. 批量转换只读一次盘，逐行查内存字典。
4. 读 xlsx 依赖 openpyxl（零依赖写出通道只能写不能读），缺失时要明确报错，
   不能让转换"成功"但输出一堆空名称。
"""

import os
import shutil
import sys

from config import columns as C

KIND_PRODUCT = "product"   # DI码 → 成品名称 / 规格
KIND_CORP = "corp"         # 机构编码 → 机构名称

_SEED_FILES = {
    KIND_PRODUCT: "products.xlsx",
    KIND_CORP: "corps.xlsx",
}
_DATA_FILES = {
    KIND_PRODUCT: "产品主数据.xlsx",
    KIND_CORP: "法人主数据.xlsx",
}
_SHEET_NAMES = {
    KIND_PRODUCT: "产品主数据",
    KIND_CORP: "法人主数据",
}
_COLUMNS = {
    KIND_PRODUCT: lambda: C.MASTER_PRODUCT_COLUMNS,
    KIND_CORP: lambda: C.MASTER_CORP_COLUMNS,
}
TITLES = {
    KIND_PRODUCT: "产品主数据",
    KIND_CORP: "法人主数据",
}


class MasterDataError(Exception):
    """主数据读写失败。"""


# ---------------------------------------------------------------- 路径

def _frozen():
    return getattr(sys, "frozen", False)


def app_dir():
    """exe 所在目录（冻结）或项目根目录（源码运行）。"""
    if _frozen():
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def data_dir():
    """运行时主数据目录：<app_dir>/主数据。"""
    return os.path.join(app_dir(), "主数据")


def _seed_dir():
    """内置种子所在目录。"""
    if _frozen():
        return os.path.join(getattr(sys, "_MEIPASS", app_dir()), "data", "masterdata")
    return os.path.join(app_dir(), "data", "masterdata")


def data_path(kind):
    return os.path.join(data_dir(), _DATA_FILES[kind])


def column_defs(kind):
    """该主数据的列定义 [(字段名, 表头, 类型, 宽度)]，第 0 个是主键。"""
    return _COLUMNS[kind]()


def headers(kind):
    return [c[1] for c in column_defs(kind)]


# ---------------------------------------------------------------- 读写

def _require_openpyxl():
    try:
        import openpyxl  # noqa: F401
    except ImportError as e:  # pragma: no cover - 打包后才会发生
        raise MasterDataError(
            "缺少 openpyxl，无法读取主数据。"
            "成品名称/规格/供货者/客户名称将无法填充。请先安装：pip install openpyxl"
        ) from e


def _cell(v):
    """单元格值转干净字符串。整数型浮点（如 1.0）去掉小数点。"""
    if v is None:
        return ""
    if isinstance(v, float) and v == int(v):
        return str(int(v))
    return str(v).strip()


def load_rows(kind, path=None):
    """读一张主数据表，返回 [{field: value}] 列表。文件不存在返回 []。"""
    _require_openpyxl()
    import openpyxl

    path = path or data_path(kind)
    if not os.path.isfile(path):
        return []
    cols = _COLUMNS[kind]()
    try:
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    except Exception as e:
        raise MasterDataError(f"打开 {os.path.basename(path)} 失败：{e}") from e
    try:
        ws = wb[_SHEET_NAMES[kind]] if _SHEET_NAMES[kind] in wb.sheetnames else wb.worksheets[0]
        rows = []
        for i, row in enumerate(ws.iter_rows(min_row=2, values_only=True), 2):
            if row is None:
                continue
            rec = {}
            for j, col in enumerate(cols):
                rec[col[0]] = _cell(row[j]) if j < len(row) else ""
            if not rec.get(cols[0][0]):
                continue          # 主键为空的行直接跳过
            rows.append(rec)
        return rows
    finally:
        wb.close()


def save_rows(kind, rows):
    """整表写回磁盘（先写临时文件再替换，避免写一半断电把数据弄坏）。"""
    _require_openpyxl()
    import openpyxl
    from openpyxl.styles import Font, PatternFill

    d = data_dir()
    os.makedirs(d, exist_ok=True)
    cols = _COLUMNS[kind]()
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = _SHEET_NAMES[kind]

    ws.append([c[1] for c in cols])
    head_font = Font(bold=True, color="FFFFFF")
    head_fill = PatternFill("solid", fgColor="3B5BA5")
    for j, col in enumerate(cols, 1):
        cell = ws.cell(row=1, column=j)
        cell.font = head_font
        cell.fill = head_fill
        ws.column_dimensions[cell.column_letter].width = col[3] or 16

    for r in rows:
        ws.append([r.get(c[0], "") or "" for c in cols])

    # 主键列设为文本格式，避免纯数字编码被 Excel 转成数值
    pk_col = cols[0][0]
    col_idx = [c[0] for c in cols].index(pk_col) + 1
    for row in ws.iter_rows(min_row=2, min_col=col_idx, max_col=col_idx):
        for cell in row:
            cell.number_format = "@"

    target = data_path(kind)
    tmp = target + ".tmp"
    try:
        wb.save(tmp)
        os.replace(tmp, target)
    except Exception as e:
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except OSError:
            pass
        raise MasterDataError(f"保存 {os.path.basename(target)} 失败：{e}") from e


# ---------------------------------------------------------------- 种子

def _seed_path(kind):
    return os.path.join(_seed_dir(), _SEED_FILES[kind])


def missing_seed_files():
    """内置种子是否齐全。打包配置漏了会在这里暴露。"""
    return [k for k in _SEED_FILES if not os.path.isfile(_seed_path(k))]


def ensure_seeded(force=False):
    """磁盘上没有主数据时，从内置种子写一份。

    返回 {kind: "created" | "kept" | "no_seed"}。
    **已有数据绝不覆盖** —— 用户可能在工具里改了上百条。
    """
    os.makedirs(data_dir(), exist_ok=True)
    result = {}
    for kind in _SEED_FILES:
        target = data_path(kind)
        if not force and os.path.isfile(target):
            result[kind] = "kept"
            continue
        seed = _seed_path(kind)
        if not os.path.isfile(seed):
            result[kind] = "no_seed"
            continue
        try:
            shutil.copyfile(seed, target)
            result[kind] = "created"
        except Exception as e:
            raise MasterDataError(f"初始化 {_DATA_FILES[kind]} 失败：{e}") from e
    return result


def seed_diff(kind):
    """对比内置种子与磁盘：返回只在种子里有的 {key: row}。

    用于「换新版 exe 后有新增内置数据」的合并提示。磁盘已有的 key 一律不返回。
    """
    seed = _seed_path(kind)
    if not os.path.isfile(seed):
        return {}
    try:
        seed_rows = load_rows(kind, path=seed)
    except MasterDataError:
        return {}
    if not seed_rows:
        return {}

    pk = _COLUMNS[kind]()[0][0]
    return {r[pk]: r for r in seed_rows if r[pk]}


# ---------------------------------------------------------------- 查表

class _Index:
    """只读索引：主键 → 行。"""

    _kind = ""

    def __init__(self, rows=None):
        self._rows = {}
        self.duplicates = 0
        pk = _COLUMNS[self._kind]()[0][0]
        for r in rows or []:
            key = r.get(pk, "")
            if not key:
                continue
            if key in self._rows:
                self.duplicates += 1
            self._rows[key] = r

    def __len__(self):
        return len(self._rows)

    def __contains__(self, key):
        return bool(key) and key in self._rows

    def get(self, key):
        return self._rows.get(key or "")

    def keys(self):
        return self._rows.keys()


class ProductIndex(_Index):
    """DI码 → (成品名称, 规格)。"""
    _kind = KIND_PRODUCT

    def lookup(self, di_code):
        r = self.get(di_code)
        if not r:
            return "", ""
        return r.get("prod_name", ""), r.get("spec", "")


class CorpIndex(_Index):
    """机构编码 → 机构名称。"""
    _kind = KIND_CORP

    def lookup(self, code):
        r = self.get(code)
        return r.get("corp_name", "") if r else ""


def load_indexes():
    """一次读盘，返回 (ProductIndex, CorpIndex) 与读取错误列表。

    出错时不抛异常，返回空索引 + 错误说明，让转换能给出明确提示而不是整体崩掉。
    """
    errors = []
    try:
        ensure_seeded()
    except MasterDataError as e:
        errors.append(str(e))
    try:
        products = ProductIndex(load_rows(KIND_PRODUCT))
    except MasterDataError as e:
        errors.append(str(e))
        products = ProductIndex()
    try:
        corps = CorpIndex(load_rows(KIND_CORP))
    except MasterDataError as e:
        errors.append(str(e))
        corps = CorpIndex()
    return products, corps, errors
