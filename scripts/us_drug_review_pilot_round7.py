from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
US_CASES = ROOT / "public" / "data" / "us_cases.json"
US_OVERRIDES = ROOT / "data" / "manual_overrides" / "us_overrides.json"
REPORT_MD = ROOT / "reports" / "us_drug_review_pilot_round7.md"
REPORT_CSV = ROOT / "reports" / "us_drug_review_pilot_round7.csv"

PILOT_IDS = [
    "us_0205",
    "us_0206",
    "us_0258",
    "us_0282",
    "us_0293",
    "us_0295",
    "us_0296",
    "us_0312",
    "us_0313",
    "us_0314",
    "us_0315",
]

SUMMARIES: dict[str, dict[str, str]] = {
    "us_0205": {
        "focus": "RNA phosphoramidite / anticipation / genus-species",
        "patent_type": "制备方法/中间体",
        "result_cn": "全部无效",
        "summary": "要点：核酸合成中间体或 phosphoramidite 权利要求如果以 Markush 或属概念覆盖具体化合物，现有技术公开落入该属的具体 species 即可构成 anticipation。本案涉及用于 5'→3' reverse RNA synthesis 的 phosphoramidites。PTAB 认为 Aerschot 已公开与权利要求落入范围相同的具体氟化核苷化合物，且专利权人未能通过 claim construction 或优先权抗辩避开该公开。最终结果为全部无效。",
    },
    "us_0206": {
        "focus": "RNA synthesis intermediate / anticipation",
        "patent_type": "制备方法/中间体",
        "result_cn": "全部无效",
        "summary": "要点：RNA 合成方法和中间体类专利的 anticipation 判断，关键是对比现有技术是否已经公开同一 phosphoramidite/solid support 结构及其在 reverse RNA synthesis 中的用途。本案涉及 3'-DMT-5'-CE ribonucleoside phosphoramidites 和对应 solid supports。PTAB 认为在先 '696 patent 已公开 claims 1、2 的核心结构和用途，足以预见被挑战权利要求。最终结果为全部无效。",
    },
    "us_0258": {
        "focus": "modified guide RNA / CRISPR / obviousness",
        "patent_type": "生物制品/抗体",
        "result_cn": "全部无效",
        "summary": "要点：CRISPR guide RNA 化学修饰的 obviousness，不只看 CRISPR 系统是否新，还要看 RNA 修饰领域是否已经教导相同修饰位置、修饰类型及改善稳定性/活性的动机。本案涉及 chemically modified guide RNA。PTAB 认为 Pioneer Hi-Bred 与 Krutzfeldt、Deleavey、Soutschek、Yoo 等文献组合已经给出相关修饰策略，专利权人的行业认可或复制证据不足以克服强显而易见性证明。最终结果为全部无效。",
    },
    "us_0282": {
        "focus": "nucleoside protecting group / oligonucleotide synthesis",
        "patent_type": "制备方法/中间体",
        "result_cn": "全部无效",
        "summary": "要点：寡核苷酸合成中保护基、nucleoside、phosphoramidite 和 solid support 的改进，如果现有技术已公开相同保护基或可预期的合成路线，通常难以仅凭“高纯度合成”效果维持专利性。本案涉及 N-2-acetyl protected guanine nucleosides 及其在 RNA/oligo synthesis 中的使用。PTAB 认为 Reddy、Gaur 等预见部分权利要求，Crooke、Pitsch、Fan、Scaringe 等组合使其余权利要求显而易见。最终结果为全部无效。",
    },
    "us_0293": {
        "focus": "PD-1 therapy / MSI-H cancer / anticipation",
        "patent_type": "用途/适应症",
        "result_cn": "全部无效",
        "summary": "要点：抗 PD-1 治疗按 biomarker 选择患者的用途权利要求，如果临床研究记录已经公开 MSI-H/dMMR 患者、pembrolizumab/PD-1 blockade 和治疗癌症结果，可能直接构成 anticipation。本案涉及 checkpoint blockade 治疗 microsatellite instability 高突变负荷肿瘤。PTAB 认为 MSI-H Study Record 已公开 claims 1–8 的核心治疗方法，Pernot、Benson、Brown、Duval 等进一步支持显而易见性。最终结果为全部无效。",
    },
    "us_0295": {
        "focus": "PD-1 therapy / MSI biomarker / clinical prior art",
        "patent_type": "用途/适应症",
        "result_cn": "全部无效",
        "summary": "要点：肿瘤免疫治疗中的患者分层限制，不能只因写入 MSI-H、MMR-deficiency 或 mutational burden 就当然形成可专利区别；关键是这些 biomarker 与 PD-1 therapy 的临床关联是否已经被公开。本案属于 checkpoint blockade/MSI 同族，PTAB 认为临床研究记录和肿瘤免疫文献已教导用 anti-PD-1 antibody 治疗该类患者，被挑战权利要求不可专利。最终结果为全部无效。",
    },
    "us_0296": {
        "focus": "PD-1 therapy / anticipation and fallback obviousness",
        "patent_type": "用途/适应症",
        "result_cn": "全部无效",
        "summary": "要点：当单一 clinical study record 已经披露患者 biomarker、治疗药物和疗效评价时，PTAB 可先按 anticipation 处理；即使某些细节被争议，相关综述和机制文献也可能作为 fallback obviousness 证据。本案涉及 checkpoint blockade and microsatellite instability 同族权利要求。PTAB 认为 MSI-H Study Record 及 Pernot、Benson 等组合足以击破被挑战权利要求。最终结果为全部无效。",
    },
    "us_0312": {
        "focus": "PD-1 therapy / broad claim set / anticipation",
        "patent_type": "用途/适应症",
        "result_cn": "全部无效",
        "summary": "要点：较宽的治疗方法 claim set 若覆盖 anti-PD-1 antibody 治疗 MSI/MMR-deficient cancer，现有临床研究记录可能同时击破独立和多项从属权利要求。本案涉及 claims 1–28。PTAB 认为 MSR 公开了多项核心限制，Pernot、Benson、Brown、Duval、Chapelle、Hamid 等文献进一步证明不同从属特征显而易见。最终结果为全部无效。",
    },
    "us_0313": {
        "focus": "PD-1 therapy / dependent cancer features",
        "patent_type": "用途/适应症",
        "result_cn": "全部无效",
        "summary": "要点：在 anti-PD-1/MSI 治疗同族案中，加入特定癌种、检测状态或治疗反应等从属限制，仍需与现有临床记录形成实质区别。本案涉及 claims 1–4、6–10、12–15。PTAB 认为 MSR 已预见多数治疗方法限制，Pernot、Benson、Chapelle、Hamid 等补充文献使其余特征显而易见。最终结果为全部无效。",
    },
    "us_0314": {
        "focus": "PD-1 therapy / MSI-H Study Record",
        "patent_type": "用途/适应症",
        "result_cn": "全部无效",
        "summary": "要点：若临床研究记录已经列明 MSI-H 患者接受 PD-1 blockade 并获得治疗评价，专利权人很难仅凭权利要求文字重组获得新的治疗用途保护。本案涉及 claims 1–7。PTAB 认为 MSI-H Study Record 逐项公开 claims 1–3、5–7，并且 Pernot、Brown、Duval、Benson、Chapelle、Hamid 等文献使其他限制显而易见。最终结果为全部无效。",
    },
    "us_0315": {
        "focus": "PD-1 therapy / large dependent claim set",
        "patent_type": "用途/适应症",
        "result_cn": "全部无效",
        "summary": "要点：对于大量从属权利要求，PTAB 会按患者类型、癌种、检测方法、抗体选择和治疗方案逐项对照 clinical study record 和补充文献。本案涉及 anti-PD-1 therapy for MSI/MMR-deficient cancer 的 claims 1–30。PTAB 认为 MSI-H Study Record 已预见大量权利要求，Brown、Duval、Benson、Koh、Ajani、Chapelle、Steinert、Hamid 等进一步证明其余从属特征显而易见。最终结果为全部无效。",
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
        title = case.get("patent_title") or case.get("title") or ""
        existing = overrides.get(case_id, {})
        overrides[case_id] = {
            **existing,
            "summary": review["summary"],
            "summary_source": "drug_review_pilot_7",
            "summary_review_required": False,
            "patent_type": review["patent_type"],
            "patent_type_basis": "第七轮药物相关案例试点：RNA/寡核苷酸合成、CRISPR guide RNA 和 PD-1/MSI 治疗用途人工复核。",
            "classification_review": {
                "recommended_patent_type": review["patent_type"],
                "reason": "第七轮试点，按药企关注的核酸药物工艺、中间体和肿瘤免疫治疗用途分类。",
                "source": "us_drug_review_pilot_round7",
            },
            "deep_review": {
                **existing.get("deep_review", {}),
                "legal_focus": review["focus"],
                "final_result_cn": review["result_cn"],
                "drug_pilot_round": "seventh",
            },
            "confidence": {
                **case.get("confidence", {}),
                "summary": 0.86,
                "patent_type": 0.86,
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
        "# 美国药物相关案例第七轮试点报告",
        "",
        f"- 试点案例数：{len(rows)}",
        "- 范围：RNA/寡核苷酸合成、CRISPR guide RNA 修饰、PD-1/MSI 肿瘤免疫治疗用途。",
        "- 口径：强调 anticipation、obviousness、biomarker 患者分层和工艺中间体的审查重点。",
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
