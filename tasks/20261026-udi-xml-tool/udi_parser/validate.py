"""单人校验：对单个文件做内部一致性检查。"""

from .models import BillDoc, Issue, RelationDoc

LEVEL_ERROR = "错误"
LEVEL_WARN = "警告"
LEVEL_INFO = "提示"


def validate_bill(doc: BillDoc, products=None, corps=None):
    """销售出库单校验。

    products / corps 是主数据索引。传了就额外检查 DI码 / 机构编码 是否登记过，
    没登记记「提示」级 —— 它不影响出单，只是提醒去补主数据。
    """
    issues = []

    # M_PRODUCT_NOT_FOUND：DI码 在产品主数据里查不到
    if products is not None:
        reported = set()
        for ln in doc.lines:
            di = ln.product_code
            if di in reported:
                continue
            if not di:
                reported.add(di)
                issues.append(Issue(
                    rule="M_PRODUCT_NOT_FOUND", level=LEVEL_INFO,
                    location=f"第 {ln.seq} 条",
                    message="明细没有 DI码，无法匹配成品名称和规格",
                ))
                continue
            if di not in products:
                reported.add(di)
                issues.append(Issue(
                    rule="M_PRODUCT_NOT_FOUND", level=LEVEL_INFO,
                    location=f"DI码 {di}",
                    message=f"DI码 {di} 未在「产品主数据」中登记，成品名称/规格留空",
                ))

    # M_CORP_NOT_FOUND：法人编码在法人主数据里查不到
    if corps is not None:
        for field, label in (("owner_corp_id", "供货者"), ("to_corp_id", "客户名称")):
            reported = set()
            for ln in doc.lines:
                code = getattr(ln, field)
                if not code or code in reported:
                    continue
                if code not in corps:
                    reported.add(code)
                    issues.append(Issue(
                        rule="M_CORP_NOT_FOUND", level=LEVEL_INFO,
                        location=f"第 {ln.seq} 条",
                        message=f"{label}编码 {code} 未在「法人主数据」中登记，名称留空",
                    ))

    # A_DUP_CODE：同单内码重复
    seen = {}
    for ln in doc.lines:
        seen.setdefault(ln.code, []).append(ln.seq)
    for code, seqs in seen.items():
        if len(seqs) > 1:
            issues.append(Issue(
                rule="A_DUP_CODE", level=LEVEL_ERROR,
                location=f"第 {', '.join(map(str, seqs))} 条",
                message=f"UDI 码重复：{code}",
            ))

    # 码格式：30 位
    for ln in doc.lines:
        if len(ln.code) != 30 or not ln.code.isdigit():
            issues.append(Issue(
                rule="A_CODE_FORMAT", level=LEVEL_WARN,
                location=f"第 {ln.seq} 条",
                message=f"码不是 30 位纯数字：{ln.code!r}（长度 {len(ln.code)}）",
            ))

    if not doc.lines:
        issues.append(Issue(rule="A_NO_LINES", level=LEVEL_ERROR, location="全文", message="文件内没有任何明细"))

    return issues


def validate_relation(doc: RelationDoc):
    """生产入库单校验。"""
    issues = []

    # B_DUP_CODE：整码重复
    seen = {}
    for g in doc.groups:
        for c in g.all_codes:
            seen.setdefault(c.cur_code, []).append(c.seq_in_file)
    for code, seqs in seen.items():
        if len(seqs) > 1:
            issues.append(Issue(
                rule="B_DUP_CODE", level=LEVEL_ERROR,
                location=f"第 {', '.join(map(str, seqs))} 条",
                message=f"码重复出现 {len(seqs)} 次：{code}",
            ))

    # B_PARENT_MISMATCH：盒码的 parent 必须等于所在箱块的箱码
    for g in doc.groups:
        for box_no, box in enumerate(g.boxes, 1):
            for item_no, c in enumerate(box.items, 1):
                if c.parent_code != box.box_code:
                    issues.append(Issue(
                        rule="B_PARENT_MISMATCH", level=LEVEL_ERROR,
                        location=f"第{g.relation_index}组第{g.batch_index}批 箱{box_no} 第{item_no}盒（文件第{c.seq_in_file}条）",
                        message=f"parentCode={c.parent_code or '(空)'}，与当前箱码 {box.box_code or '(空)'} 不一致",
                    ))

    # B_LEADING_ITEM：盒码先于任何箱码出现
    for g in doc.groups:
        for box_no, box in enumerate(g.boxes, 1):
            if not box.box_code:
                issues.append(Issue(
                    rule="B_LEADING_ITEM", level=LEVEL_ERROR,
                    location=f"第{g.relation_index}组第{g.batch_index}批 块{box_no}",
                    message=f"有 {box.box_count} 个盒码出现在任何箱码之前（文件第{box.start_seq}~{box.end_seq}条）",
                ))

    # B_EMPTY_BOX：箱码下无盒码
    for g in doc.groups:
        for box_no, box in enumerate(g.boxes, 1):
            if box.box_code and box.box_count == 0:
                issues.append(Issue(
                    rule="B_EMPTY_BOX", level=LEVEL_WARN,
                    location=f"第{g.relation_index}组第{g.batch_index}批 箱{box_no}",
                    message=f"箱码 {box.box_code} 下没有任何盒码",
                ))

    # B_ORPHAN_PARENT：parent 指向不存在的箱码
    box_codes = {b.box_code for g in doc.groups for b in g.boxes if b.box_code}
    for g in doc.groups:
        for c in g.all_codes:
            if c.pack_layer == "1" and c.parent_code and c.parent_code not in box_codes:
                issues.append(Issue(
                    rule="B_ORPHAN_PARENT", level=LEVEL_ERROR,
                    location=f"文件第{c.seq_in_file}条",
                    message=f"parentCode {c.parent_code} 在整个文件中找不到对应箱码",
                ))

    # B_CASCADE_INFO：cascade 比例与实际装箱数不符（仅提示）
    for g in doc.groups:
        cascade = (g.relation.cascade or "").strip()
        if ":" not in cascade:
            continue
        try:
            ratio = int(cascade.split(":")[1])
        except (ValueError, IndexError):
            continue
        counts = sorted({b.box_count for b in g.boxes if b.box_count})
        if ratio and counts and any(c != ratio for c in counts):
            actual = "、".join(str(c) for c in counts)
            issues.append(Issue(
                rule="B_CASCADE_INFO", level=LEVEL_INFO,
                location=f"第{g.relation_index}组第{g.batch_index}批",
                message=f"cascade 标称每箱 {ratio}，实际每箱盒数为 {actual}；本项不参与任何计算，仅供参考",
            ))

    # 码格式：30 位
    for g in doc.groups:
        for c in g.all_codes:
            if len(c.cur_code) != 30 or not c.cur_code.isdigit():
                issues.append(Issue(
                    rule="B_CODE_FORMAT", level=LEVEL_WARN,
                    location=f"文件第{c.seq_in_file}条",
                    message=f"码不是 30 位纯数字：{c.cur_code!r}（长度 {len(c.cur_code)}）",
                ))

    if not doc.code_total:
        issues.append(Issue(rule="B_NO_CODES", level=LEVEL_ERROR, location="全文", message="文件内没有任何码"))

    return issues
