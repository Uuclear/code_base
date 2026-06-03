# ScanReport 开发文档

## 项目概述

扫描 `report/` 下含二维码的检验检测报告图片，识别二维码并抓取院网/协会在线报告，输出 JSON。

## 报告类型

| 类型 | 识别特征 | 示例 | 二维码位置 |
|------|----------|------|------------|
| 院网 | SRIBS 水印、「检验检测报告」 | `1780415252701.jpg` | 右上角 |
| 协会 | SCETIA 水印、页脚「上海市建设工程检测行业协会印制」 | `1780415252895.jpg` | 右上角 |

`1780415252775.jpg` 为封面，无二维码，流水线会跳过。

## 整体流程

```mermaid
flowchart TD
    scan[扫描 report/*.jpg] --> qr[QReader detect_and_decode]
    qr -->|无 QR| ocr{RapidOCR-json 已配置?}
    ocr -->|否| skip[跳过并记录]
    ocr -->|是| regex[正则: 编号|防伪码 / URL / 内网编号]
    regex -->|无法识别| skip
    qr -->|有 QR| classify{内容分类}
    regex --> classify
    classify -->|http URL 非 scetia| yuanwang[院网: GetReportInfo]
    classify -->|编号+防伪码| xiehui[协会: 防伪查询]
    classify -->|仅内网编号| limis[LimisQuery 10.1.228.22]
    yuanwang --> json[output/*.json]
    xiehui --> json
    limis --> json
```

### OCR 回退（`src/rapidocr_client.py` + `src/text_extract.py`）

