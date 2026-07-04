# 生物医药专利案例知识库

这是一个本地生成、GitHub Pages 可部署的静态案例检索网站，用于管理中国和美国生物医药专利无效/专利挑战案例。

## 先进入项目目录

以后在 PowerShell 里先运行：

```powershell
cd "C:\Users\Administrator.DESKTOP-IL6JQAH\Desktop\无效决定\patent-invalidity-kb"
```

## 当前网站结构

```text
public/
├── index.html
├── cn/index.html
├── us/index.html
├── app.js
├── style.css
├── data/
│   ├── cn_cases.json
│   ├── us_cases.json
│   └── all_cases_manifest.json
└── pdfs/
```

团队访问 GitHub Pages 时进入 `public/index.html` 对应的网站入口，然后选择中国案例库或美国案例库。

## 重新生成案例数据

当前 PDF 已经通过 MinerU 解析完成。日常维护不要重新 OCR，直接运行：

```powershell
C:\Users\Administrator.DESKTOP-IL6JQAH\AppData\Local\Programs\Python\Python311\python.exe scripts\build_jurisdiction_data.py
```

脚本会生成或更新：

```text
public/data/cn_cases.json
public/data/us_cases.json
public/data/all_cases_manifest.json
reports/review_queue.csv
reports/review_queue.md
reports/data_quality_report.md
```

## 人工修正字段

不要直接修改 `public/data/cn_cases.json` 或 `public/data/us_cases.json`，因为重新生成时会被覆盖。

请把人工修正写入：

```text
data/manual_overrides/cn_overrides.json
data/manual_overrides/us_overrides.json
```

示例：

```json
{
  "cn_0001": {
    "patent_title": "人工确认的专利名称",
    "patent_type": "化合物专利",
    "summary": "人工修正后的决定要点",
    "patent_owner": "专利权人名称",
    "invalidity_petitioner": "无效请求人名称"
  },
  "us_0205": {
    "patent_title": "Confirmed English Patent Title",
    "patent_type": "生物制品/抗体",
    "petitioner": "Petitioner name",
    "patent_owner": "Patent Owner name",
    "summary": "人工修正后的美国案例要点"
  }
}
```

重新运行 `build_jurisdiction_data.py` 后，manual_overrides 会优先于自动识别结果，后续重跑不会覆盖人工修正。

## 待复核清单

优先查看：

```text
reports/review_queue.csv
```

其中 `edit_file` 会告诉你应该修改 `cn_overrides.json` 还是 `us_overrides.json`。

数据质量概览在：

```text
reports/data_quality_report.md
```

## 本地人工编辑工具

可以用浏览器打开：

```text
tools/review_editor.html
```

该页面可以加载待复核清单、填写修正值，并导出 `cn_overrides.json` 或 `us_overrides.json`。导出后，把文件替换到 `data/manual_overrides/`，再重新运行 build 脚本。

注意：普通静态网页不能直接写回本地文件，所以编辑器采用“导出 JSON 文件”的方式。

## 美国专利标题缓存

如果美国案例自动无法识别 patent title，可以手动写入本地缓存：

```powershell
C:\Users\Administrator.DESKTOP-IL6JQAH\AppData\Local\Programs\Python\Python311\python.exe scripts\patent_lookup_us.py "US 10,123,456 B2" --title "Confirmed patent title"
```

缓存位置：

```text
data/external/us_patents_cache.json
```

重新运行 build 脚本后，美国案例标题会优先使用缓存中的 patent title。

## 分享给团队

GitHub Pages 适合团队访问，地址形如：

```text
https://用户名.github.io/patent-invalidity-kb/
```

PDF 链接使用相对路径，例如：

```text
pdfs/cn/example.pdf
pdfs/us/example.pdf
```

如果离线分享，请将整个 `case_library` 或仓库文件夹一起打包发送；仅发送 `index.html` 将无法打开本地 PDF。

## 安全

MinerU API Key 只能放在本地环境变量中，不要写入 HTML、JS、JSON、README 或提交到 GitHub。

`.gitignore` 已排除常见密钥文件和 MinerU zip 原始包目录。
