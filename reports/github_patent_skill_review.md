# GitHub Patent Skill / Repo Review

## 搜索关键词

- patent skills
- patent parser USPTO
- USPTO patent data parser
- PTAB parser
- PTAB API
- inter partes review parser
- patent invalidity
- patent claims parser

## 候选仓库评估

| 仓库 | 用途 | 维护状态 | 专利号解析 | title / abstract / claims | PTAB / IPR / PGR 文书 | Python | Node | 依赖重量 | 许可证 | 建议 |
|---|---|---|---|---|---|---|---|---|---|---|
| newlany/patent-skills | 专利工作流/技能集合，偏专利撰写、OA、无效策略等 agent 说明 | README 日期 2026-05-30，较新 | 否 | 否 | 不是结构化 PTAB 解析器 | 部分脚本 | 否 | 不适合作为库 | 未在 README 中明确 | 不引入 |
| TamerKhraisha/uspto-patent-data-parser | 解析 USPTO Bulk Data grant full text | README 修改于 2020-09-07 | 可从 bulk data 中解析 | 可解析 abstract / claims 等字段 | 不解析 PTAB / IPR / PGR 文书 | 是 | 否 | 需要下载/读取 bulk zip，Pandas + BeautifulSoup | README 未明确许可证 | 不引入运行链路 |
| hopped/uspto-patents-parsing-tools | 老式 USPTO XML/SGML 解析工具 | README 修改于 2014-05-29，陈旧 | 可处理专利 XML | 可处理部分专利元数据 | 不解析 PTAB / IPR / PGR 文书 | 是 | 否 | 代码年代久，重复脚本较多 | MIT | 不引入 |
| opsomerto/uspto-parser | Spark/Scala wrapper，面向 USPTO bulk archive 转 parquet | README 修改于 2017-05-28 | 可处理 patentNb | schema 包含 abstract / claims | 不解析 PTAB / IPR / PGR 文书 | 否，Scala/Spark | 否 | 很重：Spark、sbt、Docker/Parquet | README 未明确许可证 | 不引入 |
| gabriele-di-bona/US-patents-extractor | 下载并解析 USPTO 全量 corpus 的 HPC/batch 脚本 | README 修改于 2023-02-03 | 可处理 UID/grant 数据 | 可提取 title / abstract 等 | 不解析 PTAB / IPR / PGR 文书 | Python + bash | 否 | 很重：全量 bulk data 可达 118GB，HPC 假设 | README 未明确许可证 | 不引入 |

## 结论

这些仓库主要解决 USPTO bulk patent corpus 的下载和解析，不解决本项目最关键的任务：从 PTAB Final Written Decision / Institution Decision 或法院文书中稳定抽取 proceeding number、challenged patent、Petitioner、Patent Owner、grounds、outcome，并再用专利号回查专利信息。

未找到可直接解决本项目美国无效决定阅读问题的成熟 skill，因此本项目采用自建美国文书解析 pipeline。

最终方案：

- 本项目新增 `scripts/us_case_parser.py`，专门解析 PTAB/法院文书结构。
- 本项目新增 `scripts/us_patent_lookup.py`，通过专利号优先查本地缓存；当前 PatentsView 旧查询端点返回 ODP HTML，批量构建默认不启用该旧端点，转用 Google Patents 补全标题/摘要并保留人工核对链接。
- 保留 `services/patent_providers/` 作为接口层，后续可接 USPTO 官方接口、PatentsView 或 Patent Connector 思路，但不把 Codex 内部 connector 作为网站构建依赖。
