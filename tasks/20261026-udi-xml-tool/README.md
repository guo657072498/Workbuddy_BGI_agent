# UDI XML 转 Excel

| 项 | 内容 |
|---|---|
| 创建日期 | 2026-10-26 |
| 类型 | 代码 |
| 状态 | 已完成 |
| 一句话说明 | UDI 系统 XML 转 Excel，免安装 exe，支持压缩包批量 |

**交付物**：`dist\UDI转换工具.exe`（14 MB 单文件，双击即用，目标机器无需装 Python）

把 UDI 系统收到的 XML 转成 Excel 明细行。提供两种形态：

- **免安装 exe**（给用户用）：`dist\UDI转换工具.exe`，单个文件，双击即用
- **源码版**（自己维护）：`python run.py`，便于改字段和调试

## 给用户：使用 exe

双击 `UDI转换工具.exe`，把文件拖进窗口，点「开始转换」。

**能拖什么**

| 类型 | 说明 |
|---|---|
| `.xml` 文件 | 直接处理，可一次拖多个 |
| `.zip` 压缩包 | 自动展开，里面的 xml 全部处理（含子目录） |
| 文件夹 | 递归查找里面的 xml 和 zip |

- 压缩包**不需要手动解压**，程序在内存里直接读
- 结果默认输出到 exe 同目录的 `输出结果\`，可在界面上改
- 一个 xml 对应一个 Excel，同名文件自动加序号，不覆盖已有结果
- 转换完会问要不要打开输出目录

**不支持**：`.rar`、`.7z`（会提示改为 zip 或先手动解压）

## 两种文件类型

类型靠 XML 的 schema 声明 + 结构双重判断，不看文件名。

| 类型 | schema 声明 | 结构 | Sheet |
|---|---|---|---|
| 出入库单 | `终端接口XML Schema-3.0.xsd` | DocHeader + HasProducts + Data | 出入库明细 / 产品汇总 / 校验 |
| 生产入库单 | `关联关系XML Schema-3.0.xsd` | Relation + Batch + Code | 盒明细 / 箱汇总 / 码清单 / 校验 |

## 解析要点

### 生产入库单的码顺序

码按 **先箱码、后跟该箱内的盒码** 排列，盒码的 `parentCode` 指向当前箱码。

程序严格按 XML 原始顺序切块（遇 `packLayer=2` 开新箱块），**不靠流水号推箱内成员**——
实测箱1 流水 209~285、箱2 为 282~358，两者重叠且跳号，用流水号会算错。

`cascade="1:160"` 是标称值，与实际装箱数（75/25）不符，只原样展示、不参与计算，
在「校验」sheet 里给一条提示。

### 30 位码必须存文本

码一律按文本写入（单元格 `@` 格式），否则 Excel 会转成科学计数法导致精度丢失。
写盘后会回读校验，确认码仍是 30 位文本，不通过会在界面标黄并在日志里报警。

### 交叉关联

出库单的码去入库单里找所属箱码，采用「有则填、无则空」。
找不到只记提示级，不算错误。

## 调整 Excel 字段

**只改 `config/columns.py`**，改完重新打包即可，不用动解析代码。

列元组：`(字段名, 表头, 类型, 宽度)`

- `text`：文本，强制 `@` 格式（**码必须用这个**）
- `auto`：数字或文本自动判断（序号、数量）
- `date`：日期，已归一化为 `YYYY-MM-DD`

删一行即隐藏该列；调顺序即调表头顺序。

## 源码版用法

```bat
python run.py <文件或目录> [-o 输出目录] [-e auto|openpyxl|stdlib]
```

也可以双击 `一键转换.bat` 后拖文件进去。

## 重新打包

双击 `打包exe.bat`，或手动：

```bat
py -3.14 -m PyInstaller --noconfirm --clean udi_tool.spec
```

产物在 `dist\UDI转换工具.exe`（约 14 MB，单文件，无需 Python 环境）。

打包注意事项（踩过的坑）：

1. **`udi_parser/__init__.py` 不能是空文件**——空 `__init__.py` 会被当成命名空间包，
   PyInstaller 会漏收子模块，运行时抛 `No module named 'udi_parser.source'`。
   现在里面显式 import 了所有子模块。
2. **spec 里 datas 必须是 3 元组**（`目标路径, 源路径, "DATA"`），
   PyInstaller 6.x 不接受 2 元组。
3. **日志回调抛异常不能中断转换**——`converter._log` 已包 try/except，
   避免控制台编码不支持某字符时整批失败。

## 自检模式

打包后想验证 exe 是否正常，可不打开界面直接跑一次转换：

```bat
set UDI_SELFTEST=D:\out
set UDI_SELFTEST_IN=D:\some\test.zip
UDI转换工具.exe
```

会打印解析结果和自检结论后退出，适合发给用户前先自己验一遍。

## 目录结构

```
tasks/20261026-udi-xml-tool/
├── README.md             本文件
├── gui.py                图形界面入口
├── run.py                命令行入口
├── converter.py          转换核心（界面与命令行共用）
├── config/columns.py     列定义 ← 改字段只改这里
├── udi_parser/
│   ├── detect.py         类型识别
│   ├── source.py         输入展开（xml / zip / 文件夹）
│   ├── parse_bill.py     出入库单解析
│   ├── parse_relation.py 生产入库单解析（顺序切块）
│   ├── flatten.py        扁平化成行
│   ├── validate.py       单人校验
│   ├── crosscheck.py     跨文件交叉校验
│   └── models.py         数据结构
├── xlsx/
│   ├── writer.py         两条写出通道（openpyxl / 零依赖）
│   └── verify.py         写盘自检
├── udi_tool.spec         打包配置
├── 打包exe.bat           一键打包
├── 一键转换.bat          源码版双击运行
├── dist/                 最终产物（入库）
│   └── UDI转换工具.exe
├── output/               命令行运行产物（不入库）
└── 输出结果/             exe 默认输出目录（不入库）
```

## 说明与遗留

**迁移期豁免**：本任务创建于项目规范建立之前，源码直接放在任务根目录，未迁入 `src/`。
按 `AGENTS.md` 的约定，老任务保持原样，不为整齐而做大重构。

**已知限制**：不支持 `.rar` / `.7z` 压缩包，遇到会提示改用 zip 或先手动解压。

**cascade 字段待确认**：入库单里 `cascade="1:160"`，实测每箱 75 或 25 盒，两者不符。
程序只把它原样展示、不参与计算，并在「校验」sheet 给一条提示。
如果业务上确实应该是每箱 160，这可能是数据源的问题，需要回查。


## 校验规则

| 规则 | 级别 | 含义 |
|---|---|---|
| A_AMOUNT_MISMATCH | 警告 | 产品声明数量 ≠ 实际明细条数 |
| A_UNDECLARED_PRODUCT | 警告 | 明细里有产品但 HasProducts 未声明 |
| A_DUP_CODE | 错误 | 同单内 UDI 码重复 |
| A_CODE_FORMAT | 警告 | 码不是 30 位纯数字 |
| B_PARENT_MISMATCH | 错误 | 盒码 parent 与当前箱码不一致 |
| B_LEADING_ITEM | 错误 | 盒码出现在任何箱码之前 |
| B_DUP_CODE | 错误 | 码重复 |
| B_EMPTY_BOX | 警告 | 箱码下没有盒码 |
| B_ORPHAN_PARENT | 错误 | parent 指向不存在的箱码 |
| B_CODE_FORMAT | 警告 | 码不是 30 位纯数字 |
| B_CASCADE_INFO | 提示 | cascade 标称比例与实际不符（不参与计算） |
| X_NO_LINK | 提示 | 出库码在入库单中找不到所属箱码 |
