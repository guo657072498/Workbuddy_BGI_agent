"""UDI XML 转 Excel —— 图形界面。

设计要点：
1. 转换在后台线程跑，界面不卡死，进度条实时更新。
2. 优先使用 Windows 原生拖拽（tkinterdnd2）；不可用时自动退回「添加文件/文件夹」按钮。
3. 所有异常都在界面里以弹窗或日志呈现，绝不静默退出。
"""

import os
import queue
import subprocess
import sys
import threading
import traceback

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

# 打包后 _MEIPASS 是临时解包目录，源码运行时是脚本目录
if getattr(sys, "frozen", False):
    APP_DIR = os.path.dirname(sys.executable)
    RES_DIR = getattr(sys, "_MEIPASS", APP_DIR)
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))
    RES_DIR = APP_DIR
sys.path.insert(0, RES_DIR)

from converter import convert          # noqa: E402
from udi_parser import source as src_mod  # noqa: E402

# ---------------------------------------------------------------- 拖拽支持

DND_OK = False
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    DND_OK = True
except Exception:
    DND_FILES = None


# ---------------------------------------------------------------- 主窗口

class App:
    def __init__(self, root):
        self.root = root
        self.sources = []          # XmlSource 列表
        self.queue = queue.Queue()
        self.worker = None
        self.cancel_flag = threading.Event()
        self.results = []
        self._build_ui()
        self._poll_queue()

    # ------------------------------------------------------------ 布局

    def _build_ui(self):
        self.root.title("UDI XML 转 Excel")
        self.root.geometry("860x680")
        self.root.minsize(760, 580)

        style = ttk.Style()
        try:
            style.theme_use("vista")
        except tk.TclError:
            pass

        # 顶部标题
        head = ttk.Frame(self.root, padding=(16, 14, 16, 6))
        head.pack(fill="x")
        ttk.Label(head, text="UDI XML 转 Excel", font=("Microsoft YaHei UI", 15, "bold")).pack(anchor="w")
        ttk.Label(
            head,
            text="支持 xml 文件、zip 压缩包、文件夹。压缩包内的 xml 会被自动展开处理。",
            foreground="#666",
        ).pack(anchor="w", pady=(3, 0))

        # 拖拽区
        drop_wrap = ttk.Frame(self.root, padding=(16, 8, 16, 0))
        drop_wrap.pack(fill="both", expand=False)
        self.drop = tk.Frame(drop_wrap, bg="#F5F8FF", highlightthickness=2,
                             highlightbackground="#B8CCF0", height=120)
        self.drop.pack(fill="x")
        self.drop.pack_propagate(False)
        self.drop_label = tk.Label(
            self.drop,
            text=("把 xml 文件、zip 压缩包或文件夹拖到这里" if DND_OK
                  else "点击下方按钮添加文件（当前环境不支持拖拽）"),
            bg="#F5F8FF", fg="#3B5BA5", font=("Microsoft YaHei UI", 11),
        )
        self.drop_label.pack(expand=True)

        if DND_OK:
            for w in (self.drop, self.drop_label):
                w.drop_target_register(DND_FILES)
                w.dnd_bind("<<Drop>>", self._on_drop)
            self.drop_label.configure(
                text="把 xml 文件、zip 压缩包或文件夹拖到这里\n也可以点下面的按钮选择",
                justify="center",
            )

        # 按钮行
        btn_row = ttk.Frame(self.root, padding=(16, 10, 16, 0))
        btn_row.pack(fill="x")
        ttk.Button(btn_row, text="添加文件…", command=self._add_files).pack(side="left")
        ttk.Button(btn_row, text="添加文件夹…", command=self._add_folder).pack(side="left", padx=(8, 0))
        ttk.Button(btn_row, text="清空列表", command=self._clear).pack(side="left", padx=(8, 0))
        self.count_label = ttk.Label(btn_row, text="已添加 0 个文件", foreground="#666")
        self.count_label.pack(side="right")

        # 文件列表
        list_wrap = ttk.Frame(self.root, padding=(16, 10, 16, 0))
        list_wrap.pack(fill="both", expand=True)
        cols = ("file", "type", "status")
        self.tree = ttk.Treeview(list_wrap, columns=cols, show="headings", height=9)
        self.tree.heading("file", text="文件")
        self.tree.heading("type", text="识别类型")
        self.tree.heading("status", text="状态")
        self.tree.column("file", width=430, anchor="w")
        self.tree.column("type", width=190, anchor="w")
        self.tree.column("status", width=200, anchor="w")
        vsb = ttk.Scrollbar(list_wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.tree.tag_configure("ok", foreground="#1B7F3B")
        self.tree.tag_configure("err", foreground="#C0392B")
        self.tree.tag_configure("warn", foreground="#B9770E")

        # 输出目录
        out_row = ttk.Frame(self.root, padding=(16, 10, 16, 0))
        out_row.pack(fill="x")
        ttk.Label(out_row, text="输出到：").pack(side="left")
        self.out_var = tk.StringVar(value=os.path.join(APP_DIR, "输出结果"))
        ttk.Entry(out_row, textvariable=self.out_var).pack(side="left", fill="x", expand=True, padx=(6, 6))
        ttk.Button(out_row, text="更改…", command=self._pick_out).pack(side="left")
        ttk.Button(out_row, text="打开", command=self._open_out).pack(side="left", padx=(6, 0))

        # 操作行
        act = ttk.Frame(self.root, padding=(16, 12, 16, 0))
        act.pack(fill="x")
        self.btn_start = ttk.Button(act, text="开始转换", command=self._start)
        self.btn_start.pack(side="left")
        self.btn_cancel = ttk.Button(act, text="取消", command=self._cancel, state="disabled")
        self.btn_cancel.pack(side="left", padx=(8, 0))
        self.progress = ttk.Progressbar(act, mode="determinate", maximum=100)
        self.progress.pack(side="left", fill="x", expand=True, padx=(12, 0))
        self.pct_label = ttk.Label(act, text="", width=6, anchor="e")
        self.pct_label.pack(side="left", padx=(6, 0))

        # 日志
        log_wrap = ttk.Frame(self.root, padding=(16, 10, 16, 14))
        log_wrap.pack(fill="both", expand=False)
        self.log = tk.Text(log_wrap, height=7, wrap="word", bg="#FAFAFA",
                           relief="solid", borderwidth=1, font=("Consolas", 9))
        lsb = ttk.Scrollbar(log_wrap, orient="vertical", command=self.log.yview)
        self.log.configure(yscrollcommand=lsb.set)
        self.log.pack(side="left", fill="both", expand=True)
        lsb.pack(side="right", fill="y")
        for tag, color in (("info", "#333"), ("ok", "#1B7F3B"),
                           ("warn", "#B9770E"), ("error", "#C0392B")):
            self.log.tag_configure(tag, foreground=color)
        self.log.configure(state="disabled")
        self._log(f"就绪。{'拖拽' if DND_OK else '按钮'}添加文件后点「开始转换」。", "info")

    # ------------------------------------------------------------ 日志 / 进度

    def _log(self, text, level="info"):
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n", level)
        self.log.see("end")
        self.log.configure(state="disabled")

    def _poll_queue(self):
        """主线程定时取出工作线程的消息，避免跨线程操作界面。"""
        try:
            while True:
                kind, payload = self.queue.get_nowait()
                if kind == "log":
                    self._log(*payload)
                elif kind == "progress":
                    done, total, name = payload
                    pct = int(done * 100 / total) if total else 0
                    self.progress["value"] = pct
                    self.pct_label.configure(text=f"{pct}%")
                elif kind == "row":
                    idx, text, tag = payload
                    iid = f"row{idx}"
                    if self.tree.exists(iid):
                        self.tree.set(iid, "status", text)
                        self.tree.item(iid, tags=(tag,))
                elif kind == "done":
                    self._on_done(payload)
                elif kind == "fatal":
                    messagebox.showerror("出错了", payload)
        except queue.Empty:
            pass
        self.root.after(80, self._poll_queue)

    # ------------------------------------------------------------ 添加文件

    def _on_drop(self, event):
        try:
            paths = self.root.tk.splitlist(event.data)
        except Exception:
            paths = [event.data]
        self._add_paths(list(paths))

    def _add_files(self):
        paths = filedialog.askopenfilenames(
            title="选择 xml 或 zip 文件",
            filetypes=[("XML 和压缩包", "*.xml *.XML *.zip *.ZIP"), ("所有文件", "*.*")],
        )
        if paths:
            self._add_paths(list(paths))

    def _add_folder(self):
        d = filedialog.askdirectory(title="选择包含 xml / zip 的文件夹")
        if d:
            self._add_paths([d])

    def _add_paths(self, paths):
        if self.worker and self.worker.is_alive():
            messagebox.showinfo("请稍候", "正在转换中，请等待完成或点「取消」。")
            return
        try:
            new_sources, errors = src_mod.expand(paths)
        except Exception as e:
            messagebox.showerror("添加失败", f"读取文件时出错：\n{e}")
            return

        existing = {(s.display_name, id(s)) for s in self.sources}
        added = 0
        for s in new_sources:
            if (s.display_name, id(s)) in existing:
                continue
            self.sources.append(s)
            added += 1

        for e in errors:
            self._log("！ " + e, "warn")

        self._refresh_tree()
        if added:
            self._log(f"已添加 {added} 个文件（压缩包已展开）。", "info")
        elif not errors:
            self._log("没有新增可处理的 xml。", "warn")
        if errors and not added:
            messagebox.showwarning("没有可处理的文件", "\n".join(errors[:8]))

    def _refresh_tree(self):
        self.tree.delete(*self.tree.get_children())
        for i, s in enumerate(self.sources):
            self.tree.insert("", "end", iid=f"row{i}",
                             values=(s.display_name, "待识别", "待处理"))
        self.count_label.configure(text=f"已添加 {len(self.sources)} 个文件")

    def _clear(self):
        if self.worker and self.worker.is_alive():
            messagebox.showinfo("请稍候", "正在转换中，无法清空。")
            return
        self.sources.clear()
        self.results = []
        self._refresh_tree()
        self.progress["value"] = 0
        self.pct_label.configure(text="")

    # ------------------------------------------------------------ 输出目录

    def _pick_out(self):
        d = filedialog.askdirectory(title="选择输出目录")
        if d:
            self.out_var.set(d)

    def _open_out(self):
        d = self.out_var.get().strip()
        if not d:
            return
        if not os.path.isdir(d):
            messagebox.showinfo("目录不存在", "还没有输出结果，或目录已被移动。")
            return
        try:
            if os.name == "nt":
                os.startfile(d)  # noqa: S606
            elif sys.platform == "darwin":
                subprocess.Popen(["open", d])
            else:
                subprocess.Popen(["xdg-open", d])
        except Exception as e:
            messagebox.showerror("打不开", str(e))

    # ------------------------------------------------------------ 转换

    def _start(self):
        if self.worker and self.worker.is_alive():
            return
        if not self.sources:
            messagebox.showinfo("没有文件", "请先添加要转换的 xml 或压缩包。")
            return
        out_dir = self.out_var.get().strip()
        if not out_dir:
            messagebox.showinfo("缺少输出目录", "请先选择输出目录。")
            return

        self.cancel_flag.clear()
        self.btn_start.configure(state="disabled")
        self.btn_cancel.configure(state="normal")
        self.progress["value"] = 0
        self.pct_label.configure(text="0%")
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")
        self._log(f"输出目录：{out_dir}", "info")

        for i in range(len(self.sources)):
            iid = f"row{i}"
            if self.tree.exists(iid):
                self.tree.set(iid, "status", "处理中…")
                self.tree.item(iid, tags=())

        sources = list(self.sources)
        self.worker = threading.Thread(
            target=self._run_worker, args=(sources, out_dir), daemon=True
        )
        self.worker.start()

    def _run_worker(self, sources, out_dir):
        try:
            results, _ = convert(
                sources, out_dir,
                progress=lambda d, t, n: self.queue.put(("progress", (d, t, n))),
                cancel=lambda: self.cancel_flag.is_set(),
                log=lambda m, lv="info": self.queue.put(("log", (m, "ok" if lv == "ok" else lv))),
            )
            # 逐行回填状态
            name_to_idx = {s.display_name: i for i, s in enumerate(sources)}
            for r in results:
                idx = name_to_idx.get(r.display_name)
                if idx is None:
                    continue
                if r.ok:
                    txt = f"完成 {r.info} {('·校验通过' if r.verify_ok else '·自检异常')}"
                    tag = "ok" if r.verify_ok else "warn"
                else:
                    txt = "失败：" + r.error[:60]
                    tag = "err"
                self.queue.put(("row", (idx, txt, tag)))
            self.queue.put(("done", results))
        except Exception:
            self.queue.put(("fatal", "转换过程中出现意外错误：\n\n" + traceback.format_exc()))

    def _cancel(self):
        self.cancel_flag.set()
        self.btn_cancel.configure(state="disabled")
        self._log("正在取消…", "warn")

    def _on_done(self, results):
        self.results = results
        self.btn_start.configure(state="normal")
        self.btn_cancel.configure(state="disabled")

        ok = [r for r in results if r.ok]
        bad = [r for r in results if not r.ok]
        warn_verify = [r for r in ok if not r.verify_ok]

        self._log("─" * 52, "info")
        self._log(f"完成：成功 {len(ok)} 个，失败 {len(bad)} 个。", "ok" if not bad else "warn")
        if warn_verify:
            self._log(f"注意：{len(warn_verify)} 个文件写盘自检未通过，请抽查。", "error")
        if bad:
            for r in bad[:5]:
                self._log(f"  失败：{r.display_name} — {r.error}", "error")

        if bad:
            messagebox.showwarning(
                "部分文件未成功",
                f"成功 {len(ok)} 个，失败 {len(bad)} 个。\n详见下方日志。",
            )
        elif ok:
            if messagebox.askyesno("转换完成", f"成功转换 {len(ok)} 个文件。\n现在打开输出目录吗？"):
                self._open_out()


# ---------------------------------------------------------------- 入口

def run(argv=None):
    argv = sys.argv if argv is None else argv

    # 自检模式：设置 UDI_SELFTEST=<输出目录> 时跑一次转换后退出（用于验证打包产物）
    selftest = os.environ.get("UDI_SELFTEST")
    if selftest:
        return _selftest(selftest)

    try:
        if DND_OK:
            root = TkinterDnD.Tk()
        else:
            root = tk.Tk()
    except Exception as e:
        # 极端情况：没有图形环境
        print(f"无法启动图形界面：{e}")
        return 1
    App(root)
    root.mainloop()
    return 0


def _selftest(out_dir):
    """不打开窗口，直接跑一遍完整转换，把结果打到 stdout。"""
    import traceback

    # 控制台可能是 GBK，统一成能容错的 utf-8 输出
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    def say(msg):
        try:
            print(msg, flush=True)
        except Exception:
            pass

    say("=== 自检模式 ===")
    say("Python: " + sys.version.split()[0])
    say("冻结包: " + str(getattr(sys, "frozen", False)))
    say("拖拽支持: " + str(DND_OK))
    try:
        import tkinter
        say(f"tkinter: {tkinter.TkVersion}")
    except Exception as e:
        say(f"tkinter 失败: {e}")

    data = os.environ.get("UDI_SELFTEST_IN", "")
    paths = [p for p in data.split(";") if p]
    if not paths:
        say("未提供测试输入")
        return 1
    ok = True
    try:
        sources, errors = src_mod.expand(paths)
        say(f"展开出 {len(sources)} 个 xml，提示 {len(errors)} 条")
        for e in errors:
            say("  ! " + e)
        results, _ = convert(sources, out_dir, log=lambda m, lv="info": say("  " + m))
        for r in results:
            if r.ok:
                say(f"  OK  {r.display_name} -> {os.path.basename(r.out_path)} | {r.info}")
            else:
                ok = False
                say(f"  ERR {r.display_name}: {r.error}")
    except Exception:
        ok = False
        say("自检异常：")
        say(traceback.format_exc())

    say("=== 自检" + ("通过" if ok else "失败") + " ===")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(run())
