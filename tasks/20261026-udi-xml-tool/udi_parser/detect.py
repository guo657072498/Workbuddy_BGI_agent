"""文件类型识别：schema 声明 + 结构双重判断，不依赖文件名。"""

import xml.etree.ElementTree as ET

XSI_SCHEMA = "{http://www.w3.org/2001/XMLSchema-instance}noNamespaceSchemaLocation"

TYPE_BILL = "bill"            # 终端接口：销售出库单（DocHeader + Data）
TYPE_RELATION = "relation"    # 关联关系：生产入库单（Relation + Batch + Code）
TYPE_UNKNOWN = "unknown"

TYPE_LABEL = {
    TYPE_BILL: "销售出库单（终端接口）",
    TYPE_RELATION: "生产入库单（关联关系）",
    TYPE_UNKNOWN: "未知格式",
}


class DetectError(Exception):
    """无法识别文件类型。"""


def load_root(path):
    """读取 XML 根节点。以二进制读入，交由解析器按文件头声明处理编码。

    path 可以是磁盘路径、os.PathLike，也可以是 XmlSource（压缩包内的字节流）。
    """
    data = _read_bytes(path)
    try:
        return ET.fromstring(data)
    except ET.ParseError as e:
        raise DetectError(f"XML 解析失败：{e}") from e
    except ValueError as e:
        raise DetectError(f"XML 内容为空或编码异常：{e}") from e


def _read_bytes(path):
    """统一取值：XmlSource / 路径 / 字节。"""
    if isinstance(path, (bytes, bytearray)):
        return bytes(path)
    if hasattr(path, "read") and not isinstance(path, (str, bytes)):
        return path.read()
    with open(path, "rb") as f:
        return f.read()


def _schema_hint(root):
    """从 schema 声明判断类型，返回 bill / relation / None。"""
    loc = root.get(XSI_SCHEMA) or ""
    if "关联关系" in loc:
        return TYPE_RELATION
    if "终端接口" in loc:
        return TYPE_BILL
    return None


def _struct_hint(root):
    """从实际结构判断类型，返回 bill / relation / None。"""
    tags = {el.tag for el in root.iter()}
    if "DocHeader" in tags:
        return TYPE_BILL
    # Relation 与 Batch 同时存在才算关联关系
    if "Relation" in tags and "Batch" in tags:
        return TYPE_RELATION
    if "Relate" in tags:
        return TYPE_RELATION
    return None


def detect(root):
    """返回 (类型, 判定依据说明)。schema 与结构冲突时报错。"""
    by_schema = _schema_hint(root)
    by_struct = _struct_hint(root)

    if by_schema and by_struct and by_schema != by_struct:
        raise DetectError(
            f"schema 声明指向「{TYPE_LABEL[by_schema]}」，"
            f"但实际结构像「{TYPE_LABEL[by_struct]}」，请确认文件是否完整"
        )
    if by_schema:
        return by_schema, f"schema 声明：{root.get(XSI_SCHEMA)}"
    if by_struct:
        return by_struct, "按结构判定"
    raise DetectError(
        "既不是销售出库单，也不是生产入库单。"
        f"根节点={root.tag}，子节点={[c.tag for c in root][:6]}"
    )
