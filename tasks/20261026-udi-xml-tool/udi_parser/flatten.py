"""扁平化：把解析结果整理成行（dict 列表），供 Excel 写出。

行内容的"取哪些字段"由 config/columns.py 决定；本模块只负责算出所有可用字段。
"""

from .models import BillDoc, RelationDoc


def _norm_date(s):
    """日期归一化：2024/7/5 0:00:00 -> 2024-07-05；已是 YYYY-MM-DD 的原样返回。"""
    s = (s or "").strip()
    if not s:
        return ""
    head = s.split(" ")[0]
    sep = "/" if "/" in head else "-" if "-" in head else None
    if not sep:
        return s
    parts = head.split(sep)
    if len(parts) != 3:
        return s
    try:
        y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
    except ValueError:
        return s
    return f"{y:04d}-{m:02d}-{d:02d}"


def code_part(code, start, end=None):
    """安全取码段：越界返回空串，绝不抛异常。"""
    if not isinstance(code, str):
        return ""
    return code[start:end] if end is not None else code[start:]


# ---------------------------------------------------------------- 文件 A

def bill_rows(doc: BillDoc):
    """出入库单 -> 明细行字段。"""
    h = doc.header
    declared = {p.code: p.amount for p in doc.products}
    unit_map = {p.code: p.pack_unit for p in doc.products}

    # 同一产品出现在多个明细里时，每个产品只填一次"声明数量"
    rows = []
    for ln in doc.lines:
        code = ln.code
        rows.append({
            "seq": ln.seq,
            "file": doc.file_name,
            "store_no": h.store_no,
            "doc_type": h.doc_type,
            "store_type": h.store_type,
            "direction": _direction(h),
            "bill_time": h.bill_time,
            "operate_date": h.operate_date,
            "act_date": ln.act_date,
            "product_code": ln.product_code,
            "code": code,
            "pack_flag": code_part(code, 16, 18),
            "serial": code_part(code, 18),
            "pack_unit": unit_map.get(ln.product_code, ""),
            "declared_amount": declared.get(ln.product_code, ""),
            "operator": ln.actor or h.operator,
            "owner_corp": ln.owner_corp_id,
            "to_corp": ln.to_corp_id,
            "corp_order": ln.corp_order_id,
            "wrong_code": ln.wrong_code,
            "ext1": ln.ext1, "ext2": ln.ext2, "ext3": ln.ext3,
            "ext4": ln.ext4, "ext5": ln.ext5,
            "event_name": h.event_name,
            "main_action": h.main_action,
            "remark": h.remark,
        })
    return rows


def _direction(h):
    """业务方向：根据 StoreType 判断。"""
    st = (h.store_type or "").lower()
    act = (h.main_action or "").lower()
    if "out" in st or "out" in act:
        return "出库"
    if "in" in st or "in" in act:
        return "入库"
    return ""


def bill_summary_rows(doc: BillDoc):
    """按产品汇总：声明量 vs 实际条数。"""
    actual = {}
    for ln in doc.lines:
        actual[ln.product_code] = actual.get(ln.product_code, 0) + 1
    rows = []
    for i, p in enumerate(doc.products, 1):
        act = actual.get(p.code, 0)
        diff = act - p.amount
        rows.append({
            "seq": i,
            "product_code": p.code,
            "pack_unit": p.pack_unit,
            "declared": p.amount,
            "actual": act,
            "diff": diff,
            "verdict": "一致" if diff == 0 else ("多 " + str(diff) if diff > 0 else "少 " + str(-diff)),
            "batch_no": p.batch_no,
            "has_codes": p.has_codes,
            "file": doc.file_name,
            "store_no": doc.header.store_no,
        })
    # 明细里出现但产品声明里没有的产品
    for code, act in actual.items():
        if not any(p.code == code for p in doc.products):
            rows.append({
                "seq": len(rows) + 1,
                "product_code": code,
                "pack_unit": "",
                "declared": 0,
                "actual": act,
                "diff": act,
                "verdict": "未声明",
                "batch_no": "",
                "has_codes": "",
                "file": doc.file_name,
                "store_no": doc.header.store_no,
            })
    return rows


# ---------------------------------------------------------------- 文件 B

def _group_ctx(g, box, box_no, item_no):
    """一组共用字段。"""
    r, b = g.relation, g.batch
    return {
        "relation_index": g.relation_index,
        "batch_index": g.batch_index,
        "product_code": r.product_code,
        "sub_type_no": r.sub_type_no,
        "cascade": r.cascade,
        "package_spec": r.package_spec,
        "batch_no": b.batch_no,
        "made_date": _norm_date(b.made_date),
        "validate_date": _norm_date(b.validate_date),
        "made_date_raw": b.made_date,
        "validate_date_raw": b.validate_date,
        "workshop": b.workshop,
        "line_name": b.line_name,
        "line_manager": b.line_manager,
        "work_order": b.work_order,
        "box_no": box_no,
        "item_no": item_no,
        "box_seq": box.start_seq if box else "",
    }


def box_item_rows(doc: RelationDoc):
    """每盒（单品）一行。"""
    rows = []
    n = 0
    for g in doc.groups:
        for box_no, box in enumerate(g.boxes, 1):
            for item_no, c in enumerate(box.items, 1):
                n += 1
                row = _group_ctx(g, box, box_no, item_no)
                row.update({
                    "seq": n,
                    "file": doc.file_name,
                    "box_code": box.box_code,
                    "code": c.cur_code,
                    "pack_flag": code_part(c.cur_code, 16, 18),
                    "serial": code_part(c.cur_code, 18),
                    "parent_code": c.parent_code,
                    "pack_layer": c.pack_layer,
                    "layer_name": _layer_name(c.pack_layer),
                    "flag": c.flag,
                    "status": c.status,
                    "print_count": c.print_count,
                    "seq_in_file": c.seq_in_file,
                })
                rows.append(row)
    return rows


def box_rows(doc: RelationDoc):
    """每箱一行。"""
    rows = []
    for g in doc.groups:
        for box_no, box in enumerate(g.boxes, 1):
            row = _group_ctx(g, box, box_no, "")
            serials = [int(code_part(c.cur_code, 18) or 0) for c in box.items]
            row.update({
                "seq": box_no,
                "file": doc.file_name,
                "box_code": box.box_code or "（无箱码）",
                "box_count": box.box_count,
                "start_seq": box.start_seq,
                "end_seq": box.end_seq,
                "serial_min": min(serials) if serials else "",
                "serial_max": max(serials) if serials else "",
                "first_code": box.items[0].cur_code if box.items else "",
                "last_code": box.items[-1].cur_code if box.items else "",
                "layer_name": "箱",
            })
            rows.append(row)
    return rows


def code_all_rows(doc: RelationDoc):
    """全量码清单（含箱码行）。"""
    rows = []
    for g in doc.groups:
        for c in g.all_codes:
            row = _group_ctx(g, None, "", "")
            row.pop("box_seq", None)
            row.update({
                "seq_in_file": c.seq_in_file,
                "file": doc.file_name,
                "code": c.cur_code,
                "pack_layer": c.pack_layer,
                "layer_name": _layer_name(c.pack_layer),
                "parent_code": c.parent_code,
                "pack_flag": code_part(c.cur_code, 16, 18),
                "serial": code_part(c.cur_code, 18),
                "is_box": "是" if c.pack_layer == "2" else "",
                "flag": c.flag,
                "status": c.status,
                "print_count": c.print_count,
            })
            rows.append(row)
    return rows


def _layer_name(layer):
    return {"1": "盒", "2": "箱", "3": "托"}.get(layer, f"未知({layer})")
