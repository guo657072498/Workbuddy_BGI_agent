"""主数据管理窗：产品 / 法人共用一套界面。

功能：搜索、双击改单元格、删除行、新增一行、上传 Excel、导出当前数据。
任何修改立即写盘，没有「草稿」状态 —— 所以删除前会二次确认。
"""

import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from . import importing, store


class MasterDataWindow(tk.Toplevel):
    def __init__(self, master, kind, on_change=None):
        self.kind = kind
        self.on_change = on_change
        self.cols = store.column_defs(kind)
        self.rows = []
        self._editor = None
        self._filtered = []

        super().__init__(master)
        self.title(store.TITLES[kind])
        self.geometry("820x560")
        self.minsize(640, 420)
        self.transient(master)

        self._build()
        self.reload()

    # ------------------------------------------------------------ 布局

    def _build(self):
        top = ttk.Frame(self, padding=(12, 10, 12, 0))
        top.pack(fill="x")
        ttk.Label(top, text="搜索：").pack(side="left")
        self.search_var = tk.StringVar()
        entry = ttk.Entry(top, textvariable=self.search_var)
        entry.pack(side="left", fill="x", expand=True, padx=(4, 0))
        self.search_var.trace_add("write", lambda *_: self._render())
        self.count_label = ttk.Label(top, text="", foreground="#666")
        self.count_label.pack(side="left", padx=(10, 0))

        wrap = ttk.Frame(self, padding=(12, 8, 12, 0))
        wrap.pack(fill="both", expand=True)
        ids = [c[0] for c in self.cols]
        self.tree = ttk.Treeview(wrap, columns=ids, show="headings", height=16)
        for c in self.cols:
            self.tree.heading(c[0], text=c[1])
            self.tree.column(c[0], width=max(c[3] * 7, 90), anchor="w")
        vsb = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(wrap, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        wrap.rowconfigure(0, weight=1)
        wrap.columnconfigure(0, weight=1)
        self.tree.bind("<Double-1>", self._begin_edit)
        self.tree.bind("<Delete>", lambda e: self._delete())

        btns = ttk.Frame(self, padding=(12, 8, 12, 12))
        btns.pack(fill="x")
        ttk.Button(btns, text="上传 Excel…", command=self._import).pack(side="left")
        ttk.Button(btns, text="导出当前数据…", command=self._export).pack(side="left", padx=(8, 0))
        ttk.Button(btns, text="新增一行", command=self._add_row).pack(side="left", padx=(8, 0))
        ttk.Button(btns, text="删除选中行", command=self._delete).pack(side="left", padx=(8, 0))
        ttk.Button(btns, text="打开数据文件", command=self._open_file).pack(side="left", padx=(8, 0))
        ttk.Button(btns, text="关闭", command=self.destroy).pack(side="right")

        hint = ttk.Frame(self, padding=(12, 0, 12, 8))
        hint.pack(fill="x")
        ttk.Label(
            hint,
            text="双击单元格可直接修改，改完回车生效并立即保存。数据文件位置：主数据\\"
                 + os.path.basename(store.data_path(self.kind)),
            foreground="#888",
        ).pack(anchor="w")

    # ------------------------------------------------------------ 数据

    def reload(self):
        try:
            self.rows = store.load_rows(self.kind)
        except store.MasterDataError as e:
            messagebox.showerror("读取失败", str(e), parent=self)
            self.rows = []
        self._render()

    def _save(self):
        try:
            store.save_rows(self.kind, self.rows)
        except store.MasterDataError as e:
            messagebox.showerror("保存失败", str(e), parent=self)
            return False
        if self.on_change:
            try:
                self.on_change()
            except Exception:
                pass
        return True

    def _render(self, select=None):
        kw = self.search_var.get().strip().lower()
        self.tree.delete(*self.tree.get_children())
        ids = [c[0] for c in self.cols]
        self._filtered = []
        for idx, r in enumerate(self.rows):
            values = [r.get(k, "") for k in ids]
            if kw and not any(kw in str(v).lower() for v in values):
                continue
            self._filtered.append(idx)
            self.tree.insert("", "end", iid=str(idx), values=values)
        self.count_label.configure(
            text=f"共 {len(self.rows)} 条" + (f"，筛选后 {len(self._filtered)} 条" if kw else "")
        )
        if select is not None and self.tree.exists(str(select)):
            self.tree.selection_set(str(select))
            self.tree.see(str(select))

    # ------------------------------------------------------------ 编辑

    def _begin_edit(self, event):
        """双击单元格 → 在该位置浮出一个输入框。"""
        region = self.tree.identify("region", event.x, event.y)
        if region != "cell":
            return
        row_id = self.tree.identify_row(event.y)
        col_id = self.tree.identify_column(event.x)
        if not row_id or not col_id:
            return
        col_idx = int(col_id.replace("#", "")) - 1
        if not (0 <= col_idx < len(self.cols)):
            return
        field = self.cols[col_idx][0]

        bbox = self.tree.bbox(row_id, col_id)
        if not bbox:
            return
        x, y, w, h = bbox
        self._close_editor()

        var = tk.StringVar(value=self.rows[int(row_id)].get(field, ""))
        ed = ttk.Entry(self.tree, textvariable=var)
        ed.place(x=x, y=y, width=w, height=h)
        ed.focus_set()
        ed.select_range(0, "end")
        self._editor = (ed, var, int(row_id), field)

        ed.bind("<Return>", lambda e: self._commit_edit())
        ed.bind("<FocusOut>", lambda e: self._commit_edit())
        ed.bind("<Escape>", lambda e: self._close_editor())

    def _close_editor(self):
        if self._editor:
            try:
                self._editor[0].destroy()
            except Exception:
                pass
            self._editor = None

    def _commit_edit(self):
        if not self._editor:
            return
        ed, var, row_idx, field = self._editor
        value = var.get().strip()
        self._editor = None
        try:
            ed.destroy()
        except Exception:
            pass

        row = self.rows[row_idx]
        if (row.get(field, "") or "") == value:
            return

        # 主键不能改成与别人重复
        if field == self.cols[0][0] and value:
            if any(i != row_idx and r.get(field, "") == value for i, r in enumerate(self.rows)):
                messagebox.showwarning("主键重复", f"「{value}」已存在，未修改。", parent=self)
                return
            if not value:
                messagebox.showwarning("主键不能为空", "主键留空则该行无法被查到，已忽略。", parent=self)
                return

        row[field] = value
        if self._save():
            self._render(select=row_idx)

    # ------------------------------------------------------------ 增删

    def _add_row(self):
        blank = {c[0]: "" for c in self.cols}
        self.rows.append(blank)
        idx = len(self.rows) - 1
        self._save()
        self.search_var.set("")
        self._render(select=idx)
        # 直接进入第一格编辑
        self.after(60, lambda: self._edit_first_cell(idx))

    def _edit_first_cell(self, row_idx):
        if not self.tree.exists(str(row_idx)):
            return
        bbox = self.tree.bbox(str(row_idx), "#1")
        if not bbox:
            return
        x, y, w, h = bbox
        field = self.cols[0][0]
        self._close_editor()
        var = tk.StringVar(value="")
        ed = ttk.Entry(self.tree, textvariable=var)
        ed.place(x=x, y=y, width=w, height=h)
        ed.focus_set()
        self._editor = (ed, var, row_idx, field)
        ed.bind("<Return>", lambda e: self._commit_edit())
        ed.bind("<FocusOut>", lambda e: self._commit_edit())
        ed.bind("<Escape>", lambda e: self._close_editor())

    def _delete(self):
        sel = [int(i) for i in self.tree.selection()]
        if not sel:
            messagebox.showinfo("未选中", "请先选中要删除的行（可按住 Ctrl 多选）。", parent=self)
            return
        if not messagebox.askyesno(
            "确认删除",
            f"确定删除 {len(sel)} 条？\n\n此操作会立即写入磁盘，无法撤销。",
            parent=self,
        ):
            return
        for i in sorted(sel, reverse=True):
            if 0 <= i < len(self.rows):
                del self.rows[i]
        self._save()
        self._render()

    # ------------------------------------------------------------ 导入 / 导出

    def _import(self):
        path = filedialog.askopenfilename(
            parent=self,
            title=f"选择{store.TITLES[self.kind]}Excel",
            filetypes=[("Excel 工作簿", "*.xlsx *.xlsm"), ("所有文件", "*.*")],
        )
        if not path:
            return
        try:
            new_rows, mapping, missing, header = importing.read_sheet(path, self.kind)
        except store.MasterDataError as e:
            messagebox.showerror("读取失败", str(e), parent=self)
            return

        if missing:
            got = "、".join(str(h) for h in header if h) or "（空表头）"
            messagebox.showerror(
                "表头不匹配",
                f"缺少必需列：{'、'.join(missing)}\n\n"
                f"文件中读到的表头：{got}\n\n"
                f"请确认：第一行是表头，且包含上述列。",
                parent=self,
            )
            return
        if not new_rows:
            messagebox.showinfo("没有数据", "表头识别成功，但表中没有有效数据行（主键列为空的行会被跳过）。", parent=self)
            return

        result = importing.compare(self.kind, new_rows, self.rows)
        if not ImportPreview(self, result).confirmed:
            return

        merged = importing.merge(self.kind, self.rows, result, overwrite=result["_overwrite"])
        self.rows = merged
        if self._save():
            self.search_var.set("")
            self._render()
            messagebox.showinfo(
                "导入完成",
                f"新增 {len(result['to_add'])} 条，"
                f"{'覆盖' if result['_overwrite'] else '跳过'}冲突 {len(result['conflicts'])} 条，"
                f"相同跳过 {result['same']} 条。\n\n当前共 {len(self.rows)} 条。",
                parent=self,
            )

    def _export(self):
        default = os.path.basename(store.data_path(self.kind))
        path = filedialog.asksaveasfilename(
            parent=self,
            title="导出主数据",
            defaultextension=".xlsx",
            initialfile=default,
            filetypes=[("Excel 工作簿", "*.xlsx")],
        )
        if not path:
            return
        try:
            _write_rows(path, self.kind, self.rows)
        except Exception as e:
            messagebox.showerror("导出失败", str(e), parent=self)
            return
        messagebox.showinfo("已导出", f"已保存到：\n{path}", parent=self)

    def _open_file(self):
        path = store.data_path(self.kind)
        if not os.path.isfile(path):
            messagebox.showinfo("文件不存在", f"还没有数据文件：\n{path}", parent=self)
            return
        try:
            os.startfile(path)  # noqa: S606
        except Exception as e:
            messagebox.showerror("打不开", f"{e}\n\n文件位置：\n{path}", parent=self)


def _write_rows(path, kind, rows):
    """把行写到指定路径（复用 store 的样式逻辑，只改目标文件）。"""
    import openpyxl
    from openpyxl.styles import Font, PatternFill

    cols = store.column_defs(kind)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = store._SHEET_NAMES[kind]
    ws.append([c[1] for c in cols])
    for j, c in enumerate(cols, 1):
        cell = ws.cell(row=1, column=j)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="3B5BA5")
        ws.column_dimensions[cell.column_letter].width = c[3] or 16
    for r in rows:
        ws.append([r.get(c[0], "") or "" for c in cols])
    for row in ws.iter_rows(min_row=2, min_col=1, max_col=1):
        for cell in row:
            cell.number_format = "@"
    wb.save(path)


