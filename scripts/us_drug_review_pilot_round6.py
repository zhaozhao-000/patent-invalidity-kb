from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
US_CASES = ROOT / "public" / "data" / "us_cases.json"
US_OVERRIDES = ROOT / "data" / "manual_overrides" / "us_overrides.json"
REPORT_MD = ROOT / "reports" / "us_drug_review_pilot_round6.md"
REPORT_CSV = ROOT / "reports" / "us_drug_review_pilot_round6.csv"

PILOT_IDS = [
    "us_0220",
    "us_0226",
    "us_0245",
    "us_0247",
    "us_0275",
    "us_0289",
    "us_0290",
    "us_0311",
    "us_0286",
]

SUMMARIES: dict[str, dict[str, str]] = {
    "us_0220": {
        "focus": "NR composition / anticipation / obviousness",
        "patent_type": "制剂/组合物",
        "result_cn": "全部无效",
        "summary": "要点：营养/药物组合物权利要求如果只要求 nicotinamide riboside 与载体形成可口服组合物，现有技术中对同一成分、给药用途和常规载体的公开可能足以构成 anticipation 或 obviousness。本案涉及 NR/NAD 相关组合物及癌症或代谢相关用途。PTAB 认为 Stamler 已公开 NR 药物组合物，至少使 claim 2 显而易见；关于其他参考文献是否可用无需再判断。最终结果为全部无效。",
    },
    "us_0226": {
        "focus": "NR composition / prior art proof",
        "patent_type": "制剂/组合物",
        "result_cn": "维持有效",
        "summary": "要点：同一 NR/NAD 技术领域中，请求人仍需证明每项现有技术完整公开或提示权利要求组合。本案涉及含 nicotinamide riboside 的组合物和使用方法。PTAB 认为 Cell Article 与 Rosenbloom 的组合、以及 PCT Publication 均未充分证明 claims 1–3 被公开或显而易见；请求人未完成逐项举证责任。最终结果为维持有效。",
    },
    "us_0245": {
        "focus": "antibody purification ligand / partial invalidity",
        "patent_type": "生物制品/抗体",
        "result_cn": "部分无效",
        "summary": "要点：抗体纯化用 Protein A 配基案族中，PTAB 对主组合动机和从属限制分开判断。多数 claims 中关于 Domain C 配基、碱清洗稳定性和抗体/Fab 结合能力的限制已由 Linhult、Abrahmsen、Hober 等组合教导；但 claims 4 和 17 的具体限制未被充分证明。该案体现生物工艺工具专利中从属技术特征仍可能决定无效范围。最终结果为部分无效。",
    },
    "us_0247": {
        "focus": "antibody purification ligand / obviousness",
        "patent_type": "生物制品/抗体",
        "result_cn": "全部无效",
        "summary": "要点：针对抗体纯化配基的 obviousness，若现有技术已经公开 Protein A domain 改造、碱稳定性需求和抗体结合用途，专利权人需要指出权利要求中真正区别于组合文献的结构或性能。本案涉及包含 Staphylococcus aureus protein A domain C 的 chromatography ligand。PTAB 认为 Linhult、Abrahmsen、Hober 等组合足以覆盖 claims 1–7、10–20、23–26。最终结果为全部无效。",
    },
    "us_0275": {
        "title": "Hydrophilic linkers and their uses for conjugation of drugs to a cell binding molecules",
        "focus": "ADC linker / anticipation / obviousness",
        "patent_type": "生物制品/抗体",
        "result_cn": "部分无效",
        "summary": "要点：抗体药物偶联物 ADC linker 专利的判断重点，是现有技术是否公开特定 hydrophilic linker、细胞结合分子、药物负载和连接方式的组合。本案涉及用于将药物偶联至 cell binding molecules 的 hydrophilic linkers。PTAB 认为 Morales-Sanfrutos、Harris、Singh、Bhakta 等证明多数 claims 不可专利，但 claims 25、32–34 未被充分证明。最终结果为部分无效。",
    },
    "us_0289": {
        "focus": "botulinum neurotoxin delivery / obviousness",
        "patent_type": "用途/适应症",
        "result_cn": "全部无效",
        "summary": "要点：治疗剂递送系统如果核心是将 botulinum neurotoxin light chain 送入目标细胞，显而易见性会关注现有技术是否已经教导细胞膜 permeabilization、鼻部或其他局部治疗场景，以及将神经毒素递送用于治疗反应的动机。本案中，PTAB 认为 Makower、Fang、Edwards 等组合足以使 claims 1–3、7、9、10、17–25 显而易见。最终结果为全部无效。",
    },
    "us_0290": {
        "focus": "botulinum neurotoxin delivery / obviousness",
        "patent_type": "用途/适应症",
        "result_cn": "全部无效",
        "summary": "要点：botulinum neurotoxin 递送类权利要求不能只依赖“治疗剂递送”这一宽泛概念获得专利性；请求人若能证明现有技术已经公开目标组织、递送机制和治疗用途，组合动机和成功预期通常较强。本案与同族案一致，PTAB 认为 Makower、Fang、Edwards 等使 claims 1、2、5、8–10、12、14 显而易见。最终结果为全部无效。",
    },
    "us_0311": {
        "title": "Hydrophilic linkers and their uses for conjugation of drugs to a cell binding molecules",
        "focus": "ADC linker / duplicate proceeding / partial invalidity",
        "patent_type": "生物制品/抗体",
        "result_cn": "部分无效",
        "summary": "要点：本案与 us_0275 属同一 ADC linker 决定，适合作为 hydrophilic linker 和 drug loading 风险的学习案例。PTAB 认为多数权利要求中的 linker、cell binding molecule 和药物偶联组合可由 Morales-Sanfrutos、Harris、Singh、Bhakta 等现有技术证明不可专利；但 claims 25、32–34 未被充分证明。最终结果为部分无效。",
    },
    "us_0286": {
        "focus": "non-drug consumer product / motion to amend",
        "patent_type": "其他",
        "result_cn": "原权利要求取消，替代权利要求未准入",
        "summary": "要点：该案核心是天然 1,2-alkanediols 作为个人护理品等消费品防腐体系，并非创新药企重点关注的药物专利。PTAB 准许专利权人取消原 claims 1–6、8–10、22–28，但认为 proposed substitute claims 29–44 相对于 Wright '451 显而易见，未准入替代权利要求。该案主要用于标记“非药物核心/其他”，不作为药物专利学习重点。最终结果为原权利要求取消，替代权利要求未准入。",
    },
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    data = load_json(US_CASES)
    cases = data.get("cases", data) if isinstance(data, dict) else data
    by_id = {case["case_id"]: case for case in cases}
    overrides = load_json(US_OVERRIDES) if US_OVERRIDES.exists() else {}
    rows: list[dict[str, Any]] = []

    for case_id in PILOT_IDS:
        case = by_id[case_id]
        review = SUMMARIES[case_id]
        title = review.get("title") or case.get("patent_title") or case.get("title") or ""
        existing = overrides.get(case_id, {})
        overrides[case_id] = {
            **existing,
            "title": title,
            "patent_title": title,
            "summary": review["summary"],
            "summary_source": "drug_review_pilot_6",
            "summary_review_required": False,
            "patent_type": review["patent_type"],
            "patent_type_basis": "第六轮药物相关案例试点：补充 NR/NAD、ADC linker、botulinum delivery、抗体纯化工艺及非药物核心纠偏。",
            "classification_review": {
                "recommended_patent_type": review["patent_type"],
                "reason": "第六轮试点；对药物相关案例补充深度要点，对非药物消费品案例纠偏为其他。",
                "source": "us_drug_review_pilot_round6",
            },
            "deep_review": {
                **existing.get("deep_review", {}),
                "legal_focus": review["focus"],
                "final_result_cn": review["result_cn"],
                "drug_pilot_round": "sixth",
            },
            "confidence": {
                **case.get("confidence", {}),
                "summary": 0.84,
                "patent_type": 0.84,
            },
            "review_required": False,
        }
        rows.append(
            {
                "case_id": case_id,
                "patent_number": case.get("patent_number", ""),
                "proceeding_number": case.get("proceeding_number", ""),
                "patent_title": title,
                "patent_type": review["patent_type"],
                "legal_focus": review["focus"],
                "result_cn": review["result_cn"],
                "summary": review["summary"],
            }
        )

    write_json(US_OVERRIDES, overrides)
    REPORT_MD.write_text(render_markdown(rows), encoding="utf-8")
    write_csv(rows)


def render_markdown(rows: list[dict[str, Any]]) -> str:
    lines = [
        "# 美国药物相关案例第六轮试点报告",
        "",
        f"- 试点案例数：{len(rows)}",
        "- 范围：补充 NR/NAD、ADC linker、botulinum delivery、抗体纯化工艺，并纠正一个非药物核心案例。",
        "- 口径：继续突出法律判断和证据缺口，减少程序性复述。",
        "",
    ]
    for row in rows:
        lines.extend(
            [
                f"## {row['case_id']} - {row['patent_title']}",
                "",
                f"- 程序号：{row['proceeding_number']}",
                f"- 专利号：{row['patent_number']}",
                f"- 专利类型：{row['patent_type']}",
                f"- 法律点：{row['legal_focus']}",
                f"- 结果：{row['result_cn']}",
                f"- {row['summary']}",
                "",
            ]
        )
    return "\n".join(lines)


def write_csv(rows: list[dict[str, Any]]) -> None:
    with REPORT_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "case_id",
                "patent_number",
                "proceeding_number",
                "patent_title",
                "patent_type",
                "legal_focus",
                "result_cn",
                "summary",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
