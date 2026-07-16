from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
US_CASES = ROOT / "public" / "data" / "us_cases.json"
US_OVERRIDES = ROOT / "data" / "manual_overrides" / "us_overrides.json"
REPORT_MD = ROOT / "reports" / "us_drug_review_pilot.md"
REPORT_CSV = ROOT / "reports" / "us_drug_review_pilot.csv"

PILOT_IDS = [
    "us_0216",
    "us_0223",
    "us_0229",
    "us_0232",
    "us_0240",
    "us_0250",
    "us_0259",
    "us_0260",
    "us_0269",
    "us_0288",
    "us_0298",
    "us_0299",
    "us_0307",
    "us_0308",
    "us_0309",
]

SUMMARIES: dict[str, dict[str, str]] = {
    "us_0216": {
        "focus": "priority / written description",
        "patent_type": "制剂/组合物",
        "result_cn": "维持有效",
        "summary": "要点：涉及后续公开能否作为现有技术时，PTAB 先判断被挑战权利要求是否能够享有较早优先权日；如果说明书已经足以支持相关治疗组合物和用途，则较晚公开不能作为现有技术使用。本案中，请求人依赖 Allgenesis PCT 挑战治疗翼状胬肉的组合物/方法，但 PTAB 认为相关权利要求能够获得较早有效申请日，因此该 PCT 不能作为可用现有技术。最终结果为维持有效。",
    },
    "us_0223": {
        "focus": "obviousness / reasonable expectation of success",
        "patent_type": "用途/适应症",
        "result_cn": "全部无效",
        "summary": "要点：给药途径或给药装置类权利要求的 obviousness 判断，重点在于现有技术是否给出采用该给药方式的动机，以及本领域技术人员是否会预期其能够实现治疗效果。本案涉及吸入给药 treprostinil；PTAB 认为现有技术已经教导相关治疗用途、吸入给药方案和计量吸入装置，请求人也证明了组合动机和 reasonable expectation of success。专利权人的客观证据不足以克服该显而易见性结论。最终结果为全部无效。",
    },
    "us_0229": {
        "focus": "dosing regimen / priority / obviousness",
        "patent_type": "用途/适应症",
        "result_cn": "全部无效",
        "summary": "要点：给药间隔或治疗方案类专利不能只依靠已知药物本身获得稳定性；关键在于说明书和优先权文件是否支持具体给药方案，以及现有技术是否已经给出采用该方案的合理路径。本案涉及 VEGF antagonist 治疗血管生成性眼病的给药方案。PTAB 围绕优先权、written description 和现有技术对给药频率的教导进行判断，认为被挑战权利要求未能避免现有技术挑战。最终结果为全部无效。",
    },
    "us_0232": {
        "focus": "protein mutant / obviousness",
        "patent_type": "生物制品/抗体",
        "result_cn": "全部无效",
        "summary": "要点：蛋白突变体类专利的 obviousness 判断，不能只看目标蛋白是否已知，还要看现有技术是否教导了具体突变位点、功能改进方向以及本领域技术人员是否有理由作出该突变。本案涉及 Factor IX polypeptide mutant。PTAB 认为 Stafford、Manno 等文献组合已经给出获得相关 FIX 突变体及其用途的充分技术路径，专利权人的反驳和客观证据不足以改变显而易见性判断。最终结果为全部无效。",
    },
    "us_0240": {
        "focus": "formulation / inherency / priority",
        "patent_type": "制剂/组合物",
        "result_cn": "部分无效",
        "summary": "要点：制剂权利要求中，如果某些性能或参数是现有配方实施后必然产生的结果，PTAB 可能将其作为 inherency 处理；但对于未被现有技术充分公开或未必然产生的特征，仍需逐项证明。本案涉及鼻内 epinephrine 制剂及其治疗用途。PTAB 认定部分权利要求的制剂特征和效果已由现有技术公开或固有产生，但另一些权利要求仍未被请求人充分证明。最终结果为部分无效。",
    },
    "us_0250": {
        "focus": "motion to amend / written description / enablement",
        "patent_type": "用途/适应症",
        "result_cn": "原权利要求取消，替代权利要求未准入",
        "summary": "要点：在 PTAB 程序中，专利权人提出替代权利要求时，不能只缩小文字范围，还必须证明替代方案获得说明书支持、可实施，并能克服现有技术。本案涉及降低接受铂类化疗儿童患者耳毒性的治疗方法。PTAB 准许专利权人取消原 claim 1，但认为拟加入的 substitute claim 未满足准入要求，尤其没有充分克服 written description、enablement 或现有技术方面的问题。最终结果为原权利要求取消，替代权利要求未准入。",
    },
    "us_0259": {
        "focus": "method of treatment / inherency",
        "patent_type": "用途/适应症",
        "result_cn": "全部无效",
        "summary": "要点：治疗方法权利要求如果把已知给药方案的自然结果写成降低风险或改善结局，需要警惕 inherency 和 obviousness 风险。PTAB 会考察现有技术是否已经教导相同患者群体、相同治疗方案，以及所主张的临床效果是否是实施该方案时自然发生的结果。本案涉及降低心血管事件风险的治疗方法。PTAB 认为 Foley 等文献使被挑战权利要求显而易见，部分结果性限制不能挽救专利性。最终结果为全部无效。",
    },
    "us_0260": {
        "focus": "clinical disclosure / anticipation",
        "patent_type": "生物制品/抗体",
        "result_cn": "全部无效",
        "summary": "要点：抗体给药方案如果已在临床试验登记或临床资料中公开，PTAB 可能直接按 anticipation 处理；关键是该公开是否足以教导权利要求中的患者、剂量、给药途径和疗效相关限制。本案涉及皮下给药 anti-IL-6 receptor antibody。PTAB 认为 NCT 临床公开 anticipates 多数被挑战权利要求，个别权利要求虽未被该公开直接预见，但整体无效挑战仍成立。最终结果为全部无效。",
    },
    "us_0269": {
        "focus": "polymorph / inherency / anticipation",
        "patent_type": "晶型/盐/溶剂合物",
        "result_cn": "全部无效",
        "summary": "要点：晶型专利的 anticipation 和 inherency 判断，重点是现有技术制备方法是否必然或实际产生了被要求保护的晶型，以及表征证据是否足以对应权利要求。本案涉及 fingolimod hydrochloride 多晶型及其制备方法。PTAB 围绕 Mutz 等现有技术、内部文件和晶型表征证据判断，认为被挑战晶型权利要求未能避开现有技术。最终结果为全部无效。",
    },
    "us_0288": {
        "focus": "cocrystal / written description / enablement",
        "patent_type": "晶型/盐/溶剂合物",
        "result_cn": "全部无效",
        "summary": "要点：药物共晶或多组分固体形态权利要求，不能只用晶体工程的一般概念支持过宽范围；written description 和 enablement 要求说明书足以支持具体 API、共晶形成物及其相互作用。本案涉及含活性药物成分的 multiple-component solid phases。PTAB 认为 Hickey 等现有技术公开了相关限制，且专利权人未能依靠说明书支持或可实施性抗辩保住被挑战权利要求。最终结果为全部无效。",
    },
    "us_0298": {
        "focus": "deuterated compound / obviousness",
        "patent_type": "用途/适应症",
        "result_cn": "维持有效",
        "summary": "要点：氘代药物或氘代用途的 obviousness 判断，不能简单认为把已知活性分子氘代就是常规替换；PTAB 仍会考察现有技术是否给出针对该适应症、该氘代位置和预期药代改善的具体动机及 reasonable expectation of success。本案涉及 deuterated JAK inhibitors 治疗脱发。PTAB 认为请求人未能证明现有技术组合会使本领域技术人员合理预期获得权利要求方案。最终结果为维持有效。",
    },
    "us_0299": {
        "focus": "compound / ADC payload / written description",
        "patent_type": "化合物专利",
        "result_cn": "全部无效",
        "summary": "要点：化合物或 ADC payload 类权利要求，即使属于药物核心专利，也需要在结构范围、连接基团和用途之间建立充分支持；同时，如果现有技术已经公开落入权利要求范围的具体结构或给出明确改造路径，anticipation 或 obviousness 风险较高。本案涉及可与 ligand 偶联的 monomethylvaline compounds。PTAB 认为请求人以优势证据证明被挑战化合物权利要求不可专利。最终结果为全部无效。",
    },
    "us_0307": {
        "focus": "dosage / objective indicia / obviousness",
        "patent_type": "制剂/组合物",
        "result_cn": "部分无效",
        "summary": "要点：药物剂量或给药方案的 obviousness 判断中，客观证据可以作为反驳因素，但必须与被要求保护的技术方案具有足够 nexus，且强度足以克服现有技术的直接教导。本案涉及癫痫障碍治疗方法和组合物。PTAB 在考虑 objective indicia 后，仍认为部分 ganaxolone 静脉给药相关权利要求被现有技术教导或建议，但并非所有权利要求均被充分证明。最终结果为部分无效。",
    },
    "us_0308": {
        "focus": "process / enablement of prior art",
        "patent_type": "制备方法/中间体",
        "result_cn": "全部无效",
        "summary": "要点：当请求人依赖现有技术文献作 anticipation 时，专利权人可以挑战该文献是否 enabling；但负担在于证明本领域技术人员不能在无过度实验情况下实施该公开。本案涉及 endoxifen 的制备和使用方法。PTAB 认为专利权人未能证明 Ahmad 不是 enabling prior art，因此该文献可用于破坏被挑战权利要求的专利性。最终结果为全部无效。",
    },
    "us_0309": {
        "focus": "formulation / obviousness",
        "patent_type": "制剂/组合物",
        "result_cn": "全部无效",
        "summary": "要点：药物糖浆或混悬制剂的 obviousness 判断，通常会关注替代辅料是否已有用途教导、是否解决相同制剂问题，以及替换后是否具有可预期效果。本案涉及使用 agave syrup 等成分的 pharmaceutical syrup formulation or suspension。PTAB 认为现有技术已经给出用相关天然甜味/掩味成分替代传统辅料的动机，专利权人的反驳不足以避免显而易见性。最终结果为全部无效。",
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
        override = {
            **overrides.get(case_id, {}),
            "summary": review["summary"],
            "summary_source": "drug_review_pilot_2",
            "summary_review_required": False,
            "patent_type": review["patent_type"],
            "patent_type_basis": "第二轮药物相关案例试点：按药物核心保护对象和法律判断标准人工复核。",
            "classification_review": {
                "recommended_patent_type": review["patent_type"],
                "reason": "第二轮药物相关案例试点，已排除明显检测、测序、设备、日化或非药物核心案例。",
                "source": "us_drug_review_pilot",
            },
            "deep_review": {
                **overrides.get(case_id, {}).get("deep_review", {}),
                "legal_focus": review["focus"],
                "final_result_cn": review["result_cn"],
                "drug_pilot_round": "second",
            },
            "confidence": {
                **case.get("confidence", {}),
                "summary": 0.88,
                "patent_type": 0.88,
            },
        }
        overrides[case_id] = override
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
        "# 美国药物相关案例第二轮试点报告",
        "",
        f"- 试点案例数：{len(rows)}",
        "- 范围：从剩余美国案例中筛选药物相关案例，排除明显检测、测序、设备、日化或非药物核心案例。",
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
