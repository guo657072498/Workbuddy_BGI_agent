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
from converter import convert                                      # noqa: E402
from udi_parser import detect                                      # noqa: E402
from udi_parser import source as src_mod                           # noqa: E402

TYPE_BILL = detect.TYPE_BILL
TYPE_RELATION = detect.TYPE_RELATION


# ---------------------------------------------------------------- 收集文件

def collect(paths):
    """把传入的路径展开成 xml 文件列表（只用于打印预览）。

    真正的展开（含 zip 内层）由 udi_parser.source.expand 负责，
    这里只做「找不到路径」的提示和去重。
    """
    out = []
    for p in paths:
        if os.path.isdir(p):
            for ext in ("*.xml", "*.XML"):
                out.extend(glob.glob(os.path.join(p, ext)))
        elif os.path.isfile(p):
            out.append(p)
        else:
            print(f"  [跳过] 找不到：{p}")
    seen, uniq = set(), []
    for p in out:
        ap = os.path.abspath(p)
        if ap not in seen:
            seen.add(ap)
            uniq.append(ap)
    return uniq


# ---------------------------------------------------------------- 输出

def _issue_stat(issues):
    if not issues:
        return "无"
    cnt = {}
    for i in issues:
        cnt[i.level] = cnt.get(i.level, 0) + 1
    return "、".join(f"{k} {v}" for k, v in cnt.items())


# ---------------------------------------------------------------- 主流程

def run(input_paths, out_dir, engine):
    sources, expand_errors = src_mod.expand(input_paths)
    for e in expand_errors:
        print(f"  [提示] {e}")
    if not sources:
        print("没有找到任何可处理的 xml 或压缩包。")
        return 1

    os.makedirs(out_dir, exist_ok=True)
    print(f"共 {len(sources)} 个 xml（含压缩包内文件），输出到：{out_dir}\n")

    logs = []

    def _log(msg, level="info"):
        logs.append((level, msg))
        print("  " + msg)

    results, _ = convert(sources, out_dir, engine=engine, log=_log)

    ok = fail = 0
    for r in results:
        print(f"[{r.display_name}]")
        if r.ok:
            print(f"  类型：{r.type_label}")
            print(f"  内容：{r.info}")
            print(f"  校验：{_issue_stat(r.issues)}")
            if not r.verify_ok:
                print(f"  ⚠ 写盘自检未通过，请抽查")
            for w in r.warnings:
                print(f"  ! {w}")
            print(f"  输出：{os.path.basename(r.out_path)}  [{r.engine}]")
            ok += 1
        else:
            print(f"  [失败] {r.error}")
            fail += 1
        print()

    print("=" * 60)
    print(f"完成：成功 {ok} 个，失败 {fail} 个。输出目录：{out_dir}")
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
