# PlateStudio 高清车牌图像工具

由 CYHPLAY 发布的 Windows 中文桌面工具，支持自定义车牌号码、样式预览、平滑字符和可调立体效果。

![效果预览](assets/preview.png)

## 下载与使用

在 [Releases](https://github.com/CYHPLAY/plate-studio-16k/releases) 下载 Windows 发布包，解压后双击 `PlateStudio_16K_Fast.exe`。
适用 Windows 10/11 64 位，无需安装 Python，无需联网。

1. 输入号码：普通样式 7 位，新能源样式 8 位。
2. 选择车牌类型、单双层及压凸效果，根据预览调整强度。
3. 设置导出尺寸，点击“导出图片…”保存 PNG 或 JPG。

小写字母自动转大写，空格和分隔点自动去除。支持中文保存路径及 Ctrl+S。

## 功能

- 8 种车牌样式；黄牌及普通白牌支持双层。
- 保留字符造型和外框，平滑数字边缘。
- 可调压凸高光、侧边阴影和轻投影。
- 后台导出，PNG 无损或 JPG 高质量保存。
- 分块计算光照，减少临时图像副本与导出峰值内存。

## 导出规格

宽度支持 440～16000 像素，高度按车牌比例计算。双层最大为 16000 × 8000。
建议先用 3840 或 7680 像素确认效果；更大输出需要更多内存与时间。
PNG 使用快速无损压缩，文件可能稍大。查看清晰度请使用导出图的 100% 大小，窗口预览会缩小。

## 源码运行与构建

需要 Python 3.12（包含 Tcl/Tk）。

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe src/plate_studio.py
powershell -ExecutionPolicy Bypass -File .\build.ps1
```

构建产物为 `dist/PlateStudio_16K_Fast.exe`。首次构建需要联网安装依赖。

## 验证与性能

```powershell
.\.venv\Scripts\python.exe src/plate_studio.py --self-test work/self-test
```

覆盖 8 种样式及单双层组合。已验证打包程序及最大尺寸 PNG 导出。
EXE 约 67.8 MB；本机 7680 像素双层导出峰值内存约 309 MiB，较优化前减少约 18%。
测试方法和限制见 [性能说明](docs/PERFORMANCE.md)，实际结果随电脑和设置变化。

## 使用边界

仅用于合法的设计预览、教学、测试和视觉研究。软件不校验号码真实性或登记情况，
图像不保证符合官方号牌标准，压凸与光照是二维模拟。

**不得用于伪造、变造、冒用号牌、欺诈或规避执法。** 使用前请阅读 [免责声明](DISCLAIMER.md)。

## 许可

许可、版权及素材来源信息集中保留于 [LICENSE](LICENSE) 和 [第三方说明](THIRD_PARTY_NOTICES.md)。
