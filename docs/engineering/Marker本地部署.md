# Marker 本地抽取

## 部署与版本

- 主项目 Python 环境：`.venv`；独立推理环境：`.venv-marker`，Python 3.12.7。
- 固定 `marker-pdf==1.9.3`、`surya-ocr==0.16.7`、`torch==2.10.0+cu128`、`torchvision==0.25.0+cu128`。
- 使用 1.9.3 的进程内 PyTorch 接口。这里不是对 Marker 2.x 推理服务接口的适配，勿直接升级依赖。
- 硬件验收：RTX 5080 Laptop GPU，16 GB 显存；CUDA 路径成功处理 15 页论文。
- `scripts/install-marker.bat` 创建推理环境，先从 PyTorch CUDA 12.8 官方索引安装 CUDA wheel，再安装 `requirements-marker.lock` 并执行 `pip check`。
- `scripts/prepare-marker.bat` 抽取 `paper/nlp/Attention Is All You Need.pdf`，生成样本；`scripts/start.bat` 默认直接读取这些样本，不重复推理。
- `PAPERX_MARKER_DEVICE=cpu` 可显式选用 CPU；未经性能验收。CUDA 不可用时明确失败，不自动降级。

## 模型管理

所有推理库缓存变量都在导入 ML 库之前设置。默认目录不可由用户级缓存变量覆盖：

| 内容 | 项目内路径 |
| --- | --- |
| Surya 权重（当前实际下载） | `model/surya/` |
| Hugging Face hub、assets、xet | `model/huggingface/` |
| Torch hub、编译缓存 | `model/torch/` |
| Triton 缓存 | `model/triton/` |
| XDG 通用缓存 | `model/cache/` |
| 模型下载与推理临时目录 | `model/tmp/` |

当前权重合计 2,222,300,876 字节，约 2.07 GiB；Python 环境占用另计。普通启动不加载权重。删除权重后下次推理会重新下载；不建议以删除模型的方式清理解析缓存。

`model/`、`.venv-marker/`、`data/` 均被 Git 忽略。推理工作进程设置 `use_llm=False`，不使用第三方翻译 API 或 Key；下载开源模型需要网络，不应把首次部署称为完全离线。

## 抽取与契约

1. 主环境在启动推理前校验 PDF 签名、50 MiB 限制、300 页限制及加密状态。
2. 原始 JSON 缓存键使用 PDF SHA256 和 `marker-1.9.3-paperx-v1`，记录源摘要、库版本、设备、配置和 worker revision。
3. 工作进程单次构建 Marker 文档，然后分别输出 `blocks.json` 和 `blocks.md`。GPU 使用 SDPA 和小批次；禁用 Windows 多进程。
4. 适配器按 Marker 容器顺序递归，只递归布局容器，不把 Table 拆成 TableCell。页眉、页脚和引用占位不作为正文块输出。
5. HTML 只解析为纯文本，屏蔽 script/style；不会把 PDF 衍生 HTML 注入前端。
6. 坐标从显示页归一化坐标逆旋转，再将 CropBox 映射到未旋转 MediaBox；检测异常、非有限及退化边界。
7. 保留标题树、列表、图、表和公式。多条 math 节点分行保存；所有公式候选置信度为 0、状态待人工复核，不允许复制。
8. 原始图像保留在 PDF 中，当前未另导出图片文件。API 继续服务原 PDF 与适配后的只读样本。

缓存路径：

```text
data/marker/marker-1.9.3-paperx-v1/<PDF SHA256>/
  blocks.json
  blocks.md
  worker.log
data/samples/transformer/
  original.pdf
  document.json
  sample.json
  history/
```

推理失败不会静默回退旧抽取器，也不会覆盖已发布样本。显式 `prepare_samples.py --parser pdfplumber` 仅用于对照。旧样本导出会归档；只有同页、同类型且文本完全相同的唯一匹配块可自动迁移锚点，其他锚点标记待复核。

## 真实论文结果

Transformer 论文：15 页、173 块，其中 90 段正文、43 条列表、26 个标题、5 个图、5 个公式、4 个表。摘要作为一个完整段落保留，不包含原先混入的 arXiv `7v26730` 字串。第二页保留 9 个正文段落及 3 个标题，完整表格不再碎裂为单元格。

这是版面分块改善，不是逐字人工校对结果。已发现的误差包括：摘要中的 `Englishto-German` 缺连接符、作者姓名区域漏字/分组错误、表格中的 `Wodel` 错字，以及注意力公式缺少部分前缀。跨页表格合并、精确作者元数据、可信公式复制都不属于本次完成范围。

## 验证

后端覆盖容器顺序、完整表格、页眉过滤、HTML 安全、多公式、项目内缓存、旋转/CropBox、来源校验、损坏缓存、加密 PDF、旧锚点迁移与真实论文缓存。测试不下载模型；真实论文/缓存不存在时相应用例明确 skip。

浏览器回归包含 PDF canvas 非白屏像素检测、段落及表格坐标选中、页码/目录联动、390 px 手机宽度和真实 Marker 论文截图。结构化缓存重复适配的一致性不等同于 GPU 模型逐字确定性。

本机验收：后端 38 项、前端单元 5 项、浏览器端到端 6 项全部通过；Ruff 和前端构建通过。Transformer 论文独立运行两次 GPU 推理，适配后的结构块完全一致；这仅证明本次两次运行一致，不是对其他文档或设备的确定性保证。

保留的 pdfplumber 合成旋转基线在 90/270 度页无法抽取文本，180 度页文字也存在倒序。浏览器测试验证这些页仍可渲染、缺块时显示限制，并仅对存在的块检查选中状态，不把旧基线当作准确文本结果。Marker 适配器另有全部四种旋转的坐标回归。

另对四页旋转样本执行了真实 Marker GPU 推理：0/90/180/270 度页均生成文本，共 12 块，逆旋转后的区域位置相近。但 90 度页段落内两句顺序颠倒，各页同一标题的层级也不一致；旋转文本阅读顺序和标题层级仍需复核，不能仅凭有块就判定抽取正确。

## 许可

版本资料依据 Marker 官方 `v1.9.3` 标签的 README，而非 2.x/master 文档。该版本 README 声明代码为 GPL，模型权重为修改后的 AI Pubs Open Rail-M，并列出研究、个人及低于指定规模初创企业的许可条件。商业部署应单独核对代码和权重许可；本次技术接入不构成商业授权审查。

参考：https://github.com/datalab-to/marker/tree/v1.9.3
