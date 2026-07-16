from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
US_CASES = ROOT / "public" / "data" / "us_cases.json"
US_OVERRIDES = ROOT / "data" / "manual_overrides" / "us_overrides.json"
REPORT_MD = ROOT / "reports" / "us_drug_review_pilot_round3.md"
REPORT_CSV = ROOT / "reports" / "us_drug_review_pilot_round3.csv"

PILOT_IDS = [
    "us_0208",
    "us_0212",
    "us_0221",
    "us_0230",
    "us_0241",
    "us_0253",
    "us_0257",
    "us_0261",
    "us_0263",
    "us_0277",
    "us_0287",
    "us_0292",
    "us_0294",
    "us_0300",
    "us_0305",
    "us_0306",
]

SUMMARIES: dict[str, dict[str, str]] = {
    "us_0208": {
        "focus": "immunogenic composition / obviousness",
        "patent_type": "制剂/组合物",
        "result_cn": "全部无效",
        "summary": "要点：免疫原性组合物或疫苗组合物的 obviousness 判断，不只看各抗原组分是否分别已知，还要看现有技术是否给出将这些抗原、载体或佐剂组合到同一免疫组合物中的动机，以及是否会合理预期获得免疫保护效果。本案涉及 conjugated capsular saccharide antigens 的免疫组合物。PTAB 认为现有技术已经提供相关抗原组合和免疫用途的充分教导，专利权人的客观证据不足以克服显而易见性。最终结果为全部无效。",
    },
    "us_0212": {
        "focus": "medical use / inherency / reasonable expectation",
        "patent_type": "用途/适应症",
        "result_cn": "全部无效",
        "summary": "要点：精神疾病治疗用途类权利要求中，如果现有技术已经公开相同活性成分、相同患者或疾病场景，PTAB 会重点审查所谓疗效或机制限制是否只是给药后的固有结果，以及本领域技术人员是否有合理成功预期。本案涉及治疗 schizophrenia 的药物。PTAB 认为现有技术对相关治疗用途和效果已有足够教导，被挑战权利要求不能仅靠结果性表述避开 obviousness 或 inherency。最终结果为全部无效。",
    },
    "us_0221": {
        "focus": "isotope-enriched compound / obviousness / secondary considerations",
        "patent_type": "化合物专利",
        "result_cn": "全部无效",
        "summary": "要点：同位素富集或氘代/同位素替换类化合物，不能自动视为非显而易见；关键在于现有技术是否给出对已知活性分子进行同位素替换以改善药代、安全性或疗效的动机，以及专利权人的 secondary considerations 是否与权利要求范围有足够 nexus。本案涉及 isotope-enriched 3-amino-1-propanesulfonic acid derivatives。PTAB 认为现有技术组合和本领域常识足以支持 obviousness，客观证据不足以改变结论。最终结果为全部无效。",
    },
    "us_0230": {
        "focus": "VEGF dosing regimen / written description",
        "patent_type": "用途/适应症",
        "result_cn": "全部无效",
        "summary": "要点：VEGF antagonist 给药方案类专利的稳定性通常取决于两个问题：一是优先权或说明书是否支持具体给药间隔；二是现有临床文献是否已经教导该间隔具有合理疗效。本案涉及用 VEGF antagonist 治疗血管生成性眼病。PTAB 认为被挑战权利要求中的治疗方案未能避开现有技术，相关 written description 和 claim construction 抗辩不足以维持专利性。最终结果为全部无效。",
    },
    "us_0241": {
        "focus": "cell therapy / written description / anticipation",
        "patent_type": "生物制品/抗体",
        "result_cn": "维持有效",
        "summary": "要点：细胞治疗或 allogenic cell 相关权利要求的无效判断，需要把细胞来源、制备条件、分化状态和治疗用途逐项对应到现有技术公开。不能只因现有技术讨论相似细胞或临床用途，就推定其公开了权利要求限定的完整组合。本案涉及 allogenic cell 的临床衍生方法和治疗用途。PTAB 认为请求人未能证明现有技术 anticipates 或 renders obvious 被挑战权利要求。最终结果为维持有效。",
    },
    "us_0253": {
        "focus": "ophthalmic formulation / anticipation / written description",
        "patent_type": "制剂/组合物",
        "result_cn": "全部无效",
        "summary": "要点：眼科制剂权利要求如果通过成分、浓度、用途或性能参数限定，PTAB 会逐项比较现有眼科组合物是否已经公开这些限制；如果所谓性能是已知制剂自然具有的效果，也可能难以支撑专利性。本案涉及 ophthalmic composition。PTAB 认为现有技术已经公开或使显而易见被挑战组合物的关键限制，written description 和 claim construction 争议未能改变无效结论。最终结果为全部无效。",
    },
    "us_0257": {
        "focus": "guide RNA chemical modification / enablement",
        "patent_type": "生物制品/抗体",
        "result_cn": "全部无效",
        "summary": "要点：guide RNA 化学修饰类专利的 enablement 和 obviousness 判断，重点是说明书和现有技术是否足以教导哪些修饰位置、修饰类型能够实现稳定性或编辑效果。若现有技术已经给出相同或高度相近的修饰策略，单纯强调 CRISPR 场景通常不足以保住专利性。本案涉及 chemically modified guide RNA。PTAB 认为请求人证明了相关修饰方案不可专利。最终结果为全部无效。",
    },
    "us_0261": {
        "focus": "antibody dosing / clinical disclosure / anticipation",
        "patent_type": "生物制品/抗体",
        "result_cn": "全部无效",
        "summary": "要点：抗体皮下给药方案如果已经在临床试验、标签或研究资料中公开，PTAB 会严格比对患者群体、剂量、给药间隔和疗效限制；即使权利要求加入药代或结果性特征，也可能被认定为现有给药方案的固有结果。本案涉及 subcutaneously administered anti-IL-6 receptor antibody。PTAB 认为现有临床公开和组合文献足以破坏被挑战权利要求。最终结果为全部无效。",
    },
    "us_0263": {
        "focus": "peptide agonist / obviousness / reasonable expectation",
        "patent_type": "用途/适应症",
        "result_cn": "维持有效",
        "summary": "要点：受体激动剂或肽类治疗用途的 obviousness 判断，需要证明现有技术不仅公开了靶点和候选分子，还给出了用于特定组织炎症或癌变治疗的组合动机和 reasonable expectation of success。本案涉及 guanylate cyclase receptor agonists 的治疗用途。PTAB 认为请求人未能充分证明现有技术会使本领域技术人员合理预期获得权利要求治疗方案。最终结果为维持有效。",
    },
    "us_0277": {
        "focus": "gene therapy vector / written description",
        "patent_type": "用途/适应症",
        "result_cn": "维持有效",
        "summary": "要点：基因治疗载体类权利要求的 written description 和 obviousness 判断，关键是载体结构、调控元件、编码序列和治疗用途是否在现有技术或说明书中形成具体对应。不能只因 globin gene therapy 方向已知，就当然认为特定载体构型和治疗方案显而易见。本案涉及编码 human globin gene 的治疗载体。PTAB 认为请求人未能证明被挑战权利要求不可专利。最终结果为维持有效。",
    },
    "us_0287": {
        "focus": "early treatment regimen / obviousness",
        "patent_type": "用途/适应症",
        "result_cn": "全部无效",
        "summary": "要点：已知药物的新给药时间窗或低剂量方案，能否获得专利性，取决于现有技术是否已经提示该患者群体、给药时机和预期临床获益。本案涉及 myocardial infarction 后早期给予低剂量 colchicine。PTAB 认为现有技术已经提供在相关患者中早期使用 colchicine 的充分动机和成功预期，written description 抗辩未能避免无效结论。最终结果为全部无效。",
    },
    "us_0292": {
        "focus": "AAV vector function / obviousness",
        "patent_type": "生物制品/抗体",
        "result_cn": "维持有效",
        "summary": "要点：AAV 载体功能改进类权利要求的 obviousness 判断，需要具体证明现有技术会引导本领域技术人员采用权利要求中的改造方式，并合理预期提高载体功能。泛泛证明 AAV 载体和相关功能优化方向已知并不足够。本案涉及提高 AAV vector function 的方法。PTAB 认为请求人未能证明现有技术组合达到被挑战权利要求的关键限制。最终结果为维持有效。",
    },
    "us_0294": {
        "focus": "checkpoint blockade / inherency / written description",
        "patent_type": "用途/适应症",
        "result_cn": "全部无效",
        "summary": "要点：肿瘤免疫治疗用途类权利要求如果把患者分层、生物标志物或治疗反应写入权利要求，PTAB 会考察这些特征是否已由现有临床研究公开，或是否是实施已知治疗方案时自然识别的结果。本案涉及 checkpoint blockade 与 microsatellite instability。PTAB 认为现有技术已经教导相关患者群体和免疫检查点治疗方案，written description 或 claim construction 抗辩不足以维持专利性。最终结果为全部无效。",
    },
    "us_0300": {
        "focus": "small molecule antagonist / anticipation / enablement",
        "patent_type": "化合物专利",
        "result_cn": "全部无效",
        "summary": "要点：小分子拮抗剂类权利要求的 anticipation 和 obviousness 风险主要来自现有技术是否公开落入权利要求范围的具体化合物、Markush 结构或可实施制备路径。本案涉及 corticotropin releasing factor receptor antagonists。PTAB 认为现有技术对相关化合物结构和用途已有充分公开，说明书支持或 enablement 争议不足以保住被挑战权利要求。最终结果为全部无效。",
    },
    "us_0305": {
        "focus": "method of treatment / written description / enablement",
        "patent_type": "用途/适应症",
        "result_cn": "全部无效",
        "summary": "要点：治疗 Parkinson's disease 的方法权利要求需要在说明书和现有技术之间明确区分：如果权利要求覆盖较宽患者、剂量或治疗效果范围，说明书必须支持该范围；同时现有技术若已给出相同治疗路径，则 obviousness 风险较高。本案中，PTAB 认为请求人证明了相关治疗方法权利要求缺乏可维持的专利性基础。最终结果为全部无效。",
    },
    "us_0306": {
        "focus": "diagnosis and treatment / written description / enablement",
        "patent_type": "用途/适应症",
        "result_cn": "全部无效",
        "summary": "要点：诊断并治疗特定适应症的权利要求，若同时包含生物标志物、患者筛选和治疗步骤，PTAB 会分别审查说明书是否支持完整人群范围、治疗效果是否可实施，以及现有技术是否已经教导该治疗路径。本案涉及 vitiligo 的诊断和治疗。PTAB 认为请求人证明了被挑战权利要求在 written description、enablement 或 obviousness 方面存在缺陷。最终结果为全部无效。",
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
        overrides[case_id] = {
            **overrides.get(case_id, {}),
            "summary": review["summary"],
            "summary_source": "drug_review_pilot_3",
            "summary_review_required": False,
            "patent_type": review["patent_type"],
            "patent_type_basis": "第三轮药物相关案例试点：按药企关注的药物核心保护对象和法律判断标准人工复核。",
            "classification_review": {
                "recommended_patent_type": review["patent_type"],
                "reason": "第三轮药物相关案例试点，已排除明显设备、检测、测序、农业、日化或非药物核心案例。",
                "source": "us_drug_review_pilot_round3",
            },
            "deep_review": {
                **overrides.get(case_id, {}).get("deep_review", {}),
                "legal_focus": review["focus"],
                "final_result_cn": review["result_cn"],
                "drug_pilot_round": "third",
            },
            "confidence": {
                **case.get("confidence", {}),
                "summary": 0.86,
                "patent_type": 0.86,
            },
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
        "# 美国药物相关案例第三轮试点报告",
        "",
        f"- 试点案例数：{len(rows)}",
        "- 范围：继续从剩余美国案例中筛选药物相关案例，排除明显设备、检测、测序、农业、日化或非药物核心案例。",
        "- 口径：参照中国案例决定要点，突出法律点审查标准、本案适用和最终结果。",
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
    fieldnames = [
        "case_id",
        "patent_number",
        "proceeding_number",
        "patent_title",
        "patent_type",
        "legal_focus",
        "result_cn",
        "summary",
    ]
    with REPORT_CSV.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


if __name__ == "__main__":
    main()
