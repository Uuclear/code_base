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
    qr -->|无 QR| skip[跳过并记录]
    qr -->|有 QR| classify{QR 内容分类}
    classify -->|http URL 非 scetia| yuanwang[院网: numDecode + GetReportInfo]
    classify -->|scetia 或 编号|防伪码| xiehui[协会: POST/GET 防伪查询]
    yuanwang --> json[output/*.json]
    xiehui --> json
```

## 院网（jktac）

- 页面：`/WeChat/rQuery?rId=...&rNo=...`，内容由 JS 加载。
- `handle.js` 中 `numDecode(rId, 2)` 将混淆 `rId` 转为数字 `testingReportId`。
- 字符表：`l,e,f,v,6,2,1,a,d,h` → 索引 0–9（见 `src/jktac_codec.py`）。
- API：`POST /WeChat/GetReportInfo`，参数 `testingReportId`、`testingReportNo`。
- 实现：`src/scrape_institute.py`、`src/parse_institute_api.py`。

## 协会（scetia）

| 防伪校验码 | Endpoint | 方法 |
|------------|----------|------|
| 12 位，非 0 开头，非 3001 前缀 | `scetia.com/.../AntiFakeReportQuery.aspx` | POST |
| 10 位 | `scetimis.com/QueryReport/SearchQueryReport.aspx` | POST |
| 12 位 0 开头 / 11 位 | `rptverify.scetia.com/checkreport/` | GET |
| 12 位 3001 前缀 | `signboard.scetimis.com/checkreport` | GET |

QR 文本常见格式：`HN01-202629448|110807184827` 或 `HN1S-202600461|120807188600`。

实现：`src/scrape_association.py`。

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
│   └── parse_institute_api.py
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

## 风险与后续

- 院网 API 可能 500 超时，已实现重试；解码 ID 失败时回退原始 `rId`。
- 协会 `samples` 表格解析可加强选择器。
- 大文件：`qrdet-*.pt` 与 `report/*.jpg` 已纳入版本库，克隆后可直接开发。
