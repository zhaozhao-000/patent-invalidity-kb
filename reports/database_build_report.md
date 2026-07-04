# 数据库构建报告

- input_pdfs 总 PDF 数：331
- manifest 记录数：331
- 成功解析数：329
- 解析失败数：0
- 成功入库数：329
- 中国文件数：202
- 美国文件数：129
- unknown 文件数：0
- 重复文件数：2
- 中国案例库显示数：202
- 美国案例库显示数：129
- MinerU 成功数：331
- MinerU 失败数：0
- MinerU 未调用数：0
- 找不到原始 input PDF 的旧 JSON 记录：12

## 为什么旧网站只有 150 多个案例

旧版 `public/data/cases.json` 只写入 `include_in_kb=true` 且非重复的主案例。当前 `output/json` 中共有 333 条生成记录，其中 177 条被旧规则排除，主要原因是 `needs_ocr_review` 或正文过短。新流程不再静默丢弃这些文件，而是在 `all_cases_manifest.json` 和本报告中逐项记录状态。

## 未入库原因汇总

- same_content_hash：2

## 下一步人工复核清单

详见 `output/manual_review_jurisdiction.csv` 和 `output/manual_review_jurisdiction.json`。重点复核：标题置信度低、法律点为 pending_review、药物名称待人工确认、MinerU 未解析或解析失败的文件。
