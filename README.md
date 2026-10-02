# Paperx · AI 双栏论文阅读器

当前实现：**阶段 0 — 工程基线与可行性验证**。这是可运行的解析/坐标验证器，不是已完成的双语阅读器。

## 快速启动（Windows PowerShell）

先完成一次环境初始化：

```powershell
cd G:\Projects\Paperx
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.lock
npm --prefix web ci
```

之后每次启动项目只需：

```powershell
.\scripts\start.bat
```

批处理脚本默认复用已生成的本地样本，在两个独立命令行窗口中启动后端和前端；也可以直接双击运行。普通启动不会加载模型或重新推理。可选参数：

```powershell
.\scripts\start.bat /install       # 同时安装/更新 Python 与前端依赖
.\scripts\start.bat /prepare       # 使用 Marker 准备/更新论文样本
.\scripts\start.bat /skip-prepare   # 兼容旧参数，默认已跳过重建
.\scripts\start.bat /open-browser   # 启动后自动打开浏览器
```

浏览器打开 `http://127.0.0.1:5173`；API 文档为 `http://127.0.0.1:8000/docs`。关闭脚本启动的两个服务窗口即可停止项目。
前端默认打开本地 Transformer 样本（若存在），可切换合成样本、翻页、点击原 PDF 坐标区域检查结构块。
生产构建只是静态产物，部署时需配置同源 `/api` 反向代理；目前仅提供开发启动方式。

## 本地 Marker 抽取

真实论文默认采用 **Marker 1.9.3 / Surya 0.16.7**；合成验收样本继续使用 pdfplumber 基线，便于对比。Marker 在独立 `.venv-marker` 工作进程中运行，不占用 API 的 Python 环境；失败会明确报错，不会悄悄退回旧抽取器。

首次部署时，在完成上面的主环境初始化后运行：

```powershell
.\scripts\install-marker.bat
.\scripts\prepare-marker.bat
.\scripts\start.bat
```

安装脚本使用锁定依赖和 CUDA 12.8 PyTorch。当前已在 Python 3.12.7、RTX 5080 Laptop GPU 上完成真实推理。**模型权重、模型缓存和推理临时目录全部配置在项目的 `model/` 下**，该目录和 `.venv-marker/` 均不提交 Git；已下载的权重约 2.07 GiB，Python 环境另占磁盘空间。

默认使用 GPU；如需 CPU，先在同一个 PowerShell 会话设置 `$env:PAPERX_MARKER_DEVICE="cpu"`，再运行 `prepare-marker.bat`。CPU 路径尚未做性能验收，不会自动从 GPU 降级。首次推理需要联网下载权重，已有权重无需重复下载；本地抽取禁用 LLM，不使用 API Key、不上传论文给外部 AI 服务。

产物位于 `data/marker/<parser_version>/<PDF SHA256>/blocks.json`（原始块）、`blocks.md`（Markdown）及 `worker.log`；阅读器使用 `data/samples/transformer/document.json`。相同 PDF 会复用原始结果；重新运行准备脚本可以重新适配这些块，不代表重新推理。强制重新推理时，仅移走对应 SHA256 的原始结果目录，保留 `model/`，然后再次准备。旧导出会存入样本的 `history/`，旧锚点只对唯一完全匹配的内容自动迁移。

当前 Transformer 样本为 15 页、173 个结构块，摘要已整段保留，页眉/页脚不再混入段落。仍有字符识别、作者区域及公式细节错误，不能视作逐字校对完成；公式候选保持待核验且不可复制。部署、许可和质量边界详见 `docs/engineering/Marker本地部署.md`。

## 验证

```powershell
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m ruff check backend scripts
npm --prefix web test
npm --prefix web run build
npm --prefix web exec -- playwright install chromium
npm --prefix web run test:e2e
# 已安装 Chrome 时可不下载 Chromium：
$env:PAPERX_BROWSER_CHANNEL="chrome"
npm --prefix web run test:e2e
```

E2E 自动启动并关闭 8000/5173 服务；执行前释放这两个端口。先运行 `prepare-marker.bat`。
后端真实论文测试在用户文件不存在时明确 skip；合成样本测试不依赖该论文。
测试不调用付费 AI，不需要 Key，也不会触发模型下载。依赖清单：`requirements.lock`、`requirements-marker.lock`、`web/package-lock.json`。
Node 验证环境 24.18.0，Python 3.12.7；若升级解析依赖，必须重验样本、递增 parser_version 并重建导出。

## 目录

- `backend/paperx/`：FastAPI、Pydantic 契约、Provider 接口、Marker 适配器和旧解析基线。
- `backend/tests/`：坐标、契约、PDF Range、异常文件、真实论文与合成样本回归。
- `web/`：React/TypeScript/PDF.js 验证界面、单元及浏览器测试。
- `scripts/start.bat`：Windows 一键启动脚本（不受 PowerShell 执行策略影响）。
- `scripts/install-marker.bat`、`scripts/prepare-marker.bat`：安装独立推理环境、抽取真实论文。
- `scripts/prepare_samples.py`：生成样本、真实解析、对比 pypdf、导出 schema/OpenAPI。
- `tests/fixtures/`：原创建模样本、许可和人工预期值。
- `data/`：本地产物，已忽略；可重新导出，勿提交含未公开论文的数据。
- `model/`：项目内模型权重、库缓存、下载临时文件，已忽略。
- `docs/engineering/阶段0验收.md`：结果、限制、下一阶段前置条件。
- `docs/engineering/架构与契约.md`：坐标、ID、安全边界与选型。

## API 配置与隐私

`.env.example` 只包含非敏感默认值：API 地址 `https://api.openlux.ai`、模型 `gpt-5.6-terra`。
当前阶段不读取、不保存、不发送 API Key，也不会访问第三方翻译接口；翻译模型在第三方服务上的可用性尚未验证。Marker 首次运行会下载开源模型，论文推理在本机完成。
环境变量由 `PAPERX_` 前缀读取；当前不会自动加载 `.env`，以免误将密钥落盘当作安全持久化。
后续阶段 2 将通过后端进程内设置配置 Key（重启需重新填写），或实现加密存储后再持久化。
用户已在聊天中给出的 Key 没有写入任何项目文件。建议到服务商处轮换该 Key。

## 尚未实现

阶段 1：上传、SQLite 持久化、任务/Worker、arXiv、完整目录与图表提取、译文 PDF 关联。
阶段 2：AI 设置/模型列表/真实翻译/质量检查。
阶段 3–7：完整双栏阅读、同步、可信公式复制、笔记、语义搜索和交付回归。
现在的目录/页码/覆盖层仅用于阶段 0 技术验证；右栏是提取的英文原文，不是译文。


