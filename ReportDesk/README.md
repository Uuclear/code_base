# ReportDesk — 报告批量整理（tkinter + SQLite）

桌面应用：报告图片 → QR/OCR 识别 → 爬取（协会 / 院网 / 内网 LIMIS）→ SQLite 入库 → 按规则复制到目录。

- 代码仓库：<https://github.com/Uuclear/code_base>
- 本应用路径：仓库内的 **`ReportDesk/`**（与 [`ScanReport`](../ScanReport/)、[`LimisQuery`](../LimisQuery/) 同级）
- 入口文件：**`ReportDesk/app.py`**
- 平台：**Windows 10/11**（拖放、tkinter GUI）

---

## 给 AI / 自动化代理：部署与运行清单

> 按顺序执行下列步骤；`REPO_ROOT` 指克隆后的 **`code_base`** 目录绝对路径。  
> 所有 shell 命令默认在 **`REPO_ROOT`** 下执行。成功标准见每节 **预期结果**。

| 变量 | 值 |
|------|-----|
| `REPO_ROOT` | 例如 `C:\work\code_base`（`git clone` 后的根目录） |
| `VENV_PYTHON` | `{REPO_ROOT}\venv\Scripts\python.exe` |
| `APP_ENTRY` | `{REPO_ROOT}\ReportDesk\app.py` |
| `SCAN_REPORT` | `{REPO_ROOT}\ScanReport` |
| `DEFAULT_DB` | `{REPO_ROOT}\ReportDesk\data\reportdesk.db` |

### 前置条件（必须满足）

