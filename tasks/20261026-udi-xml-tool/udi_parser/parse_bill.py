"""文件 A 解析：终端接口 XML（出入库单）。

结构：Document/DocHeader + HasProducts/Product + Events/Event/DataField/Data
Data 每一条就是一个单品码明细，不携带箱级信息。
"""

import os

from . import detect
from .models import BillDoc, BillHeader, BillLine, BillProduct


def _f(v, default=""):
    return default if v is None else str(v).strip()


def _display_name(path):
    """从输入取一个可展示的名字。"""
    if hasattr(path, "display_name"):
        return os.path.basename(path.display_name)
    return os.path.basename(path)


def _num(v):
    """数量字段转数字，失败返回 0。"""
    s = _f(v)
    if not s:
        return 0
    try:
        n = float(s)
        return int(n) if n == int(n) else n
    except ValueError:
        return 0


def parse(path, file_name=None):
    """解析出入库单 XML，返回 BillDoc。

    path 可以是磁盘路径，也可以是 XmlSource（压缩包内的字节流）。
    file_name 用于指定展示/输出用的文件名（压缩包内文件必须传）。
    """
    root = detect.load_root(path)
    name = file_name or _display_name(path)
    doc = BillDoc(file_name=name)

    # ---- 单据头
    hdr = root.find("DocHeader")
    if hdr is not None:
        a = hdr.attrib
        doc.header = BillHeader(
            doc_owner=_f(a.get("DocOwner")),
            doc_type=_f(a.get("DocType")),
            store_type=_f(a.get("StoreType")),
            bill_time=_f(a.get("BillTime")),
            operator=_f(a.get("Operator")),
            remark=_f(a.get("Remark")),
            operate_date=_f(a.get("OperateDate")),
            doc_version=_f(a.get("DocVersion")),
            store_no=_f(a.get("StoreNo")),
            store_no_ext=_f(a.get("StoreNoExt")),
            customer_no=_f(a.get("CustomerNo")),
            corp_code=_f(a.get("CorpCode")),
            biz_corp_code=_f(a.get("BizCorpCode")),
        )

    # ---- 产品声明
    for p in root.findall("HasProducts/Product"):
        a = p.attrib
        doc.products.append(BillProduct(
            code=_f(a.get("Code")),
            batch_no=_f(a.get("BatchNo")),
            amount=_num(a.get("Amount")),
            pack_unit=_f(a.get("PackUnit")),
            has_codes=_f(a.get("HasCodes")),
        ))

    # ---- 事件（可能多个）+ 明细
    seq = 0
    for ev in root.findall("Events/Event"):
        if not doc.header.event_name:
            doc.header.event_name = _f(ev.get("Name"))
            doc.header.main_action = _f(ev.get("MainAction"))
        # DataField 可能不止一个
        for df in ev.findall("DataField"):
            for d in df.findall("Data"):
                a = d.attrib
                seq += 1
                doc.lines.append(BillLine(
                    seq=seq,
                    code=_f(a.get("Code")),
                    corp_order_id=_f(a.get("CorpOrderID")),
                    actor=_f(a.get("Actor")),
                    act_date=_f(a.get("ActDate")),
                    wrong_code=_f(a.get("WrongCode")),
                    to_corp_id=_f(a.get("ToCorpID")),
                    owner_corp_id=_f(a.get("OwnerCorpID")),
                    product_code=_f(a.get("ProductCode")),
                    ext1=_f(a.get("Ext1")),
                    ext2=_f(a.get("Ext2")),
                    ext3=_f(a.get("Ext3")),
                    ext4=_f(a.get("Ext4")),
                    ext5=_f(a.get("Ext5")),
                ))

    return doc
