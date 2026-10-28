"""列定义 —— 唯一需要修改的文件。

调整 Excel 的字段、顺序、宽度、表头，只改本文件，不必动解析或写出代码。

列元组格式：(字段名, 表头显示名, 类型, 宽度)
    字段名   —— flatten.py 里产出的 key
    表头     —— Excel 显示的文字
    类型     —— "text" 文本（强制左对齐 + 文本格式，码必须用它）
                "int"  整数
                "date" 日期（YYYY-MM-DD）
                "auto" 让 Excel 自动判断（数量、序号等）
    宽度     —— 列宽（字符数），None 表示默认

想隐藏某列：直接删掉那一行即可，不会影响解析。
"""

# ============================================================ 生产入库单（文件B）
# 每盒一行
BOX_ITEM_COLUMNS = [
    ("seq",           "序号",       "auto", 8),
    ("box_no",        "箱序号",     "auto", 8),
    ("box_code",      "箱码",       "text", 32),
    ("item_no",       "箱内序号",   "auto", 10),
    ("code",          "盒码",       "text", 32),
    ("product_code",  "产品码",     "text", 18),
    ("package_spec",  "规格",       "text", 22),
    ("pack_flag",     "包装标识",   "text", 10),
    ("serial",        "流水号",     "text", 15),
    ("batch_no",      "批次号",     "text", 16),
    ("made_date",     "生产日期",   "date", 12),
    ("validate_date", "失效日期",   "date", 12),
    ("work_order",    "工单号",     "text", 15),
    ("workshop",      "车间",       "text", 10),
    ("line_name",     "生产线",     "text", 10),
    ("cascade",       "标称比例",   "text", 10),
    ("file",          "来源文件",   "text", 38),
]

# 每箱一行
BOX_COLUMNS = [
    ("seq",           "序号",       "auto", 8),
    ("box_code",      "箱码",       "text", 32),
    ("box_count",     "箱内盒数",   "auto", 10),
    ("product_code",  "产品码",     "text", 18),
    ("package_spec",  "规格",       "text", 22),
    ("batch_no",      "批次号",     "text", 16),
    ("made_date",     "生产日期",   "date", 12),
    ("validate_date", "失效日期",   "date", 12),
    ("work_order",    "工单号",     "text", 15),
    ("serial_min",    "最小流水",   "text", 12),
    ("serial_max",    "最大流水",   "text", 12),
    ("first_code",    "首盒码",     "text", 32),
    ("last_code",     "末盒码",     "text", 32),
    ("start_seq",     "起始位置",   "auto", 10),
    ("end_seq",       "结束位置",   "auto", 10),
    ("cascade",       "标称比例",   "text", 10),
    ("file",          "来源文件",   "text", 38),
]

# 全量码清单
CODE_ALL_COLUMNS = [
    ("seq_in_file",   "文件内序号", "auto", 10),
    ("code",          "UDI码",      "text", 32),
    ("layer_name",    "层级",       "text", 8),
    ("parent_code",   "父码(箱码)", "text", 32),
    ("product_code",  "产品码",     "text", 18),
    ("pack_flag",     "包装标识",   "text", 10),
    ("serial",        "流水号",     "text", 15),
    ("batch_no",      "批次号",     "text", 16),
    ("work_order",    "工单号",     "text", 15),
    ("flag",          "标记",       "text", 8),
    ("status",        "状态",       "text", 8),
    ("print_count",   "打印次数",   "auto", 10),
    ("file",          "来源文件",   "text", 38),
]

# ============================================================ 出入库单（文件A）

# ============================================================ 销售出库单（文件A）

# 8 列。已按业务要求精简：原「业务方向/单据类型/三个时间/包装标识/流水号/单位/
# 声明数量/操作人/关联单号/错码标记/事件/来源文件」全部去掉。
# 「成品名称、规格(型号)」由产品主数据按 DI码 查出；
# 「供货者、客户名称」由法人主数据按机构编码查出。
BILL_COLUMNS = [
    ("seq",           "序号",       "auto", 8),
    ("store_no",      "DN号",       "text", 22),
    ("product_code",  "DI码",       "text", 18),
    ("prod_name",     "成品名称",   "text", 30),
    ("prod_spec",     "规格(型号)", "text", 26),
    ("code",          "UDI码",      "text", 32),
    ("owner_name",    "供货者",     "text", 26),
    ("customer_name", "客户名称",   "text", 26),
]

ISSUE_COLUMNS = [
    ("level",    "级别", "text", 8),
    ("rule",     "规则", "text", 26),
    ("location", "位置", "text", 40),
    ("message",  "说明", "text", 80),
]

# ============================================================ 主数据

# 产品主数据：DI码为主键，对应模板列的「最小销售单元产品标识（UDI）」。
# 模板 7 列全存着，输出 Excel 只用到 prod_name（成品名称）和 spec（规格(型号)）。
# 其余 4 列保留是为了「导入不丢数据」，以后想在输出里加列，直接改 BILL_COLUMNS 即可。
MASTER_PRODUCT_COLUMNS = [
    ("di_code",        "最小销售单元产品标识（UDI）", "text", 24),
    ("box_code",       "大箱标识",                    "text", 24),
    ("sap_code",       "SAP编码",                     "text", 16),
    ("prod_name",      "产品名称/通用名称",           "text", 32),
    ("spec",           "规格型号",                    "text", 32),
    ("storage_cond",   "特殊储存或操作条件",          "text", 24),
    ("category",       "分类",                        "text", 10),
]

# 法人主数据：法人编码为主键（XML 里是 OwnerCorpID / ToCorpID 的形式，如 A100）
MASTER_CORP_COLUMNS = [
    ("corp_code", "法人编码", "text", 16),
    ("corp_name", "法人名称", "text", 40),
]

# ============================================================ Sheet 名称与顺序

SHEETS_RELATION = [
    ("盒明细", BOX_ITEM_COLUMNS),
    ("箱汇总", BOX_COLUMNS),
    ("码清单", CODE_ALL_COLUMNS),
    ("校验",   ISSUE_COLUMNS),
]

SHEETS_BILL = [
    ("销售出库明细", BILL_COLUMNS),
    ("校验",         ISSUE_COLUMNS),
]

# 判定为"错误"时是否用红底标出（写盘不改数据，只改样式）
HIGHLIGHT_ERROR = True
