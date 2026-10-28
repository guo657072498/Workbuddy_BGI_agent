"""转换核心：命令行和图形界面共用同一套逻辑。

不依赖任何界面，可单独调用，也便于测试。
"""

import os
import re

from config import columns as C
from masterdata import store as md_store
from udi_parser import crosscheck, detect, flatten, parse_bill, parse_relation, validate
from udi_parser.source import XmlSource
from xlsx import verify_file, write_workbook

TYPE_BILL = detect.TYPE_BILL
TYPE_RELATION = detect.TYPE_RELATION


class TaskResult:
    """单文件处理结果。"""

    def __init__(self, display_name):
        self.display_name = display_name
        self.ok = False
        self.ftype = ""
        self.type_label = ""
        self.info = ""
        self.issues = []
        self.out_path = ""
        self.engine = ""
        self.verify_ok = False
        self.error = ""
        self.warnings = []

    @property
    def issue_text(self):
        if not self.issues:
            return "无"
        cnt = {}
        for i in self.issues:
            cnt[i.level] = cnt.get(i.level, 0) + 1
        order = ["错误", "警告", "提示"]
        return "、".join(f"{k} {cnt[k]}" for k in order if k in cnt)


def _sanitize(name):
    """把任意字符串转成安全的文件名主干（不含扩展名）。"""
    name = re.sub(r'[\\/:*?"<>|\r\n\t]', "_", name or "").strip()
    return name.strip(". ") or ""


def _safe_name(name):
    """把展示名转成安全的输出文件名。

    压缩包内的文件展示形如「xxx.zip › 路径/文件.xml」，取 › 之后的部分。
    """
    if "›" in name:
        name = name.split("›")[-1].strip()
    base = os.path.basename(name.replace("\\", "/"))
    base = os.path.splitext(base)[0]
    return _sanitize(base) or "output"


def _output_base(doc, ftype):
    """输出文件名主干。

    销售出库单：优先用 DN号（同一单多行明细取第一条的），DN号为空时回退源文件名。
    生产入库单：沿用源文件名。
    """
    if ftype == TYPE_BILL:
        dn = _sanitize((doc.header.store_no or "").strip())
        if dn:
            return dn
    return _safe_name(doc.file_name or "")


def _unique_path(out_dir, base):
    """同名文件自动加序号，不覆盖已有结果。"""
    path = os.path.join(out_dir, base + ".xlsx")
    if not os.path.exists(path):
        return path
    n = 2
    while True:
        path = os.path.join(out_dir, f"{base}({n}).xlsx")
        if not os.path.exists(path):
            return path
        n += 1


def _issue_rows(issues):
    return [{"level": i.level, "rule": i.rule, "location": i.location, "message": i.message}
            for i in issues]


def build_sheets(doc, ftype, cross_map=None, cross_issues=None,
                 products=None, corps=None):
    """按文档类型生成 (sheet名, 列定义, 行数据) 列表。

    销售出库单：销售出库明细 + 校验 两个 sheet。
    生产入库单：盒明细 + 箱汇总 + 码清单 + 校验 四个 sheet。
    """
    if ftype == TYPE_BILL:
        detail = flatten.bill_rows(doc, products=products, corps=corps)
        issues = validate.validate_bill(doc, products=products, corps=corps)
        all_issues = issues + list(cross_issues or [])
        sheets = [
            (C.SHEETS_BILL[0][0], C.SHEETS_BILL[0][1], detail),
            (C.SHEETS_BILL[1][0], C.SHEETS_BILL[1][1], _issue_rows(all_issues)),
        ]
        dn = (doc.header.store_no or "").strip()
        info = f"DN号 {dn or '(无)'} / {len(detail)} 条明细"
        return sheets, info, all_issues

    issues = validate.validate_relation(doc)
    sheets = [
        ("盒明细", C.BOX_ITEM_COLUMNS, flatten.box_item_rows(doc)),
        ("箱汇总", C.BOX_COLUMNS, flatten.box_rows(doc)),
        ("码清单", C.CODE_ALL_COLUMNS, flatten.code_all_rows(doc)),
        ("校验", C.ISSUE_COLUMNS, _issue_rows(issues)),
    ]
    info = f"{doc.box_code_total} 箱 / {doc.box_total} 盒 / {doc.code_total} 个码"
    return sheets, info, issues


def parse_all(sources):
    """第一遍：全部解析（不写盘），用于建立交叉索引。

    返回 (解析结果列表, 错误列表)。每项为 (source, ftype, doc, reason)。
    """
    parsed, errors = [], []
    for src in sources:
        try:
            root = detect.load_root(src)
            ftype, reason = detect.detect(root)
            name = os.path.basename(src.display_name)
            if ftype == TYPE_BILL:
                doc = parse_bill.parse(src, file_name=name)
            else:
                doc = parse_relation.parse(src, file_name=name)
            parsed.append((src, ftype, doc, reason))
        except detect.DetectError as e:
            errors.append((src, str(e)))
        except Exception as e:
            errors.append((src, f"解析失败：{e}"))
    return parsed, errors