- [ ] OS = Windows，已安装 **Python 3.10+**（建议 3.12），且安装包包含 **tcl/tk**
- [ ] 已安装 **git**
- [ ] 磁盘可用 ≥ 4 GB（PyTorch CPU + 依赖）
- [ ] 克隆后存在 `{SCAN_REPORT}\qrdet-*.pt`（QR 权重，一般已在仓库中）
- [ ] （推荐）已解压 [RapidOCR-json](https://github.com/hiroi-sora/RapidOCR-json) 到 `{SCAN_REPORT}\tools\RapidOCR-json`

### 步骤 A — 克隆

```powershell
git clone https://github.com/Uuclear/code_base.git
cd code_base
```

**预期结果**：当前目录为 `REPO_ROOT`，且存在子目录 `ReportDesk`、`ScanReport`、`LimisQuery`。

### 步骤 B — 虚拟环境与依赖（在 `REPO_ROOT`）

```powershell
python -m venv venv
.\venv\Scripts\python.exe -m pip install --upgrade pip
.\venv\Scripts\python.exe -m pip install torch --index-url https://download.pytorch.org/whl/cpu
.\venv\Scripts\python.exe -m pip install -r ScanReport\requirements.txt
.\venv\Scripts\python.exe -m pip install -r LimisQuery\requirements.txt
.\venv\Scripts\python.exe -m pip install -r ReportDesk\requirements.txt
```

**预期结果**：`.\venv\Scripts\python.exe -c "import torch, tkinter, PIL, windnd; print('deps ok')"` 输出 `deps ok`（`windnd` 仅 Windows）。

### 步骤 C — 验证（仍在 `REPO_ROOT`）

```powershell
.\venv\Scripts\python.exe -m unittest ReportDesk.tests.test_core -v
.\venv\Scripts\python.exe -c "import sys; sys.path.insert(0,'ReportDesk'); from gui.main_window import MainWindow; print('import ok')"
```

**预期结果**：单元测试通过；第二行打印 `import ok`。

### 步骤 D — 启动 GUI

```powershell
.\venv\Scripts\python.exe ReportDesk\app.py
```

**预期结果**：

1. 出现标题含 **ReportDesk** 的窗口（标签页：**整理**、**查询**）。
2. 启动约 0.5s 后，底部日志出现 **`QR 识别模型已就绪`**（主线程加载 PyTorch/QReader）。
3. **在此日志出现之前**，不要大批量拖入图片（否则可能 GIL 崩溃）。

### 步骤 E — 最小冒烟（可选，需外网或内网）

1. 菜单或 **设置** 中指定 **输出根目录**（任意可写文件夹）。
2. **整理** 页 → **添加文件** → 选择 `{SCAN_REPORT}\report\1.jpg`（或任意报告样图）。
3. 点击列表中该文件 → 等待右侧字段填充；或点 **开始流水线** 自动识别→爬取→入库。

**预期结果**：预览区显示图片；成功时文件复制到 `{输出根目录}\报告\...` 且日志无未处理异常。

### 一键部署脚本（PowerShell，AI 可整段执行）

将 `REPO_ROOT` 设为克隆目标父目录下的 `code_base`，或 clone 后 `cd` 进入：

```powershell
$ErrorActionPreference = "Stop"
if (-not (Test-Path "ScanReport")) {
  git clone https://github.com/Uuclear/code_base.git
  Set-Location code_base
}
$py = ".\venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
  python -m venv venv
  & $py -m pip install --upgrade pip
  & $py -m pip install torch --index-url https://download.pytorch.org/whl/cpu
  & $py -m pip install -r ScanReport\requirements.txt
  & $py -m pip install -r LimisQuery\requirements.txt
  & $py -m pip install -r ReportDesk\requirements.txt
}
& $py -m unittest ReportDesk.tests.test_core -v
& $py ReportDesk\app.py
```

### 禁止事项（自动化时注意）

- 不要将 `ReportDesk/data/reportdesk.db`、`.env`、含密码的备份提交到 git。
- 不要在后台线程首次 `import torch` / 加载 QReader；应用已在主线程预热。
- 合同表 `合同.xlsx` **不在** git 仓库内，需用户单独提供或跳过合同功能。

---

## 简介

ReportDesk 是 Windows 桌面工具，面向检测检验报告图片的批量整理：

| 能力 | 说明 |
|------|------|
| 识别 | QR（QReader/torch）+ 可选 RapidOCR |
| 爬取 | 协会、院网、内网 LIMIS（逻辑复用 ScanReport，不重复实现） |
| 入库 | SQLite，支持查询、排序、预览 |
| 归档 | 按工程名、标段、报告编号复制到规范目录 |
| 合同表 | 可选 Excel 导入，按负责人/经办人加一级目录 |

---

## 环境要求

| 项 | 要求 |
|----|------|
| 操作系统 | Windows 10/11 |
| Python | 3.10+（建议 3.12），含 **tcl/tk** |
| 网络 | 协会/院网需外网；内网报告需能访问 LIMIS（默认 `http://10.1.228.22`） |
| 磁盘 | 约 2–4 GB（venv + PyTorch CPU） |
| 可选 | `合同.xlsx`（列：项目名称、负责人、经办人） |

---

## 从零部署（人类可读分步）

### 1. 克隆仓库

```powershell
git clone https://github.com/Uuclear/code_base.git
cd code_base
```

SSH：`git clone git@github.com:Uuclear/code_base.git`

### 2. 创建 venv 并安装依赖

在 **`code_base`** 根目录：

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1

pip install --upgrade pip
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r ScanReport\requirements.txt
pip install -r LimisQuery\requirements.txt
pip install -r ReportDesk\requirements.txt
```

> 三个 `requirements.txt` 共用同一 venv。必须先装 **torch**，再装 ScanReport/ReportDesk（含 qreader、opencv）。

### 3. ScanReport 资源

| 资源 | 路径 | 说明 |
|------|------|------|
| QR 权重 | `ScanReport\qrdet-*.pt` | 克隆后通常已有 |
| RapidOCR-json | `ScanReport\tools\RapidOCR-json\` | [下载](https://github.com/hiroi-sora/RapidOCR-json) 解压；无二维码图片需 OCR 时必填 |
| 样例图片 | `ScanReport\report\*.jpg` | 用于测试 |

验证权重：

```powershell
Get-ChildItem ScanReport\qrdet-*.pt
```

### 4. 合同表（可选）

`合同.xlsx` **不在** GitHub 仓库中。任选其一：

- 将文件放到 `code_base` 的上一级并命名为 `合同.xlsx`（即与 `code_base` 同级的 `limis-api/合同.xlsx` 布局），或
- 启动应用 → **设置** → 选择 Excel → **导入合同表到数据库**

### 5. 启动

```powershell
cd code_base
.\venv\Scripts\python.exe ReportDesk\app.py
```

等待日志：**`QR 识别模型已就绪`**。

---

## 首次配置（设置对话框）

菜单或工具栏打开 **设置**：

| 设置项 | 键名 | 默认 / 说明 |
|--------|------|-------------|
| LIMIS 地址 | `limis_base` | `http://10.1.228.22` |
| LIMIS 用户名 | `limis_user` | 内网账号 |
| LIMIS 密码 | `limis_password` | 仅存本地 DB，明文 v1 |
| authType | `limis_auth_type` | `1` |
| RapidOCR 目录 | `rapidocr_dir` | `ScanReport\tools\RapidOCR-json` |
| QR 权重目录 | `scanreport_weights_dir` | `ScanReport\` |
| 输出根目录 | `output_root` | **必填**，整理后文件复制目标 |
| 数据库路径 | `db_path` | `ReportDesk\data\reportdesk.db` |
| 工程目录上级 | `organize_folder_parent` | `无` / `负责人` / `经办人` |
| 合同表路径 | `contracts_excel_path` | 可选 |

保存后写入 SQLite 表 `app_settings`。

---

## 日常使用

### 界面概览

两个标签页：

1. **整理** — 批量处理待办图片  
2. **查询** — 检索已入库报告、预览、列头排序

### 整理页工作流

```
添加图片（拖放 / 添加文件 / 添加文件夹）
    → 点击列表项预览（逐个模式）
    → 「识别并爬取」或「开始流水线」
    → 核对右侧七项字段 + OCR 区
    → 「完成并下一份」或流水线自动下一张
```

| 操作 | 说明 |
|------|------|
| 拖放 | 支持文件/文件夹；仅 Windows；**模型就绪后**再大批量拖入 |
| 逐个整理 | 模式选「逐个」→ **开始流水线**：自动 识别→爬取→入库→下一张 |
| 后台批量 | 模式选「批量」→ 设置进程数 5–10 → **开始批量**（多进程，不经 GUI 逐张） |
| 手动 | 改字段后 **识别并爬取** / **完成并下一份** |
| 停止 | 流水线运行中可停止 |

右侧字段：**二维码内容、委托编号、报告编号、工程名称、标段、样品名称、报告日期**；底部为 **OCR 内容**（只读）。

协会编号易混字（0/O、1/l、5/S 等）会自动替换重试爬取。

### 查询页

- 按委托编号、报告编号、工程名称、样品名称 **模糊搜索**
- **报告日期** 起止（日历控件）
- 点击 **列头** 排序（↑/↓）
- 选中行后底部 **预览图片**（需入库且文件仍存在）

---

## 输出目录规则

根目录为用户设置的 **`output_root`**：

```text
{output_root}/报告/{工程名称}/{报告编号}-1.jpg
{output_root}/报告/{工程名称}/{标段}/{报告编号}-1.jpg    ← 协会有标段
{output_root}/报告/_待核实/{编号}-N.ext                  ← 仅有编号、爬取失败
{output_root}/报告/{负责人|经办人}/{工程名称}/...         ← 合同匹配且设置上级目录
```

- 同编号多文件：`{编号}-1`、`-2`、`-3`（第一张也是 `-1`）
- 院网/内网无标段时不建 `{标段}/` 层
- **默认复制**，不删除原图

---

## 数据库

| 项 | 路径 |
|----|------|
| 默认库文件 | `ReportDesk/data/reportdesk.db` |
| Schema | `ReportDesk/db/schema.sql` + `schema_v2.sql` |
| 合同表 | `project_contracts`（Excel 导入） |

主要表：`reports`、`report_files`、`report_samples`、`report_tasks`、`batch_jobs`、`app_settings` 等。

`report_no` 唯一约束（大写规范化）。

---

## 环境变量（可选）

未在 GUI 配置时，可与 ScanReport/LimisQuery 共用：

| 变量 | 含义 |
|------|------|
| `LIMIS_BASE` | 内网根 URL |
| `LIMIS_USER` | 用户名 |
| `LIMIS_PASSWORD` | 密码 |
| `LIMIS_AUTH_TYPE` | 默认 `1` |
| `RAPID_OCR_JSON` | RapidOCR-json 目录 |
| `REPORTDESK_DB` | 数据库文件绝对路径 |

---

## 测试

```powershell
cd code_base
.\venv\Scripts\python.exe -m unittest ReportDesk.tests.test_core -v
.\venv\Scripts\python.exe -m unittest discover -s ReportDesk/tests -p "test_*.py" -v
```

手工集成：用 `ScanReport\report\` 下样图，在 GUI 指定输出目录后跑流水线。

---

## 故障排除

| 现象 | 处理 |
|------|------|
| 批量拖入闪退 `PyEval_RestoreThread` / GIL | 使用最新代码；等 **QR 识别模型已就绪** 后再大批量拖入 |
| 无法拖放 | `pip install windnd`；仅 Windows |
| `No module named tkinter` | 重装 Python 并勾选 tcl/tk |
| torch 安装慢/失败 | 使用 CPU 索引 URL；或配置 pip 镜像 |
| 无二维码无法识别 | 配置 RapidOCR-json 路径 |
| 内网爬取失败 | VPN/内网连通；检查 LIMIS 账号与 `limis_base` |
| 合同路径未生效 | 工程名须与 Excel **完全一致**（trim 后）；需先导入合同表 |
| 查询预览空白 | 入库文件已移动或删除；检查 `report_files` 路径 |

---

## 仓库结构

```text
code_base/                          ← REPO_ROOT（git 根）
├── ScanReport/                     ← QR/OCR/爬取
│   ├── qrdet-*.pt
│   ├── tools/RapidOCR-json/        ← 需自行下载
│   └── report/                     ← 样例图
├── LimisQuery/                     ← 内网 API 客户端
├── ReportDesk/                     ← 本应用
│   ├── app.py                      ← 启动入口
│   ├── README.md                   ← 本文档
│   ├── requirements.txt
│   ├── core/                       ← 流水线、归档、字段映射
│   ├── gui/                        ← tkinter 界面
│   ├── db/                         ← SQLite
│   ├── data/                       ← reportdesk.db（gitignore）
│   └── tests/
└── venv/                           ← 本地创建（gitignore）
```

---

## 依赖说明

| 包 | 用途 |
|----|------|
| torch / qreader | QR 检测（ScanReport） |
| opencv-python-headless | 图像读取 |
| requests / beautifulsoup4 / lxml | 爬取 |
| Pillow | 预览 |
| windnd | Windows 拖放 |
| tkcalendar / openpyxl | 日期选择、合同导入 |
| tkinter | 标准库 GUI |

---

## 安全提示

- LIMIS 密码保存在本机 SQLite **明文**（`app_settings`），仅用于本机批处理。
- 勿将 `ReportDesk/data/reportdesk.db`、含凭据的备份提交到 git 或上传到公共网盘。

---

## 相关文档

- [ScanReport README](../ScanReport/README.md) — 解码与爬取细节  
- [LimisQuery README](../LimisQuery/README.md) — 内网客户端  
- [ScanReport DEVELOPMENT.md](../ScanReport/docs/DEVELOPMENT.md) — 协议与字段说明
