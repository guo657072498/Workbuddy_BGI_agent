"""文件 B 解析：关联关系 XML（生产入库单）。

结构：Document/Events/Event/Relation/Batch/Code

码的排列约定（实测 100% 成立）：
    先出现箱码（packLayer=2），紧随其后的是该箱内的盒码（packLayer=1），
    盒码的 parentCode 指向当前箱码。

因此按 XML 原始顺序扫描切块，不靠流水号推箱内成员（实测箱1/箱2 流水重叠）。
不假设箱数、每箱数量、cascade 比例。
"""

import os

from . import detect
from .models import BatchInfo, BoxBlock, CodeNode, RelationBatch, RelationDoc, RelationInfo


def _f(v, default=""):
    return default if v is None else str(v).strip()


def _display_name(path):
    """从输入取一个可展示的名字。"""
    if hasattr(path, "display_name"):
        return os.path.basename(path.display_name)
    return os.path.basename(path)


def _parse_codes(batch_el, seq_start):
    """取出 Batch 下全部 Code，保持原始顺序，返回 (codes, 下一个可用序号)。"""
    codes = []
    seq = seq_start
    for el in batch_el.findall("Code"):
        a = el.attrib
        seq += 1
        codes.append(CodeNode(
            seq_in_file=seq,
            cur_code=_f(a.get("curCode")),
            pack_layer=_f(a.get("packLayer")),
            parent_code=_f(a.get("parentCode")),
            flag=_f(a.get("flag")),
            print_count=_f(a.get("printCount")),
            status=_f(a.get("status")),
        ))
    return codes, seq


def split_boxes(codes):
    """按顺序把码序列切成箱块。

    规则：遇到 packLayer==2 的箱码即开启新箱块；packLayer==1 的盒码归入当前箱块。
    若盒码出现在任何箱码之前（游离盒码），归入一个 box_code 为空的块。
    """
    blocks = []
    current = None
    for c in codes:
        if c.pack_layer == "2":
            current = BoxBlock(box_code=c.cur_code, start_seq=c.seq_in_file, end_seq=c.seq_in_file)
            blocks.append(current)
        elif c.pack_layer == "1":
            if current is None:
                # 游离盒码：单独成块，箱码留空
                current = BoxBlock(box_code="", start_seq=c.seq_in_file, end_seq=c.seq_in_file)
                blocks.append(current)
            current.items.append(c)
            current.end_seq = c.seq_in_file
        # 其他层级（如三层包装）不入箱块，但仍保留在 all_codes 中
    return blocks


def parse(path, file_name=None):
    """解析生产入库单 XML，返回 RelationDoc。

    path 可以是磁盘路径，也可以是 XmlSource（压缩包内的字节流）。
    file_name 用于指定展示/输出用的文件名（压缩包内文件必须传）。
    """
    root = detect.load_root(path)
    doc = RelationDoc(file_name=file_name or _display_name(path))
    doc.license = _f(root.get("License"))

    events_el = root.find("Events")
    if events_el is not None:
        doc.version = _f(events_el.get("version"))

    seq = 0
    rel_idx = 0
    for ev in root.findall("Events/Event"):
        if not doc.event_name:
            doc.event_name = _f(ev.get("name"))
        for rel in ev.findall("Relation"):
            rel_idx += 1
            a = rel.attrib
            rel_info = RelationInfo(
                product_code=_f(a.get("productCode")),
                sub_type_no=_f(a.get("subTypeNo")),
                cascade=_f(a.get("cascade")),
                package_spec=_f(a.get("packageSpec")),
                comment=_f(a.get("comment")) or _f(a.get("commentZh")),
            )
            batch_els = rel.findall("Batch")
            if not batch_els:
                # Relation 下没有 Batch：仍记录，避免丢数据
                doc.groups.append(RelationBatch(
                    relation_index=rel_idx, batch_index=1, relation=rel_info,
                ))
            for b_idx, b in enumerate(batch_els, 1):
                ba = b.attrib
                batch_info = BatchInfo(
                    batch_no=_f(ba.get("batchNo")),
                    made_date=_f(ba.get("madeDate")),
                    validate_date=_f(ba.get("validateDate")),
                    workshop=_f(ba.get("workshop")),
                    line_name=_f(ba.get("lineName")),
                    line_manager=_f(ba.get("lineManager")),
                    work_order=_f(ba.get("workOrder")),
                )
                codes, seq = _parse_codes(b, seq)
                doc.groups.append(RelationBatch(
                    relation_index=rel_idx,
                    batch_index=b_idx,
                    relation=rel_info,
                    batch=batch_info,
                    boxes=split_boxes(codes),
                    all_codes=codes,
                ))

    return doc
