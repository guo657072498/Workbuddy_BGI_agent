"""统一输入源：把「用户拖进来的东西」变成一组待处理的 XML 数据源。

支持：
    .xml              直接读取
    .zip              自动展开，递归找内层 xml（兼容内层文件夹、多个 xml、中文名）
    .rar / .7z        检测到但没有解压能力时，给出明确提示而不是静默失败
    文件夹            递归查找 xml / zip

关键设计：压缩包内的 xml **不解压到磁盘**，而是以字节流直接交给解析器，
这样处理 100 个压缩包也不会在临时目录留下垃圾。
"""

import os
import zipfile

XML_EXT = (".xml",)
ARCHIVE_EXT = (".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz")
SUPPORTED_ARCHIVE = (".zip",)


class XmlSource:
    """一个待解析的 XML。可能来自磁盘文件，也可能来自压缩包内部。"""

    def __init__(self, display_name, data=None, path=None, origin=""):
        self.display_name = display_name   # 展示给用户的名称
        self.data = data                   # bytes；为 None 时读 path
        self.path = path                   # 磁盘路径
        self.origin = origin               # 来源（压缩包名或所在目录）
        self._root = None
        self.error = ""

    def read(self):
        if self.data is not None:
            return self.data
        with open(self.path, "rb") as f:
            return f.read()

    def __repr__(self):
        return f"<XmlSource {self.display_name}>"


def is_xml(name):
    return name.lower().endswith(XML_EXT)


def is_archive(name):
    return name.lower().endswith(ARCHIVE_EXT)


# ---------------------------------------------------------------- 单个输入

def _from_zip(zip_path, base_origin=None):
    """展开一个 zip，返回 (sources, 错误列表)。"""
    sources, errors = [], []
    label = base_origin or os.path.basename(zip_path)
    try:
        with zipfile.ZipFile(zip_path) as z:
            bad = z.testzip()
            if bad:
                errors.append(f"{label}：压缩包内文件 {bad} 已损坏")
            for info in z.infolist():
                if info.is_dir():
                    continue
                # 兼容 GBK 文件名：部分系统打的包不带 UTF-8 标记
                filename = _fix_zip_name(info)
                if not is_xml(filename):
                    continue
                # 跳过明显的系统垃圾文件
                if os.path.basename(filename).startswith(("._", "~$")):
                    continue
                try:
                    data = z.read(info)
                except Exception as e:
                    errors.append(f"{label} / {filename}：读取失败（{e}）")
                    continue
                # 内层显示名：去掉压缩包内的目录前缀，冲突时保留相对路径
                sources.append(XmlSource(
                    display_name=label + " › " + filename.replace("\\", "/"),
                    data=data,
                    origin=label,
                ))
    except zipfile.BadZipFile:
        errors.append(f"{label}：不是有效的 zip（可能扩展名写错，或是分卷/RAR 改扩展名）")
    except PermissionError:
        errors.append(f"{label}：没有读取权限")
    except Exception as e:
        errors.append(f"{label}：打开失败（{e}）")
    return sources, errors


def _fix_zip_name(info):
    """zip 里的文件名编码修正。"""
    name = info.filename
    # 有 UTF-8 标记就原样用；否则尝试按 cp437 还原成 GBK
    if not (info.flag_bits & 0x800):
        try:
            raw = name.encode("cp437")
            for enc in ("gbk", "utf-8"):
                try:
                    name = raw.decode(enc)
                    break
                except UnicodeDecodeError:
                    continue
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass
    return name


def _from_archive_unsupported(path, label=None):
    label = label or os.path.basename(path)
    ext = os.path.splitext(path)[1].lower()
    if ext in (".rar", ".7z"):
        return [], [f"{label}：暂不支持 {ext} 格式，请用 zip 打包，"
                     f"或先手动解压后把 xml 拖进来"]
    return [], [f"{label}：暂不支持 {ext} 格式，请用 zip 打包，或手动解压后拖入 xml"]


def _walk_dir(dir_path):
    sources, errors = [], []
    for root, dirs, files in os.walk(dir_path):
        dirs[:] = [d for d in dirs if not d.startswith((".", "__MACOSX"))]
        for fn in sorted(files):
            full = os.path.join(root, fn)
            if is_xml(fn):
                sources.append(XmlSource(display_name=os.path.relpath(full, dir_path), path=full, origin=dir_path))
            elif fn.lower().endswith(SUPPORTED_ARCHIVE):
                s, e = _from_zip(full)
                sources.extend(s)
                errors.extend(e)
            elif is_archive(fn):
                s, e = _from_archive_unsupported(full)
                errors.extend(e)
    return sources, errors


# ---------------------------------------------------------------- 对外入口

def expand(paths):
    """把路径列表展开成 (XmlSource 列表, 全局错误列表)。"""
    sources, errors = [], []
    seen_zip = set()

    for p in paths:
        if not os.path.exists(p):
            errors.append(f"{os.path.basename(p)}：找不到该文件")
            continue

        if os.path.isdir(p):
            s, e = _walk_dir(p)
            sources.extend(s)
            errors.extend(e)
            continue

        name = os.path.basename(p)
        low = name.lower()
        if is_xml(low):
            sources.append(XmlSource(display_name=name, path=p, origin=os.path.dirname(p)))
        elif low.endswith(SUPPORTED_ARCHIVE):
            ap = os.path.abspath(p)
            if ap in seen_zip:
                continue
            seen_zip.add(ap)
            s, e = _from_zip(p)
            sources.extend(s)
            errors.extend(e)
        elif is_archive(low):
            s, e = _from_archive_unsupported(p)
            errors.extend(e)
        else:
            errors.append(f"{name}：不是 xml 也不是压缩包，已跳过")

    return sources, errors


def summarize(sources, errors):
    """给日志用的一行摘要。"""
    parts = [f"待处理 {len(sources)} 个 xml"]
    if errors:
        parts.append(f"{len(errors)} 条提示")
    return "，".join(parts)
