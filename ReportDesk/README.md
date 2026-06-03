# ReportDesk — 报告批量整理（tkinter + SQLite）

桌面应用：选择报告图片 → QR/OCR 识别 → 爬取（协会 / 院网 / 内网 LIMIS）→ SQLite 入库 → 复制到规范目录。

与 [ScanReport](../ScanReport/) 共用解码与爬取逻辑，与 [LimisQuery](../LimisQuery/) 共用内网客户端；**不复制** scrape 实现。

## 目录结构（输出）

用户可在设置中选择**输出根目录**（写入 `app_settings.output_root`）：

```text
{output_root}/报告/{工程名称}/{报告编号}-1.jpg          ← 无标段（院网/内网等）
{output_root}/报告/{工程名称}/{标段}/{报告编号}-1.jpg   ← 协会有标段时
```

- **同编号多文件**：始终带 `-1`、`-2`、`-3` 后缀（第一张也是 `-1`）。
- **标段**：仅协会有效 `project_section` 才多一层 `{标段}/`；院网、内网文件直接放在 `{工程名称}/` 下（部位记在库表 `project_part`，不进路径）。
- **爬取失败仅有编号**：复制到 `报告/_待核实/{编号}-N.ext`。
- **默认复制**，不移动原图。

## 数据库

默认路径：`ReportDesk/data/reportdesk.db`（可在设置中修改）。

主要表：`reports`（`report_no` UNIQUE 大写）、`report_files`、`report_samples`、`report_tasks`、`report_audit_history`、`integrated_list_row`、`batch_jobs`、`batch_job_items`、`app_settings`。

## 界面

应用含两个标签页：**整理**、**查询**。

### 查询页

按委托编号、报告编号、工程名称、样品名称模糊搜索；报告日期起止用**日历控件**选择；列表**点击列头**排序（↑/↓ 切换）。报告日期统一显示为 `YYYY-MM-DD`。点击结果行，底部预览图片（需已整理入库且文件路径有效）。

### 整理页

- **左侧**：待处理列表；Windows 可拖入文件/文件夹（`windnd`）。
- **中间**：报告预览 + 流水线进度条；**开始流水线**（逐个模式）自动识别→爬取→入库→下一张。
- **右侧**：七项字段 + 底部 OCR 内容；可手动「识别并爬取 / 完成并下一份」。
- **后台批量**：切换模式后 **开始批量**，进程数 5–10，多进程并行。

协会 OCR 编号含 0/O、1/l、5/S 等易混字时，爬取会自动单字符替换重试。

## 合同工程表（`project_contracts`）

- 列：**项目名称**、**负责人**、**经办人**（与根目录 `合同.xlsx` 一致）
- 设置 → **导入合同表到数据库**；首次启动若表为空会自动尝试导入 `limis-api/合同.xlsx`
- **工程目录上级**：`无` / `负责人` / `经办人` — 仅当爬取到的**工程名称与表中完全一致**时，输出路径为  
  `报告/{负责人或经办人}/{工程名称}/[标段/]{编号}-N.jpg`

## 设置（GUI）

- LIMIS 地址 / 用户名 / 密码 / `auth_type`（存于 `app_settings`，**v1 明文**，勿提交仓库）
- **工程目录上级**、**合同表 Excel** 路径与导入
- RapidOCR-json 目录（默认 `ScanReport/tools/RapidOCR-json`）
- QR 权重目录（默认 ScanReport 根目录）
- 输出根目录、数据库路径（高级）

## 运行

```bash
cd code_base
# 建议使用已有 venv
venv\Scripts\activate
pip install -r ReportDesk/requirements.txt
pip install -r ScanReport/requirements.txt
pip install -r LimisQuery/requirements.txt

python ReportDesk/app.py
```

环境变量（可选，与 ScanReport/LimisQuery 一致）：`LIMIS_BASE`、`LIMIS_USER`、`LIMIS_PASSWORD`、`LIMIS_AUTH_TYPE`、`RAPID_OCR_JSON`、`REPORTDESK_DB`。

## 测试

```bash
cd code_base
python -m unittest ReportDesk.tests.test_core -v
python -c "import sys; sys.path.insert(0,'ReportDesk'); from gui.main_window import MainWindow; print('import ok')"
```

手工集成（需内网 / 外网可达）：

```bash
# GUI 中添加 ScanReport/report/1.jpg、test2.jpg 等，指定输出目录后开始整理
```

## 依赖说明

- **torch / qreader**：ScanReport QR 检测
- **requests / bs4 / lxml**：爬取
- **tkinter**：Python 标准库（Windows 安装包通常已带）
- **Pillow / windnd**：预览与 Windows 拖放

## 安全提示

内网账号密码保存在本地 SQLite 明文中，仅用于本机批处理；请勿将 `data/reportdesk.db` 或含密码的备份提交到 git。
