"""数据模型：解析后的中间结构。"""

from dataclasses import dataclass, field
from typing import List, Optional


# ---------------------------------------------------------------- 文件 A

@dataclass
class BillHeader:
    """出/入库单的单据头（DocHeader 全部属性）。"""
    doc_owner: str = ""
    doc_type: str = ""
    store_type: str = ""
    bill_time: str = ""
    operator: str = ""
    remark: str = ""
    operate_date: str = ""
    doc_version: str = ""
    store_no: str = ""
    store_no_ext: str = ""
    customer_no: str = ""
    corp_code: str = ""
    biz_corp_code: str = ""
    # Event
    event_name: str = ""
    main_action: str = ""


@dataclass
class BillProduct:
    """HasProducts/Product：产品声明行。"""
    code: str = ""
    batch_no: str = ""
    amount: float = 0
    pack_unit: str = ""
    has_codes: str = ""


@dataclass
class BillLine:
    """DataField/Data：一条扫码明细。"""
    seq: int = 0
    code: str = ""
    corp_order_id: str = ""
    actor: str = ""
    act_date: str = ""
    wrong_code: str = ""
    to_corp_id: str = ""
    owner_corp_id: str = ""
    product_code: str = ""
    ext1: str = ""
    ext2: str = ""
    ext3: str = ""
    ext4: str = ""
    ext5: str = ""


@dataclass
class BillDoc:
    """文件 A 完整解析结果。"""
    file_name: str = ""
    header: BillHeader = field(default_factory=BillHeader)
    products: List[BillProduct] = field(default_factory=list)
    lines: List[BillLine] = field(default_factory=list)


# ---------------------------------------------------------------- 文件 B

@dataclass
class BatchInfo:
    """Relation/Batch 的属性。"""
    batch_no: str = ""
    made_date: str = ""
    validate_date: str = ""
    workshop: str = ""
    line_name: str = ""
    line_manager: str = ""
    work_order: str = ""


@dataclass
class RelationInfo:
    """Relation 的属性。"""
    product_code: str = ""
    sub_type_no: str = ""
    cascade: str = ""
    package_spec: str = ""
    comment: str = ""


@dataclass
class CodeNode:
    """Batch/Code：一个码。保留其在 XML 中的原始位置。"""
    seq_in_file: int = 0          # 在整个文件里的原始出现序号（从 1 开始）
    cur_code: str = ""
    pack_layer: str = ""          # "1"=盒, "2"=箱
    parent_code: str = ""
    flag: str = ""
    print_count: str = ""
    status: str = ""


@dataclass
class BoxBlock:
    """一个箱块：箱码 + 紧随其后的盒码。"""
    box_code: str = ""            # 箱码为空表示"游离盒码"（盒码先于任何箱码出现）
    start_seq: int = 0            # 箱码在文件中的原始序号
    end_seq: int = 0
    items: List[CodeNode] = field(default_factory=list)

    @property
    def box_count(self) -> int:
        return len(self.items)


@dataclass
class RelationBatch:
    """一组 Relation + Batch + 其下的箱块。"""
    relation_index: int = 1
    batch_index: int = 1
    relation: RelationInfo = field(default_factory=RelationInfo)
    batch: BatchInfo = field(default_factory=BatchInfo)
    boxes: List[BoxBlock] = field(default_factory=list)
    all_codes: List[CodeNode] = field(default_factory=list)


@dataclass
class RelationDoc:
    """文件 B 完整解析结果。"""
    file_name: str = ""
    license: str = ""
    event_name: str = ""
    version: str = ""
    groups: List[RelationBatch] = field(default_factory=list)

    @property
    def box_total(self) -> int:
        return sum(len(b.items) for g in self.groups for b in g.boxes)

    @property
    def box_code_total(self) -> int:
        return sum(1 for g in self.groups for b in g.boxes if b.box_code)

    @property
    def code_total(self) -> int:
        return sum(len(g.all_codes) for g in self.groups)


# ---------------------------------------------------------------- 校验

@dataclass
class Issue:
    """一条校验结果。"""
    rule: str = ""
    level: str = ""      # 错误 / 警告 / 提示
    location: str = ""   # 出处描述，如 "箱1 / 第3条"
    message: str = ""
