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
.\scripts\start.ps1
```

脚本会自动重建本地样本，并在两个独立 PowerShell 窗口中启动后端和前端。可选参数：

```powershell
.\scripts\start.ps1 -Install       # 同时安装/更新 Python 与前端依赖
.\scripts\start.ps1 -SkipPrepare   # 跳过样本重建
.\scripts\start.ps1 -OpenBrowser   # 启动后自动打开浏览器
```

浏览器打开 `http://127.0.0.1:5173`；API 文档为 `http://127.0.0.1:8000/docs`。关闭脚本启动的两个服务窗口即可停止项目。
前端默认打开本地 Transformer 样本（若存在），可切换合成样本、翻页、点击原 PDF 坐标区域检查结构块。
生产构建只是静态产物，部署时需配置同源 `/api` 反向代理；目前仅提供开发启动方式。

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

E2E 自动启动并关闭 8000/5173 服务；执行前释放这两个端口。先运行 `prepare_samples.py`。
后端真实论文测试在用户文件不存在时明确 skip；合成样本测试不依赖该论文。
测试不调用付费 AI，不需要 Key。依赖清单：`requirements.lock`、`web/package-lock.json`。
Node 验证环境 24.18.0，Python 3.12.7；若升级解析依赖，必须重验样本、递增 parser_version 并重建导出。

## 目录

- `backend/paperx/`：FastAPI、Pydantic 契约、Provider 接口、保守解析器。
- `backend/tests/`：坐标、契约、PDF Range、异常文件、真实论文与合成样本回归。
- `web/`：React/TypeScript/PDF.js 验证界面、单元及浏览器测试。
- `scripts/start.ps1`：Windows 一键启动脚本。
- `scripts/prepare_samples.py`：生成样本、真实解析、对比 pypdf、导出 schema/OpenAPI。
- `tests/fixtures/`：原创建模样本、许可和人工预期值。
- `data/`：本地产物，已忽略；可重新导出，勿提交含未公开论文的数据。
- `docs/engineering/阶段0验收.md`：结果、限制、下一阶段前置条件。
- `docs/engineering/架构与契约.md`：坐标、ID、安全边界与选型。

## API 配置与隐私

`.env.example` 只包含非敏感默认值：API 地址 `https://api.openlux.ai`、模型 `gpt-5.6-terra`。
当前阶段不读取、不保存、不发送 API Key，也不会访问第三方翻译接口；模型在第三方服务上的可用性尚未验证。
环境变量由 `PAPERX_` 前缀读取；当前不会自动加载 `.env`，以免误将密钥落盘当作安全持久化。
后续阶段 2 将通过后端进程内设置配置 Key（重启需重新填写），或实现加密存储后再持久化。
用户已在聊天中给出的 Key 没有写入任何项目文件。建议到服务商处轮换该 Key。

## 尚未实现

阶段 1：上传、SQLite 持久化、任务/Worker、arXiv、完整目录与图表提取、译文 PDF 关联。
阶段 2：AI 设置/模型列表/真实翻译/质量检查。
阶段 3–7：完整双栏阅读、同步、可信公式复制、笔记、语义搜索和交付回归。
现在的目录/页码/覆盖层仅用于阶段 0 技术验证；右栏是提取的英文原文，不是译文。
