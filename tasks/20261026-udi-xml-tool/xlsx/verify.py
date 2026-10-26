"""写盘自检：回读 Excel，确认码列仍为 30 位文本、没有科学计数法。

这是 UDI 场景的兜底防线 —— 码一旦变成数字，精度会丢，数据就废了。
"""

import re
import zipfile

from .writer import TEXT


class VerifyResult:
    def __init__(self):
        self.ok = True
        self.problems = []
        self.checked = 0

    def fail(self, msg):
        self.ok = False
        self.problems.append(msg)

    def __str__(self):
        if self.ok:
            return f"自检通过（已核验 {self.checked} 个码单元格）"
        return "自检失败：\n  - " + "\n  - ".join(self.problems)


_SCI = re.compile(r"^\d(\.\d+)?[Ee]\+?\d+$")


def _decode(s):
    return (s.replace("&lt;", "<").replace("&gt;", ">")
             .replace("&quot;", '"').replace("&apos;", "'")
             .replace("&amp;", "&"))


def verify_file(path, sheets, expect_codes=None):
    """回读 xlsx（用 zipfile 直接读 XML，不依赖 openpyxl），核验文本列。

    sheets: [(name, columns, records), ...]
    expect_codes: 可选的期望码集合，用于核对行数
    """
    r = VerifyResult()
    try:
        z = zipfile.ZipFile(path)
    except Exception as e:
        r.fail(f"无法打开文件：{e}")
        return r

    with z:
        names = z.namelist()
        # 需要按 sheet 顺序找到对应 XML
        idx = 1
        for name, columns, records, *rest in sheets:
            part = f"xl/worksheets/sheet{idx}.xml"
            idx += 1
            if part not in names:
                r.fail(f"sheet「{name}」缺失（{part}）")
                continue

            xml = z.read(part).decode("utf-8", "replace")
            rows = re.findall(r"<row[^>]*>(.*?)</row>", xml, re.S)
            # 数据行数（去表头）
            if len(rows) - 1 != len(records):
                r.fail(f"sheet「{name}」行数不符：期望 {len(records)}，实际 {len(rows) - 1}")

            # 校验文本列：每列不能出现 <v>数字</v> 形式（那意味着被当成数字了）
            text_cols = {ci: c for ci, c in enumerate(columns, 1) if c[2] == TEXT}
            for row_i, row in enumerate(rows[1:], 2):
                # 先按单元格起始位置切开，避免自闭合标签吞掉下一个单元格的内容
                pieces = re.split(r"(?=<c\b)", row)
                for piece in pieces:
                    m = re.match(r'<c\b([^>]*?)(?:/>|>(.*)</c>)$', piece.strip(), re.S)
                    if not m:
                        continue
                    attrs, inner = m.group(1), (m.group(2) or "")
                    rm = re.search(r'r="([A-Z]+)(\d+)"', attrs)
                    if not rm:
                        continue
                    col_letter, row_no = rm.group(1), rm.group(2)
                    col_no = 0
                    for ch in col_letter:
                        col_no = col_no * 26 + (ord(ch) - 64)
                    col = text_cols.get(col_no)
                    if not col:
                        continue
                    is_text_cell = 't="inlineStr"' in attrs or 't="s"' in attrs or 't="str"' in attrs
                    v = re.search(r"<v>(.*?)</v>", inner, re.S)
                    if not is_text_cell and v:
                        r.fail(f"sheet「{name}」{col_letter}{row_no} 的「{col[1]}」被写成了数字：{v.group(1)[:40]}")
                        continue
                    if v and _SCI.match(v.group(1).strip()):
                        r.fail(f"sheet「{name}」{col_letter}{row_no} 出现科学计数法：{v.group(1)}")
                        continue
                    r.checked += 1
                    # 码列长度抽检（只对有值且非占位的单元格）
                    if col[0] in ("code", "box_code", "parent_code", "first_code", "last_code"):
                        val = ""
                        t = re.search(r"<t[^>]*>(.*?)</t>", inner, re.S)
                        if t:
                            val = _decode(t.group(1)).strip()
                        if val and val not in ("（无箱码）",) and len(val) != 30:
                            r.fail(f"sheet「{name}」{col_letter}{row_no} 码长度异常 {len(val)}：{val[:40]}")
    return r
