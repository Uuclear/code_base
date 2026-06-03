# code_base

Monorepo for LIMIS / inspection-report tooling on GitHub: **Uuclear/code_base**.

| 子项目 | 说明 | 文档 |
|--------|------|------|
| **ReportDesk** | Windows 桌面：报告批量整理（GUI + SQLite） | [**ReportDesk/README.md**](ReportDesk/README.md) — **部署、使用、AI 自动化清单** |
| **ScanReport** | 报告图片 QR/OCR + 协会/院网/内网爬取 | [ScanReport/README.md](ScanReport/README.md) |
| **LimisQuery** | 内网 LIMIS HTTP 客户端 | [LimisQuery/README.md](LimisQuery/README.md) |

## 快速启动 ReportDesk

```powershell
git clone https://github.com/Uuclear/code_base.git
cd code_base
python -m venv venv
.\venv\Scripts\python.exe -m pip install torch --index-url https://download.pytorch.org/whl/cpu
.\venv\Scripts\python.exe -m pip install -r ScanReport\requirements.txt -r LimisQuery\requirements.txt -r ReportDesk\requirements.txt
.\venv\Scripts\python.exe ReportDesk\app.py
```

完整步骤、验证命令与 AI 代理检查清单见 **[ReportDesk/README.md](ReportDesk/README.md)**。  
合同工程表：**`合同.xlsx`**（仓库根目录，克隆即用）。
