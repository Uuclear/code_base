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

无二维码的图片（如封面）会跳过。

## 目录结构

```
ScanReport/
├── main.py
├── requirements.txt
├── src/
│   ├── qr_decode.py
│   ├── scrape_association.py
│   ├── scrape_institute.py
│   └── parse_html.py
├── docs/            # 开发文档
├── report/          # 样本图片（已入库）
├── output/          # 运行结果（git 忽略）
└── qrdet-*.pt       # QR 检测模型（n/s/m/l，已入库）
```
