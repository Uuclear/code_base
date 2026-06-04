# ScanReport

位于 [Uuclear/code_base](https://github.com/Uuclear/code_base) 仓库的 `ScanReport/` 子目录。

扫描 `report/` 目录下的检验检测报告图片，识别二维码并抓取院网/协会在线报告，输出 JSON。

详细设计见 [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)。
## 环境

```bash
python -m venv venv
venv\Scripts\activate
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
```

项目根目录已放置 `qrdet-*.pt` 权重时，QReader 会优先使用本地文件。

## 运行

```bash
python main.py --input report --output output
```

可选参数：

- `--weights`：qrdet 权重目录（默认项目根）
- `--limit N`：只处理前 N 张图

## 输出

- `output/{图片名}.json`：单张报告结构化结果
- `output/summary.json`：成功 / 跳过 / 失败统计

## 报告类型

| 类型 | QR 特征 | 抓取方式 |
|------|---------|----------|
| 院网 | `http(s)://` 且非 scetia 系域名 | `handle.js` 中 `numDecode(rId,2)` 得到数字 ID，再 POST `/WeChat/GetReportInfo` |

院网页面由 JS 异步加载，不解析静态 HTML。`rId` 字符表见 `src/jktac_codec.py`（与 `handle.js` 一致：`l,e,f,v,6,2,1,a,d,h`）。

| 协会 | scetia 域名，或 `报告编号\|防伪校验码` 纯文本 | 按防伪码长度路由 POST/GET |

无二维码时，若已配置 OCR 引擎，会对图片 OCR，再用正则提取：

- [RapidOCR-json](https://github.com/hiroi-sora/RapidOCR-json)（主要 Windows）
- [PaddleOCR-json](https://github.com/hiroi-sora/PaddleOCR-json)（Windows / Linux，CPU 需 AVX）

设置 `RAPID_OCR_JSON` / `PADDLE_OCR_JSON`，或在 ReportDesk 设置中选择 **OCR 引擎**。

| OCR 识别内容 | 后续动作 |
|--------------|----------|
| `报告编号\|防伪校验码`（如 `LX3S-202600055\|120707188344`） | 协会防伪查询（与 QR 相同） |
| `http(s)://…jktac…` 院网 URL | 院网 `GetReportInfo` |
| 仅内网格式报告编号（如 `JG018-250187`） | 内网 `10.1.228.22` LimisQuery（需 `LIMIS_*` 账号环境变量） |

批处理多张内网报告时，`main.py` **整批只登录一次**，复用 Cookie；`summary.json` 中可看 `limis_session_logins`（应为 1）。

```bash
# 解压 RapidOCR-json 或 PaddleOCR-json 到 ScanReport/tools/ 或设置环境变量
set RAPID_OCR_JSON=C:\path\to\RapidOCR-json
set PADDLE_OCR_JSON=C:\path\to\PaddleOCR-json

python main.py --input report --output output
python main.py -i report/test2.jpg -o output --ocr-engine paddleocr
python main.py -i report/test2.jpg -o output          # 单张图片
python main.py -i report/a.jpg -i report/b.jpg -o out  # 多张（-i 可重复）
python main.py --input report --no-ocr          # 禁用 OCR 回退
python main.py --input report --rapidocr C:\path\to\RapidOCR-json
```

仍无法识别则跳过（如纯封面、无文字）。

## 与内网综合查询（LimisQuery）的对比

内网 `http://10.1.228.22` 与本目录院网/协会二维码的**分列字段对照表**（部位≠标段、合同号≠费用、含 JSON 路径），见 **`../LimisQuery/README.md`** §「与二维码爬取（ScanReport）的字段对照（建库用）」。

## 目录结构

```
ScanReport/
├── main.py
├── requirements.txt
├── src/
│   ├── qr_decode.py
│   ├── decode_pipeline.py
│   ├── rapidocr_client.py
│   ├── text_extract.py
│   ├── scrape_association.py
│   ├── scrape_institute.py
│   ├── scrape_limis.py
│   └── parse_html.py
│   tools/RapidOCR-json/   # 自行下载放置（见上）
├── docs/            # 开发文档
├── report/          # 样本图片（已入库）
├── output/          # 运行结果（git 忽略）
└── qrdet-*.pt       # QR 检测模型（n/s/m/l，已入库）
```
