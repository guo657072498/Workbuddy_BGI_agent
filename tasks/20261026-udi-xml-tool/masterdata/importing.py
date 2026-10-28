"""主数据 Excel 导入：表头模糊匹配 + 逐行校验 + 冲突比对。

**唯一需要按真实模板修改的地方是下面的 COLUMN_ALIASES**。
表头匹配做了全角→半角、去空格、去括号归一，模板里写「DI 码」「规格（型号）」
都能对上「DI码」「规格(型号)」。
"""

import re

from . import store

# ---------------------------------------------------------------- 表头别名
#
# 下面两套别名对应你提供的真实模板：
#   产品：《（模版）武汉生科-UDI信息对应-202610.xlsx》
#         最小销售单元产品标识（UDI） / 大箱标识 / SAP编码 / 产品名称/通用名称 /
#         规格型号 / 特殊储存或操作条件 / 分类
#   法人：《（模版）法人编码.xlsx》 法人编码 / 法人名称
# 匹配时做了全角→半角、去空格归一，所以「最小销售单元产品标识(UDI)」
# 和「最小销售单元产品标识 （UDI） 」都能对上。

COLUMN_ALIASES = {
    store.KIND_PRODUCT: {
        "di_code": [
            "最小销售单元产品标识(UDI)", "最小销售单元产品标识", "DI码", "DI",
            "产品DI码", "产品标识", "产品编码", "UDI",
        ],
        "box_code":     ["大箱标识", "箱码标识", "大箱码"],
        "sap_code":     ["SAP编码", "SAP码", "物料编码"],
        "prod_name":    ["产品名称/通用名称", "产品名称", "通用名称", "成品名称", "名称"],
        "spec":         ["规格型号", "规格(型号)", "规格", "型号"],
        "storage_cond": ["特殊储存或操作条件", "储存条件", "存储条件"],
        "category":     ["分类", "产品分类", "类别"],
    },
    store.KIND_CORP: {
        "corp_code": ["法人编码", "法人代码", "机构编码", "机构代码", "编码", "代码"],
        "corp_name": ["法人名称", "法人描述", "机构名称", "名称"],
    },
}

# 必填字段：缺了就不让导入。其余列缺了只留空，不阻塞。
REQUIRED_KEYS = {
    store.KIND_PRODUCT: ["di_code", "prod_name"],
    store.KIND_CORP: ["corp_code", "corp_name"],
}

_FULLWIDTH = {
    "（": "(", "）": ")", "，": ",", "：": ":", "　": " ",
    "／": "/", "＼": "\\", "－": "-", "—": "-", "＿": "_",
}


def norm_header(text):
    """表头归一：全角转半角、去掉所有空白、转小写。"""
    s = str(text or "")
    for k, v in _FULLWIDTH.items():
        s = s.replace(k, v)
    s = re.sub(r"\s+", "", s)
    return s.lower()


def _keys_of(kind):
    return list(COLUMN_ALIASES[kind].keys())


def match_headers(header_row, kind):
    """把 Excel 实际表头映射到字段 key。

    返回 (mapping, missing)。mapping = {field_key: 列索引}；
    missing 是没匹配上的必填字段中文说明（空列表表示全部匹配上）。
    """
    aliases = COLUMN_ALIASES[kind]
    normed = [norm_header(h) for h in header_row]
    mapping = {}
    for field_key, names in aliases.items():
        wanted = [n for n in (norm_header(x) for x in names) if n]
        # 先精确匹配，再包含匹配（近似表头，如多了「（必填）」之类后缀）
        hit = None
        for i, h in enumerate(normed):
            if h and h in wanted:
                hit = i
                break
        if hit is None:
            for i, h in enumerate(normed):
                if h and any(w and (w in h or h in w) for w in wanted):
                    hit = i
                    break
        if hit is not None:
            mapping[field_key] = hit

    missing = [_label(kind, k) for k in REQUIRED_KEYS[kind] if k not in mapping]
    return mapping, missing


_LABELS = {
    store.KIND_PRODUCT: {
        "di_code": "最小销售单元产品标识（UDI）", "box_code": "大箱标识",
        "sap_code": "SAP编码", "prod_name": "产品名称/通用名称",
        "spec": "规格型号", "storage_cond": "特殊储存或操作条件",
        "category": "分类",
    },
    store.KIND_CORP: {"corp_code": "法人编码", "corp_name": "法人名称"},
}


def _label(kind, key):
    return _LABELS[kind].get(key, key)


# ---------------------------------------------------------------- 读 + 比对

def read_sheet(path, kind):
    """读 Excel 第一个工作表，返回 (rows, mapping, missing, 表头原文)。

    rows 是 [{field: value}]，已按映射取值，空主键的行被跳过。
    """
    try:
        import openpyxl
    except ImportError as e:
        raise store.MasterDataError("缺少 openpyxl，无法读取 Excel。请先安装：pip install openpyxl") from e

    if str(path).lower().endswith(".xls"):
        raise store.MasterDataError("不支持 .xls 旧格式，请在 Excel 里另存为 .xlsx 后再上传。")
    try:
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    except Exception as e:
        raise store.MasterDataError(f"打开 Excel 失败：{e}") from e

    try:
        ws = wb.worksheets[0]
        it = ws.iter_rows(values_only=True)
        try:
            header = next(it)
        except StopIteration:
            raise store.MasterDataError("Excel 是空的，没有表头。") from None

        mapping, missing = match_headers(header, kind)
        if missing:
            return [], mapping, missing, header

        pk_field = _keys_of_plan(kind)[0]
        rows = []
        for row in it:
            rec = {}
            for field, idx in mapping.items():
                v = row[idx] if idx < len(row) else None
                rec[field] = store._cell(v)
            if not rec.get(pk_field):
                continue
            rows.append(rec)
        return rows, mapping, [], header
    finally:
        wb.close()


def _keys_of_plan(kind):
    """按列定义顺序返回字段 key（第 0 个就是主键）。"""
    return [c[0] for c in store.column_defs(kind)]


def compare(kind, new_rows, existing_rows):
    """把待导入行和现有数据比对。

    返回 dict:
        to_add     —— 新增行
        conflicts  —— (旧行, 新行, 差异字段列表)
        same       —— 完全相同、跳过的行数
        dup_in_file —— 导入文件里主键重复的次数
    """
    pk = _keys_of_plan(kind)[0]
    fields = _keys_of_plan(kind)

    existing = {}
    for r in existing_rows:
        existing[r.get(pk, "")] = r

    to_add, conflicts, same = [], [], 0
    seen = set()
    dup_in_file = 0

    for r in new_rows:
        key = r.get(pk, "")
        if key in seen:
            dup_in_file += 1
        seen.add(key)

        old = existing.get(key)
        if old is None:
            to_add.append(r)
            continue
        diff = [f for f in fields if (old.get(f, "") or "") != (r.get(f, "") or "")]
        if diff:
            conflicts.append((old, r, diff))
        else:
            same += 1

    return {
        "to_add": to_add,
        "conflicts": conflicts,
        "same": same,
        "dup_in_file": dup_in_file,
    }


def merge(kind, existing_rows, result, overwrite=False):
    """把比对结果合并成最终行列表。"""
    pk = _keys_of_plan(kind)[0]
    by_key = {r.get(pk, ""): dict(r) for r in existing_rows}

    for r in result["to_add"]:
        by_key[r[pk]] = dict(r)

    if overwrite:
        for _old, new, _diff in result["conflicts"]:
            by_key[new[pk]] = dict(new)

    # 主键排序，让表格稳定
    return sorted(by_key.values(), key=lambda r: r.get(pk, ""))
