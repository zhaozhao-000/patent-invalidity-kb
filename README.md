# 生物医药专利无效决定本地知识库

这是一个本地静态 HTML 知识库。PDF 只在导入阶段处理一次，前端只读取 `public/data/cases.json` 或兼容的 `public/cases_index.json`，不需要数据库、后端服务器、聊天机器人或 RAG。

## 运行入库

```powershell
cd patent-invalidity-kb
python -m pip install -r requirements.txt
python scripts\ingest.py
```

## 本机预览

`localhost` 只适合本机预览，不能作为团队共享地址。

```powershell
cd public
python -m http.server 8000
```

浏览器访问 `http://localhost:8000`。

## GitHub Pages 团队共享

团队成员应访问 GitHub Pages 地址，例如：

```text
https://用户名.github.io/仓库名/
```

本项目使用 GitHub Actions 将 `public/` 目录发布到 GitHub Pages，工作流文件是：

```text
.github/workflows/deploy-pages.yml
```

发布目录必须包含：

```text
public/index.html
public/data/cases.json
public/pdfs/
```

在 GitHub 仓库中启用 Pages 时，选择：

```text
Source: GitHub Actions
```

每次推送到 `main` 或 `master` 后，Actions 会把 `public/` 发布到 GitHub Pages。

## 放置 PDF

- 中国文件：`input_pdfs/cn/`
- 美国文件：`input_pdfs/us/`

脚本会递归扫描子文件夹中的 `.pdf`。

## 入库阶段会做什么

- 提取 PDF 文本，扫描件标记 `needs_ocr`
- 如本机存在 Tesseract，尝试 OCR；否则标记 `ocr_status: unavailable`
- 从正文识别文档类型 `doc_type`
- 从正文判断是否进入主知识库 `include_in_kb`
- 从“决定如下 / 审查决定 / 结论 / 判决如下”等位置附近重新识别结论
- 提取专利名称作为主标题，文件名保留为 `secondary_title` / `file_name`
- 轻量识别药物名称，无法确认时写入人工复核清单
- 提取专利号、决定号、IPR/PGR/CBM 编号、法院案号、法院名称、诉讼阶段等字段
- 维护 `output/manifest.json`
- 识别重复文件和重复内容
- 关联同一专利或同一决定号的无效决定与后续诉讼判决
- 生成主索引、排除报告、关联报告和人工复核清单

## 自动标签原则

- `patent_type` 只保留一个主类型，优先根据专利名称、发明名称、涉案专利首页信息判断；无法稳定判断时标为 `other`，不再因为正文中出现“方法、组合物、制备”等词就全部打上。
- `legal_issues` 采用保守规则，优先读取“决定要点、无效理由、争议焦点、关于……、合议组认为、审查决定、Final Written Decision、Grounds、Analysis、Conclusion”等附近内容。
- 普通模板文字不直接作为法律点。例如美国 PTAB 文书中常规出现 `Claim Construction` 或 `priority date`，只有出现实质解释或优先权争议时才标为 `claim_construction` / `priority`。
- 自动标签是初筛。没有充分依据的标签会少标或不标，后续可在 `output/json/case_XXXX.json` 中人工修正。

## 主要输出

- `public/data/cases.json`
- `public/cases_index.json`
- `public/duplicates_report.html`
- `public/excluded_files_report.html`
- `public/related_cases_report.json`
- `output/manual_review.csv`
- `output/manual_review.json`
- `output/manifest.json`

## 新增字段

每个案例 JSON 会包含：

```json
{
  "patent_title": "",
  "drug_name": "",
  "drug_name_confidence": "high / medium / low / manual_required",
  "conclusion": "全部无效 / 部分无效 / 维持有效 / 待人工确认",
  "conclusion_basis": "",
  "ocr_status": "not_required / succeeded / failed / unavailable",
  "needs_manual_summary": false,
  "manual_patent_title": "",
  "manual_drug_name": "",
  "manual_summary": "",
  "manual_conclusion": "",
  "manual_notes": ""
}
```

人工字段优先级高于自动字段。修改 JSON 后运行：

```powershell
python scripts\build_index.py
```

## 哪些文档会入库

默认入库：

- 中国专利无效宣告请求审查决定
- 中国法院针对无效决定的一审、二审、再审行政判决或裁定
- 美国 PTAB 的 IPR、PGR、CBM Final Written Decision
- 美国 Federal Circuit、District Court 等涉及 PTAB、专利有效性、显而易见性、书面描述、可实施性等问题的判决

默认排除：

- 链接页、下载提示页、目录页、跳转页
- 正文很短且没有实质法律分析的网页打印件
- 空白页或需要 OCR 后才能判断的扫描件
- 重复文件或重复内容
- 无法自动判断价值的文件

排除不等于删除。所有排除记录都在 `public/excluded_files_report.html` 中。

## 人工复核

需要人工处理的案件会写入：

- `output/manual_review.csv`
- `output/manual_review.json`

如果需要补充信息，打开对应的 `output/json/case_XXXX.json`，填写：

