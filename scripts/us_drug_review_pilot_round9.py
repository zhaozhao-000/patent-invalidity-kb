from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
US_CASES = ROOT / "public" / "data" / "us_cases.json"
US_OVERRIDES = ROOT / "data" / "manual_overrides" / "us_overrides.json"
REPORT_MD = ROOT / "reports" / "us_drug_review_pilot_round9.md"
REPORT_CSV = ROOT / "reports" / "us_drug_review_pilot_round9.csv"


CASES: dict[str, dict[str, Any]] = {
    "us_0211": {
        "patent_type": "用途/适应症",
        "result_cn": "程序驳回/未作实体无效判断",
        "outcome": "dismissed",
        "technology": "多发性硬化治疗用途",
        "summary": "要点：本案涉及 Biogen 的 US8399514B2，专利标题为 Treatment for multiple sclerosis。该文书不是普通 Final Written Decision，而是 Federal Circuit 撤销原最终书面决定并发回后，PTAB 按指令 dismiss 该 IPR。因此网页中不应把本案理解为全部无效、部分无效或维持有效；它的学习点在于 IPR 程序结果与实体有效性结论必须区分。最终结果为程序驳回，未作实体无效判断。",
    },
    "us_0213": {
        "patent_type": "其他",
        "result_cn": "部分无效",
        "outcome": "mixed",
        "technology": "acephate 农药颗粒制剂",
        "summary": "要点：本案虽然标题含 granules 和 formulation，但保护对象是 acephate 等 phosphoroamidothioates 的低粉尘、水分散性农药颗粒，不是人体药物制剂。PTAB 认定 Misselbrook、CN '588、JP '902 等足以使 claims 1–4 显而易见；但对于 claim 7 及其从属项，请求人没有证明为什么技术人员会在已有良好崩解性能且成本/效率因素相反的情况下再加入 disintegrating agent。最终结果为部分无效。",
    },
    "us_0222": {
        "patent_type": "其他",
        "result_cn": "全部无效",
        "outcome": "claims unpatentable",
        "technology": "multiplex PCR / 扩增抑制",
        "summary": "要点：本案涉及 multiplex PCR 中通过形成 stable secondary structure 降低短 amplicon 扩增效率，属于分子检测/研究工具方法，不是药物专利。PTAB 的关键判断是 reasonable expectation of success 必须对应权利要求实际范围；权利要求只要求 less efficient amplification，并不要求完全消除 short amplicons。因此 Gardner 与 Lao 的组合足以支持显而易见性。最终结果为全部无效。",
    },
    "us_0251": {
        "patent_number": "US10682414B2",
        "patent_title": "Intranasal epinephrine formulations and methods for the treatment of disease",
        "petitioner": "AMPHASTAR PHARMACEUTICALS, INC.",
        "patent_owner": "AEGIS THERAPEUTICS, LLC",
        "patent_type": "制剂/组合物",
        "secondary_patent_types": ["用途/适应症"],
        "result_cn": "部分无效",
        "outcome": "mixed",
        "technology": "鼻内 epinephrine 制剂 / anaphylaxis 治疗",
        "drug_name": "epinephrine",
        "summary": "要点：本案涉及鼻内 epinephrine 制剂及其用于治疗 anaphylaxis 的方法。PTAB 的重要判断是：如果“治疗疾病”的表述只是 preamble 中的预期用途，而权利要求实质步骤是给药方法和剂量，则现有技术 Potta 即使没有证明实际达到治疗效果，也可能因公开相同给药方案而破坏新颖性。该案适合关注用途/给药方法权利要求中 preamble 是否具有限定作用。最终结果为部分无效。",
    },
    "us_0252": {
        "patent_number": "US8541569B2",
        "patent_title": "Nucleosides, nucleotides and analogs for RNA synthesis",
        "petitioner": "SHANGHAI HONGENE BIOTECH CORP.",
        "patent_owner": "CHEMGENES CORP.",
        "patent_type": "制备方法/中间体",
        "result_cn": "全部无效",
        "outcome": "claims unpatentable",
        "technology": "RNA 合成构件 / nucleoside 中间体",
        "summary": "要点：本案涉及用于高纯度 RNA 合成和 3' 端修饰的 nucleoside/nucleotide building blocks。PTAB 认为 Aerschot 已经精确公开了被挑战权利要求中的关键结构，足以构成 anticipation；在化学中间体或核酸合成构件案件中，一篇现有技术若直接落入具体结构或 species，通常比泛泛的组合动机更有杀伤力。最终结果为全部无效。",
    },
    "us_0262": {
        "patent_type": "其他",
        "result_cn": "部分无效",
        "outcome": "mixed",
        "technology": "植物/原料溶质萃取设备与工艺",
        "summary": "要点：本案涉及从 source material 中萃取 solute 的闭环设备和工艺，应用背景更接近植物材料、essential oil 或 cannabis extraction，不是药物制剂或活性成分专利。PTAB 认定 Britt 或 Hebert 等现有技术足以使 claims 1、7–17 不可专利；但对 claims 2–6、18–20，请求人没有充分说明采用多个 extract containers/separation chambers 的具体改进或组合理由。最终结果为部分无效。",
    },
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    data = load_json(US_CASES)
    cases = data.get("cases", data) if isinstance(data, dict) else data
    by_id = {case["case_id"]: case for case in cases}
    overrides = load_json(US_OVERRIDES) if US_OVERRIDES.exists() else {}
    rows: list[dict[str, Any]] = []

    for case_id, review in CASES.items():
        case = by_id[case_id]
        existing = overrides.get(case_id, {})
        confidence = {**case.get("confidence", {}), **existing.get("confidence", {})}
        confidence.update({"summary": 0.84, "patent_type": 0.86})
        deep_review = {
            **existing.get("deep_review", {}),
            "technology_context": review["technology"],
            "final_result_cn": review["result_cn"],
            "drug_pilot_round": "ninth_remaining_auto_cleanup",
        }
        override = {
            **existing,
            "summary": review["summary"],
            "summary_source": "remaining_auto_cleanup_round9",
            "summary_review_required": False,
            "patent_type": review["patent_type"],
            "patent_type_basis": f"第九轮剩余自动摘要清理：{review['technology']}。",
            "outcome": review["outcome"],
            "classification_review": {
                "recommended_patent_type": review["patent_type"],
                "reason": f"第九轮逐案复核：{review['technology']}，按真实技术对象重新分类。",
                "source": "us_drug_review_pilot_round9",
            },
            "deep_review": deep_review,
            "confidence": confidence,
            "review_required": False,
        }
        for key in [
            "patent_number",
            "patent_title",
            "petitioner",
            "patent_owner",
            "secondary_patent_types",
        ]:
            if key in review:
                override[key] = review[key]
        if "patent_number" in review:
            override["patent_numbers"] = [review["patent_number"]]
            override["main_patent_number"] = review["patent_number"]
            override["patent_number_source"] = "manual_review"
            override["patent_number_confidence"] = 0.9
        if "patent_title" in review:
            override["title"] = review["patent_title"]
        if "drug_name" in review:
            override["drug_name"] = review["drug_name"]
            override["drug_name_confidence"] = "manual_review"
            override["drug_info"] = {
                **case.get("drug_info", {}),
                **existing.get("drug_info", {}),
                "drug_name": review["drug_name"],
                "active_ingredient": review["drug_name"],
                "product_name": review["drug_name"],
                "source": "manual_review_round9",
                "confidence": 0.86,
                "review_required": False,
            }
        elif review["patent_type"] == "其他":
            override["drug_name"] = "非药物核心技术"
            override["drug_name_confidence"] = "not_drug_core"
            override["drug_info"] = {
                **case.get("drug_info", {}),
                **existing.get("drug_info", {}),
                "drug_name": "",
                "active_ingredient": "",
                "product_name": "非药物核心技术",
                "source": "manual_review_round9",
                "confidence": 0.84,
                "review_required": False,
            }
        overrides[case_id] = override
        rows.append(
            {
                "case_id": case_id,
                "patent_number": override.get("patent_number") or case.get("patent_number", ""),
                "proceeding_number": case.get("proceeding_number", ""),
                "patent_title": override.get("patent_title") or case.get("patent_title") or case.get("title") or "",
                "patent_type": override["patent_type"],
                "technology": review["technology"],
                "result_cn": review["result_cn"],
                "summary": review["summary"],
            }
        )

    write_json(US_OVERRIDES, overrides)
    REPORT_MD.write_text(render_markdown(rows), encoding="utf-8")
    write_csv(rows)


def render_markdown(rows: list[dict[str, Any]]) -> str:
    lines = [
        "# 美国案例第九轮试点：剩余自动摘要清理",
        "",
        f"- 处理案例数：{len(rows)}",
        "- 处理目标：清掉上一轮后剩余的 generated_from_full_text 自动摘要。",
        "- 处理方式：逐案补正结果、分类、标题/专利号，并把非药物核心案例从药物分类中清出。",
        "",
    ]
    for row in rows:
        lines.extend(
            [
                f"## {row['case_id']} - {row['patent_title']}",
                "",
                f"- 程序号：{row['proceeding_number']}",
                f"- 专利号：{row['patent_number']}",
                f"- 分类：{row['patent_type']}",
                f"- 技术方向：{row['technology']}",
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
                "technology",
                "result_cn",
                "summary",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
