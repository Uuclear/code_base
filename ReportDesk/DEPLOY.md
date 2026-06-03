# ReportDesk 在其他机器上安装与运行

仓库：<https://github.com/Uuclear/code_base>（本应用在 `ReportDesk/` 子目录）。

## 环境要求

| 项 | 说明 |
|----|------|
| 系统 | **Windows 10/11**（拖放依赖 `windnd`；GUI 为 tkinter） |
| Python | **3.10+**（建议 3.12），安装时勾选 **tcl/tk** |
| 网络 | 协会/院网爬取需能访问外网；内网报告需能访问 LIMIS |
| 磁盘 | 约 2–4 GB（含 PyTorch CPU 与 QR 权重） |

## 1. 克隆仓库

```powershell
git clone https://github.com/Uuclear/code_base.git
cd code_base
```

若使用 SSH：`git clone git@github.com:Uuclear/code_base.git`

## 2. 创建虚拟环境并安装依赖

在仓库根目录 `code_base/` 下执行（与 ScanReport、LimisQuery 共用同一 venv）：

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1

# CPU 版 PyTorch（无 NVIDIA 显卡时推荐）
pip install torch --index-url https://download.pytorch.org/whl/cpu

pip install -r ScanReport/requirements.txt
pip install -r LimisQuery/requirements.txt
pip install -r ReportDesk/requirements.txt
```

## 3. QR 权重与 OCR（与 ScanReport 相同）

- **QR 检测**：将 `qrdet-*.pt` 放在 `ScanReport/` 根目录（克隆仓库后通常已包含）。
- **无二维码时的 OCR**：下载 [RapidOCR-json](https://github.com/hiroi-sora/RapidOCR-json) 解压到  
  `ScanReport/tools/RapidOCR-json`  
  或在应用「设置」里填写 RapidOCR 目录。

## 4. 合同表（可选）

整理页可按合同表在输出路径前加「负责人/经办人」一级目录。

- 将 `合同.xlsx` 放到任意路径（列：项目名称、负责人、经办人）。
- 首次运行若数据库无合同数据，会尝试 `limis-api/合同.xlsx`（仅当你把整个 `limis-api` 工作区一并拷贝时）。
- 更稳妥：启动后 **设置 → 选择合同表 Excel → 导入合同表到数据库**。

## 5. 启动应用

```powershell
cd code_base
.\venv\Scripts\Activate.ps1
python ReportDesk\app.py
```

启动后约 0.5 秒会在主线程加载 QR 模型，日志出现「QR 识别模型已就绪」后再大批量拖入图片。

## 6. 首次使用设置

打开 **设置**，按需填写：

- **LIMIS 地址 / 用户名 / 密码**（内网报告）
- **输出根目录**（整理后的 `报告/...` 复制目标）
- **RapidOCR 目录**、**QR 权重目录**（默认指向 ScanReport）
- **工程目录上级**、合同表路径与导入

密码保存在本机 SQLite（`ReportDesk/data/reportdesk.db`，已在 `.gitignore`），勿把该库文件提交到 git。

## 7. 环境变量（可选）

与 ScanReport 一致，可在未配置 GUI 设置时使用：

| 变量 | 含义 |
|------|------|
| `LIMIS_BASE` | 内网 LIMIS 根 URL |
| `LIMIS_USER` / `LIMIS_PASSWORD` | 内网账号 |
| `LIMIS_AUTH_TYPE` | 默认 `1` |
| `RAPID_OCR_JSON` | RapidOCR-json 目录 |
| `REPORTDESK_DB` | 数据库文件路径 |

## 8. 验证安装

```powershell
cd code_base
.\venv\Scripts\python.exe -m unittest ReportDesk.tests.test_core -v
.\venv\Scripts\python.exe -c "import sys; sys.path.insert(0,'ReportDesk'); from gui.main_window import MainWindow; print('import ok')"
```

## 9. 常见问题

- **拖入大量图片闪退**：请用最新版；确保 QR 模型在主线程加载完成后再批量拖入。
- **无法拖放**：`pip install windnd`，且仅在 Windows 有效。
- **内网爬取失败**：检查 VPN/内网可达性与 LIMIS 账号。
- **torch 安装慢**：使用上文 CPU 索引 URL，或在本机配置 pip 镜像。

## 仓库结构速览

```text
code_base/
  ScanReport/      # QR/OCR/爬取核心
  LimisQuery/      # 内网客户端
  ReportDesk/      # 本桌面应用
  venv/            # 本地创建，不提交 git
```
