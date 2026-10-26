"""跨文件校验：出入库明细码 → 生产入库单的箱码归属。

规则「有则填、无则空」：找不到父箱只记提示，不报错。
"""

from .models import BillDoc, Issue, RelationDoc
from .validate import LEVEL_INFO


def build_code_index(rel_docs):
    """建立 盒码 -> (箱码, 批次号, 工单号) 索引。"""
    index = {}
    for doc in rel_docs:
        for g in doc.groups:
            for box in g.boxes:
                for c in box.items:
                    index[c.cur_code] = {
                        "box_code": box.box_code,
                        "batch_no": g.batch.batch_no,
                        "work_order": g.batch.work_order,
                        "product_code": g.relation.product_code,
                        "source": doc.file_name,
                    }
    return index


def crosscheck(bill_docs, rel_docs):
    """返回 (每个明细码的归属字典, 提示列表)。"""
    index = build_code_index(rel_docs)
    mapping = {}
    issues = []

    if not rel_docs:
        return mapping, issues

    for doc in bill_docs:
        for ln in doc.lines:
            hit = index.get(ln.code)
            if hit:
                mapping[ln.code] = hit
            else:
                issues.append(Issue(
                    rule="X_NO_LINK", level=LEVEL_INFO,
                    location=f"{doc.file_name} 第{ln.seq}条",
                    message=f"码 {ln.code} 在已提供的生产入库单中找不到所属箱码（可能入库单未提供，或跨产品）",
                ))
    return mapping, issues
