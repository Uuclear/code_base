# video-ocr

对视频帧中的水印区域运行 **PaddleOCR**，将识别到的文本按正则与启发式解析为四类字段：

1. **包含 `-` 的行**（`dash_line`）
2. **时间**（`time`）
3. **文字内容**（`content`）
4. **dn**（设备或流水号等标识）

## 安装

需要已安装 **PaddlePaddle**（CPU 或 GPU 版，与官方文档一致），再安装本目录：

```bash
pip install "paddlepaddle>=2.5.0" -i https://mirror.baidu.com/pypi/simple
pip install -e ".[dev]"
```

## 用法

```python
from video_ocr import WatermarkPatterns, extract_watermark_from_video

patterns = WatermarkPatterns(
    time=r"(?P<time>\d{2}:\d{2}:\d{2})",
    dn=r"(?P<dn>dn[:：]\s*\w+)",
)

out = extract_watermark_from_video(
    "sample.mp4",
    patterns=patterns,
    frame_interval=15,
    region=(0, 0, 400, 120),  # 可选：水印 ROI x, y, w, h
)
print(out.dash_line, out.time, out.content, out.dn)
```

纯文本（已有 OCR 行）解析：

```python
from video_ocr import extract_watermark_fields, WatermarkPatterns

text = "user-device\n12:34:56\n说明文字\ndn: X1"
print(extract_watermark_fields(text.splitlines(), WatermarkPatterns()))
```

## 说明

- `dash_line`：默认取**第一条包含 `-` 的行**；也可通过 `WatermarkPatterns.dash_line` 传入整行正则。
- `time` / `dn`：默认提供常见模式，可用正则覆盖；`dn` 会尽量归一化为标识值（去掉 `dn:` 前缀）。
- `content`：默认在去掉结构行后，将其余非空行合并为说明文字；也可用 `WatermarkPatterns.content` 指定 `(?P<content>...)` 在全文中匹配。