```json
{
  "manual_patent_title": "",
  "manual_drug_name": "",
  "manual_summary": "",
  "manual_conclusion": "",
  "manual_notes": ""
}
```

然后运行 `python scripts\build_index.py`。

## 分享给他人

可分享目录结构为：

```text
case_library/
├── index.html
├── data/
│   └── cases.json
├── pdfs/
│   ├── xxx.pdf
│   └── yyy.pdf
└── assets/
```

本项目当前对应的是 `public/` 文件夹。需要分享时，请将整个文件夹打包发送；仅发送 `index.html` 将无法打开本地 PDF。

PDF 链接使用相对路径，例如 `pdfs/case_0003_cn.pdf`。

## OCR

当前脚本会检测本机是否有 `tesseract` 命令：

- 有：尝试把扫描 PDF 页面转图片并 OCR
- 没有：不中断导入，标记 `ocr_status: unavailable`，并写入人工复核清单

OCR 接口在 `scripts/extract_text.py` 的 `run_ocr_placeholder(pdf_path)`。

也可以运行独立 OCR 批处理脚本：

```powershell
python scripts\ocr_pdfs.py
```

脚本逻辑：

1. 扫描当前案例 JSON 对应的 `public/pdfs/` PDF；
2. 判断文本过短、扫描件或 `needs_ocr=true` 的文件；
3. 优先尝试本地 PaddleOCR；
4. PaddleOCR 不可用时尝试 OCRmyPDF + Tesseract；
5. 都不可用时不中断，写入：

```json
{
  "ocr_status": "unavailable",
  "extracted_text_status": "ocr_unavailable",
  "needs_manual_summary": true
}
```

OCR 文本输出到：

```text
public/data/ocr_texts/
```

运行后会刷新：

```text
output/manual_review.csv
output/manual_review.json
```

### 安装 PaddleOCR

PaddleOCR 是本项目首选 OCR 方案，适合中文扫描件。建议用 Python 3.10 或 3.11 单独建 OCR 环境：

```powershell
python -m venv .venv-ocr
.\.venv-ocr\Scripts\Activate.ps1
python -m pip install -r requirements-ocr.txt
python scripts\ocr_pdfs.py
```

当前这台机器是 Python 3.14，检测结果是：`paddleocr` 可在 pip 中找到，但 `paddlepaddle` 没有匹配 Python 3.14 的发行包。因此本机当前不能直接运行 PaddleOCR，建议换 Python 3.10/3.11 环境。

### 安装 OCRmyPDF / Tesseract

备用方案是 OCRmyPDF + Tesseract。它完全本地运行，但 Windows 上还需要安装 Tesseract 和 Ghostscript，并确保命令加入 PATH。

验证：

```powershell
tesseract --version
ocrmypdf --version
```

然后运行：

```powershell
python scripts\ocr_pdfs.py --engine ocrmypdf
```

## 导入外部 OCR / Markdown

如果使用 MinerU、ABBYY、Adobe Acrobat 等外部软件完成 OCR，可以不运行本项目内置 PaddleOCR。

推荐流程：

1. 用外部软件把 PDF 转为 `.md` 或 `.txt`。
2. 将结果放入：

```text
external_ocr/
```

3. 文件名尽量使用案例 ID 或 PDF 文件名，例如：

```text
external_ocr/case_0138.md
external_ocr/case_0138_cn.md
external_ocr/2013800552388.md
```

4. 导入外部 OCR 结果：

```powershell
python scripts\import_external_ocr.py
python scripts\build_index.py
```

脚本会把外部 OCR 文本写入：

```text
output/text/
public/data/ocr_texts/
```

并更新案例字段：

```json
{
  "ocr_status": "external_imported",
  "extracted_text_status": "external_ocr",
  "needs_ocr": false
}
```

无法按文件名匹配的 OCR 文件会在命令行列为 `Unmatched`，需要改名后重新导入。

## MinerU API 自动化

公开文书可以使用 MinerU 云端 API 自动转换，但不要把 API key 写进代码。先在 PowerShell 当前窗口设置环境变量：

```powershell
$env:MINERU_API_KEY="你的 API Key"
$env:MINERU_API_BASE="https://你的 MinerU API 域名"
```

如果官方文档给出的路径不是默认值，再设置：

```powershell
$env:MINERU_SUBMIT_PATH="/api/v4/extract/task"
$env:MINERU_TASK_PATH="/api/v4/extract/task"
```

先只测试 1 个文件：

```powershell
python scripts\mineru_api_ocr.py --limit 1
python scripts\import_external_ocr.py
python scripts\build_index.py
```

确认成功后再提高数量：

```powershell
python scripts\mineru_api_ocr.py --limit 20
python scripts\import_external_ocr.py
python scripts\build_index.py
```

该脚本会把 MinerU 返回的 Markdown 写入：

```text
external_ocr/case_XXXX.md
```

然后由 `import_external_ocr.py` 导入知识库。

## 限制

结论识别、药物名称识别、文档类型识别和案件关联都是规则驱动的初筛，不等同于法律判断。`待人工确认` 和 `manual_required` 应优先人工复核。