class ImportPreview(tk.Toplevel):
    """导入前预览：新增 / 冲突 / 相同各多少，并选择冲突怎么处理。"""

    def __init__(self, master, result):
        super().__init__(master)
        self.result = result
        self.confirmed = False
        self.title("导入预览")
        self.geometry("720x480")
        self.transient(master)
        self.grab_set()

        p = ttk.Frame(self, padding=14)
        p.pack(fill="both", expand=True)

        ttk.Label(
            p,
            text=(f"读取到 {len(result['to_add']) + len(result['conflicts']) + result['same']} 行\n"
                  f"  新增 {len(result['to_add'])} 条\n"
                  f"  冲突 {len(result['conflicts'])} 条（已存在且内容不同）\n"
                  f"  相同 {result['same']} 条（自动跳过）"
                  + (f"\n  文件内主键重复 {result['dup_in_file']} 处（以最后一行为准）"
                     if result["dup_in_file"] else "")),
            justify="left",
        ).pack(anchor="w")

        if result["conflicts"]:
            ttk.Label(p, text="冲突明细（前 20 条）：", foreground="#B9770E").pack(anchor="w", pady=(10, 4))
            wrap = ttk.Frame(p)
            wrap.pack(fill="both", expand=True)
            tree = ttk.Treeview(wrap, columns=("key", "diff", "old", "new"), show="headings", height=10)
            for cid, txt, w in (("key", "主键", 120), ("diff", "差异列", 100),
                                ("old", "现有值", 200), ("new", "导入值", 200)):
                tree.heading(cid, text=txt)
                tree.column(cid, width=w, anchor="w")
            for old, new, diff in result["conflicts"][:20]:
                key = next(iter(new.values()), "")
                tree.insert("", "end", values=(
                    key, "、".join(diff),
                    " / ".join(old.get(f, "") for f in diff),
                    " / ".join(new.get(f, "") for f in diff),
                ))
            sb = ttk.Scrollbar(wrap, orient="vertical", command=tree.yview)
            tree.configure(yscrollcommand=sb.set)
            tree.pack(side="left", fill="both", expand=True)
            sb.pack(side="right", fill="y")

        self.overwrite = tk.BooleanVar(value=False)
        opt = ttk.Frame(p)
        opt.pack(fill="x", pady=(10, 0))
        ttk.Radiobutton(opt, text="跳过冲突（保留现有值）", variable=self.overwrite, value=False).pack(side="left")
        ttk.Radiobutton(opt, text="用导入值覆盖冲突", variable=self.overwrite, value=True).pack(side="left", padx=(16, 0))

        bar = ttk.Frame(p)
        bar.pack(fill="x", pady=(12, 0))
        ttk.Button(bar, text="取消", command=self.destroy).pack(side="right")
        ttk.Button(bar, text="确认导入", command=self._ok).pack(side="right", padx=(0, 8))
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.wait_window(self)

    def _ok(self):
        self.result["_overwrite"] = bool(self.overwrite.get())
        self.confirmed = True
        self.destroy()