def convert(sources, out_dir, engine="auto", progress=None, cancel=None, log=None):
    """批量转换。

    progress: callable(done, total, current_name)
    cancel:   callable() -> bool，返回 True 则中断
    log:      callable(text, level)
    返回 (结果列表, 全局错误列表)。
    """
    os.makedirs(out_dir, exist_ok=True)

    def _log(msg, level="info"):
        # 日志只是旁路输出：回调自身出错（比如控制台编码不支持某字符）
        # 绝不能影响转换主流程
        if log:
            try:
                log(msg, level)
            except Exception:
                pass

    def _cancelled():
        return bool(cancel and cancel())

    total = len(sources)
    results, global_errors = [], []

    # ---- 主数据：一次读盘，逐行查内存
    products, corps, md_errors = md_store.load_indexes()
    for e in md_errors:
        _log(f"主数据：{e}", "error")
    if not md_errors:
        _log(f"主数据：产品 {len(products)} 条、法人 {len(corps)} 条", "info")
        if products.duplicates or corps.duplicates:
            _log(f"主数据：存在重复主键（产品 {products.duplicates} 条、法人 {corps.duplicates} 条），"
                 f"后出现的覆盖前面的，建议检查", "warn")

    # ---- 第一遍：解析，建交叉索引
    _log(f"开始解析 {total} 个文件…")
    bill_docs, rel_docs = [], []
    parsed = []
    for idx, src in enumerate(sources, 1):
        if _cancelled():
            _log("已取消", "warn")
            return results, global_errors
        if progress:
            progress(idx - 1, total * 2, f"解析 {src.display_name}")
        try:
            root = detect.load_root(src)
            ftype, reason = detect.detect(root)
            name = os.path.basename(src.display_name)
            if ftype == TYPE_BILL:
                doc = parse_bill.parse(src, file_name=name)
                bill_docs.append(doc)
            else:
                doc = parse_relation.parse(src, file_name=name)
                rel_docs.append(doc)
            parsed.append((src, ftype, doc, reason))
        except detect.DetectError as e:
            r = TaskResult(src.display_name)
            r.error = str(e)
            results.append(r)
        except Exception as e:
            r = TaskResult(src.display_name)
            r.error = f"解析失败：{e}"
            results.append(r)

    cross_map, cross_issues = ({}, [])
    if bill_docs and rel_docs:
        cross_map, cross_issues = crosscheck.crosscheck(bill_docs, rel_docs)
        _log(f"交叉关联：{len(cross_map)} 个码匹配到所属箱码", "info")

    # ---- 第二遍：写盘
    done = 0
    for src, ftype, doc, reason in parsed:
        if _cancelled():
            _log("已取消", "warn")
            break
        done += 1
        if progress:
            progress(total + done - 1, total * 2, f"写出 {src.display_name}")

        r = TaskResult(src.display_name)
        r.ftype = ftype
        r.type_label = detect.TYPE_LABEL[ftype]
        try:
            # 交叉提示只挂到本条明细真正涉及的码，避免整批文件的提示挤进每个文件
            own_issues = None
            if ftype == TYPE_BILL and cross_issues:
                codes = {ln.code for ln in doc.lines}
                own_issues = [i for i in cross_issues if any(c in i.message for c in codes)]

            sheets, info, issues = build_sheets(
                doc, ftype,
                cross_map=cross_map if ftype == TYPE_BILL else None,
                cross_issues=own_issues,
                products=products,
                corps=corps,
            )
            base = _output_base(doc, ftype)
            out_path = _unique_path(out_dir, base)
            used = write_workbook(out_path, sheets, engine=engine,
                                  highlight=C.HIGHLIGHT_ERROR)
            vr = verify_file(out_path, sheets)

            r.ok = True
            r.info = info
            r.issues = issues
            r.out_path = out_path
            r.engine = used
            r.verify_ok = vr.ok
            if not vr.ok:
                r.warnings.append(str(vr))
            if base + ".xlsx" != os.path.basename(out_path):
                r.warnings.append(f"同名文件已存在，本次另存为 {os.path.basename(out_path)}")
            _log(f"[完成] {src.display_name} → {os.path.basename(out_path)}（{info}）")
        except Exception as e:
            r.error = f"写出失败：{e}"
            _log(f"[失败] {src.display_name}：{r.error}", "error")
        results.append(r)

    if progress:
        progress(total * 2, total * 2, "完成")
    return results, global_errors
