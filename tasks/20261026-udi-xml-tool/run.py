"""UDI XML → Excel 明细行

用法：
    双击 一键转换.bat                 （把 xml 拖到 bat 上，或直接双击后输入路径）
    python run.py <文件或目录> [...]  （命令行）
    python run.py -i <目录> -o <输出目录>
"""

import argparse
import glob
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def _fix_console():
    """中文 Windows 控制台默认 GBK(936)，Python 却按 UTF-8 输出，会导致乱码/报错。
    这里把 stdout 的写法改成"遇到杀不掉的字符就替换"，不改变编码。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")


_fix_console()


from config import columns as C                                    # noqa: E402
from udi_parser import crosscheck, detect, flatten, parse_bill      # noqa: E402
from udi_parser import parse_relation, validate                     # noqa: E402
from xlsx import verify_file, write_workbook                        # noqa: E402

TYPE_BILL = detect.TYPE_BILL
TYPE_RELATION = detect.TYPE_RELATION


# ---------------------------------------------------------------- 收集文件

def collect(paths):
    """把传入的路径展开成 xml 文件列表。"""
    out = []
    for p in paths:
        if os.path.isdir(p):
            for ext in ("*.xml", "*.XML"):
                out.extend(glob.glob(os.path.join(p, ext)))
        elif os.path.isfile(p):
            out.append(p)
        else:
            print(f"  [跳过] 找不到：{p}")
    # 去重并保持顺序
    seen, uniq = set(), []
    for p in out:
        ap = os.path.abspath(p)
        if ap not in seen:
            seen.add(ap)
            uniq.append(ap)
    return uniq


# ---------------------------------------------------------------- 单文件处理

def process_one(path, out_dir, engine, cross_map=None, cross_issues=None):
    """解析单个文件并写出 Excel。返回 (类型, xlsx路径, 行数信息)。"""
    root = detect.load_root(path)
    ftype, reason = detect.detect(root)
    base = os.path.splitext(os.path.basename(path))[0]
    out_path = os.path.join(out_dir, base + ".xlsx")

    if ftype == TYPE_BILL:
        doc = parse_bill.parse(path)
        issues = validate.validate_bill(doc)
        detail = flatten.bill_rows(doc)

        # 有交叉索引则补充"所属箱码"
        if cross_map:
            for row in detail:
                hit = cross_map.get(row["code"])
                row["box_code_link"] = hit["box_code"] if hit else ""
                row["batch_link"] = hit["batch_no"] if hit else ""
        else:
            for row in detail:
                row["box_code_link"] = ""
                row["batch_link"] = ""

        cols = list(C.BILL_COLUMNS)
        if cross_map or cross_issues:
            # 追加两列（追加在 UDI码 后面较难，直接放末尾，用户可自行调序）
            cols = cols + [
                ("box_code_link", "所属箱码", "text", 32),
                ("batch_link",    "所属批次", "text", 16),
            ]
        sheets = [
            ("出入库明细", cols, detail),
            ("产品汇总", C.BILL_SUMMARY_COLUMNS, flatten.bill_summary_rows(doc)),
            ("校验", C.ISSUE_COLUMNS, _issue_rows(issues + list(cross_issues or []))),
        ]
        info = f"{len(doc.products)} 个产品 / {len(detail)} 条明细"
    else:
        doc = parse_relation.parse(path)
        issues = validate.validate_relation(doc)
        sheets = [
            ("盒明细", C.BOX_ITEM_COLUMNS, flatten.box_item_rows(doc)),
            ("箱汇总", C.BOX_COLUMNS, flatten.box_rows(doc)),
            ("码清单", C.CODE_ALL_COLUMNS, flatten.code_all_rows(doc)),
            ("校验", C.ISSUE_COLUMNS, _issue_rows(issues)),
        ]
        info = f"{doc.box_code_total} 箱 / {doc.box_total} 盒 / {doc.code_total} 个码"

    used = write_workbook(out_path, sheets, engine=engine, highlight=C.HIGHLIGHT_ERROR)
    vr = verify_file(out_path, sheets)

    return {
        "type": ftype,
        "reason": reason,
        "path": out_path,
        "info": info,
        "issues": issues,
        "engine": used,
        "verify": vr,
        "doc": doc,
    }


def _issue_rows(issues):
    return [{"level": i.level, "rule": i.rule, "location": i.location, "message": i.message}
            for i in issues]


def _issue_stat(issues):
    if not issues:
        return "无"
    cnt = {}
    for i in issues:
        cnt[i.level] = cnt.get(i.level, 0) + 1
    return "、".join(f"{k} {v}" for k, v in cnt.items())


# ---------------------------------------------------------------- 主流程

def run(input_paths, out_dir, engine):
    files = collect(input_paths)
    if not files:
        print("没有找到任何 xml 文件。")
        return 1

    os.makedirs(out_dir, exist_ok=True)
    print(f"共 {len(files)} 个文件，输出到：{out_dir}\n")

    # 第一遍：只解析，先建立码→箱的索引，供交叉校验
    bill_docs, rel_docs, errors = [], [], []
    for f in files:
        try:
            root = detect.load_root(f)
            ftype, _ = detect.detect(root)
            if ftype == TYPE_BILL:
                bill_docs.append(parse_bill.parse(f))
            else:
                rel_docs.append(parse_relation.parse(f))
        except Exception as e:
            errors.append((f, e))

    cross_map, cross_issues = ({}, [])
    if bill_docs and rel_docs:
        cross_map, cross_issues = crosscheck.crosscheck(bill_docs, rel_docs)

    # 第二遍：逐文件写出
    ok = fail = 0
    for f in files:
        name = os.path.basename(f)
        print(f"[{name}]")
        try:
            r = process_one(f, out_dir, engine, cross_map, cross_issues)
            print(f"  类型：{detect.TYPE_LABEL[r['type']]}（{r['reason']}）")
            print(f"  内容：{r['info']}")
            print(f"  校验：{_issue_stat(r['issues'])}")
            if not r["verify"].ok:
                print(f"  ⚠ {r['verify']}")
            print(f"  输出：{os.path.basename(r['path'])}  [{r['engine']}]")
            ok += 1
        except detect.DetectError as e:
            print(f"  [失败] 无法识别：{e}")
            fail += 1
        except Exception as e:
            print(f"  [失败] 处理失败：{e}")
            fail += 1
            if os.environ.get("UDI_DEBUG"):
                traceback.print_exc()
        print()

    print("=" * 60)
    print(f"完成：成功 {ok} 个，失败 {fail} 个。输出目录：{out_dir}")
    if cross_issues:
        shown = len(cross_issues)
        hit = len(cross_map)
        print(f"交叉关联：{hit} 个码匹配到所属箱码，{shown} 条未能关联（提示级，不影响结果）")
    return 0 if fail == 0 else 2


def _default_out():
    d = os.path.join(HERE, "output")
    return d


def interactive():
    """无参数双击运行时的交互。"""
    print("=" * 60)
    print("  UDI XML 转 Excel")
    print("=" * 60)
    print("把 xml 文件（可多个）或文件夹拖到本窗口，按回车。")
    print("直接回车 = 处理 udi-xml 目录下的全部 xml")
    print()
    try:
        raw = input("> ").strip().strip('"')
    except (EOFError, KeyboardInterrupt):
        return 1
    if not raw:
        guess = r"E:\重要_个人存储文件夹\04.Workbuddy_Bgi\办公助理\udi-xml"
        if os.path.isdir(guess):
            raw = guess
        else:
            print("未找到默认目录，请拖入文件。")
            return 1
    paths = [p.strip().strip('"') for p in raw.replace(";", "\n").split("\n") if p.strip()]
    if len(paths) == 1 and " " in paths[0] and not os.path.exists(paths[0]):
        paths = [p for p in paths[0].split(" ") if p]
    rc = run(paths, _default_out(), "auto")
    print()
    try:
        input("按回车关闭窗口…")
    except (EOFError, KeyboardInterrupt):
        pass
    return rc


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="UDI XML 转 Excel 明细行",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="示例：\n  python run.py udi-xml\n  python run.py a.xml b.xml -o out\n",
    )
    ap.add_argument("inputs", nargs="*", help="xml 文件或包含 xml 的目录")
    ap.add_argument("-i", "--input", action="append", default=[], help="输入文件或目录（可多次）")
    ap.add_argument("-o", "--output", default=None, help="输出目录，默认 ./output")
    ap.add_argument("-e", "--engine", default="auto", choices=["auto", "openpyxl", "stdlib"],
                    help="Excel 写出引擎，默认 auto（优先 openpyxl，失败自动降级）")
    args = ap.parse_args(argv)

    inputs = list(args.inputs) + list(args.input)
    if not inputs:
        return interactive()
    return run(inputs, args.output or _default_out(), args.engine)


if __name__ == "__main__":
    sys.exit(main())