- 依赖 [RapidOCR-json](https://github.com/hiroi-sora/RapidOCR-json) Windows 可执行包；环境变量 `RAPID_OCR_JSON` 或 `--rapidocr` 指向解压目录。
- 编号规则集中定义于 `src/report_patterns.py`：
  - **内网 / 院网（同一套）**：`[A-Z]{2,4}\d{0,4}[A-Z]?-\d{6,}`（如 `JG018-250187`）；院网另需 QR 内 jktac URL + `rId`。
  - **协会报告编号**：`[A-Z]{2,4}…-\d{4,10}` 或标签后纯 `\d{4,10}`。
  - **防伪码（OCR）**：仅「防伪校验码」标签后的 **10 或 12 位**数字；二维码仍为 `编号|10/12位`。
  - **委托编号**（协会表单）：标签后纯数字 **4~6 位**（及 OCR 常见更长委托号）**不得**当作防伪码。
- 识别优先级：`报告编号|防伪码` → 协会；`http` URL → 院网/协会；标签编号+防伪 → 协会；**仅**内网/院网样式报告号 → LIMIS（`scrape_limis.py`）。
- **批处理内网**：`main.py` 对整批只 `login()` 一次，复用 `LimisClient.session`（Cookie）；`summary.json` 含 `limis_session_logins`。

## 院网（jktac）

- 页面：`/WeChat/rQuery?rId=...&rNo=...`，内容由 JS 加载。
- `handle.js` 中 `numDecode(rId, 2)` 将混淆 `rId` 转为数字 `testingReportId`。
- 字符表：`l,e,f,v,6,2,1,a,d,h` → 索引 0–9（见 `src/jktac_codec.py`）。
- API：`POST /WeChat/GetReportInfo`，参数 `testingReportId`、`testingReportNo`。
- 实现：`src/scrape_institute.py`、`src/parse_institute_api.py`。

## 协会（scetia）

| 防伪校验码 | 数据通道 | 实现 |
|------------|----------|------|
| 12 位，非 0 开头，非 3001 前缀 | ASP.NET HTML 表 | `AntiFakeReportQuery.aspx` POST → `parse_html.py` |
| 10 位 | ASP.NET HTML | `scetimis.com/QueryReport/SearchQueryReport.aspx` POST |
| 12 位 0 开头 / 11 位 | **JSON API** | `POST rptverify-service.scetia.com/api/rptAuthVerify/checkReport`，body `{no, checkCode}`，成功返回 `data.reportUrl`（PDF） |
| 12 位 3001 前缀 | **JSON API** | `POST signboard-service.scetimis.com/api/user/checkReport`，同上 |

QR 文本常见格式：`HN01-202629448|110807184827`（走 HTML）或 `HN1S-202600461|120807188600`（若码规则命中 Vue 线路则走 JSON）。

`report/` 当前样本均为 **material_html**（12 位 1 开头防伪码）；JSON 两路在 `src/parse_association_api.py` + `scrape_association.resolve_association_backend()` 中已接入。

输出 JSON 的 `query.backend` 取值：`material_html` | `scetimis_html` | `rptverify_json` | `signboard_json`。

## 目录与模块

```
ScanReport/
├── main.py                 # CLI 入口
├── requirements.txt
├── qrdet-{n,s,m,l}.pt      # QReader 检测权重（已入库）
├── report/                 # 样本 JPG
├── docs/                   # 本文档
├── src/
│   ├── qr_decode.py
│   ├── jktac_codec.py
│   ├── scrape_institute.py
│   ├── scrape_association.py
│   ├── parse_html.py
│   ├── parse_institute_api.py
│   ├── rapidocr_client.py
│   ├── text_extract.py
│   ├── decode_pipeline.py
│   └── scrape_limis.py
├── tests/
└── output/                 # 运行产物（git 忽略）
```

## 环境

```bash
python -m venv venv
venv\Scripts\activate
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
```

## 运行与验证

```bash
python main.py --input report --output output
python main.py -i report/Test1..jpg -i report/test2.jpg -o output/test_run
```

| 图片 | 预期 |
|------|------|
| `1780415252701.jpg` / `2792.jpg` | 院网 JSON 含报告编号 |
| `1780415252895.jpg` | 协会 POST，含 HN01-202629448 |
| `1780415252840.jpg` | 协会 SJ02-202600988 |
| `1780415252775.jpg` | 跳过 |

## JSON 输出示例

```json
{
  "source_image": "1780415252895.jpg",
  "report_type": "association",
  "qr_content": "HN01-202629448|110807184827",
  "query": { "report_no": "...", "anti_fake_code": "...", "endpoint": "..." },
  "project": { "report_no": "...", "project_name": "..." },
  "samples": [],
  "scraped_at": "2026-06-03T..."
}
```

## 验证层级（协会 JSON 两路）

| 层级 | 是否需要真实报告 | 当前状态 |
|------|------------------|----------|
| 路由 | 否 | `tests/test_association_backend.py`：按防伪码长度/前缀选 `material_html` / `rptverify_json` / `signboard_json` |
| 契约 | 否 | 自 `CheckReport.*.js` 确认：POST body `{no, checkCode}`；成功 `resultCode/code==200` 且 `data.reportUrl` |
| 联调（失败路径） | 否 | 用现有 HN01 码调 JSON API 得 `400`/`60025`，说明**参数形状对、码不属于该系统**（符合预期） |
| 联调（成功路径） | **是** | 需 `0` 开头 12 位或 `3001` 前缀的真实 QR；`report/` 样本均为 `1` 开头 12 位，只能验 HTML 路 |
| 流水线 Mock | 否 | `tests/test_association_json_mock.py`：Mock API 响应，验 `scrape_association` 分支与 `report_pdf_url` 输出 |

有真实 Vue 线路二维码后，在 `ScanReport` 目录执行：

```bash
python -c "
from src.qr_decode import DecodeResult
from src.scrape_association import scrape_association
import json
d = DecodeResult('x.jpg', ['报告编号|防伪码'], 'association', '报告编号', '防伪码')
print(json.dumps(scrape_association(d), ensure_ascii=False, indent=2))
"
```

成功时应见 `query.backend` 为 `rptverify_json` 或 `signboard_json`，且含可打开的 `report_pdf_url`。

## 风险与后续

- 院网 API 可能 500 超时，已实现重试；解码 ID 失败时回退原始 `rId`。
- 协会 JSON 成功路径未经真实样本端到端确认；拿到对应二维码后按上表最后一行补验即可。
- 大文件：`qrdet-*.pt` 与 `report/*.jpg` 已纳入版本库，克隆后可直接开发。
