from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
US_CASES = ROOT / "public" / "data" / "us_cases.json"
US_OVERRIDES = ROOT / "data" / "manual_overrides" / "us_overrides.json"
REPORT_MD = ROOT / "reports" / "us_drug_review_pilot_round5.md"
REPORT_CSV = ROOT / "reports" / "us_drug_review_pilot_round5.csv"

PILOT_IDS = [
    "us_0224",
    "us_0243",
    "us_0244",
    "us_0246",
    "us_0249",
    "us_0254",
    "us_0255",
    "us_0256",
    "us_0270",
    "us_0278",
    "us_0297",
    "us_0304",
]

SUMMARIES: dict[str, dict[str, str]] = {
    "us_0224": {
        "focus": "printed publication / inhaled treprostinil / obviousness",
        "patent_type": "用途/适应症",
        "result_cn": "全部无效",
        "summary": "要点：会议资料能否作为 printed publication，关键不在于是否正式期刊发表，而在于相关专业公众是否能够合理取得。本案涉及用 metered dose inhaler 吸入给药 treprostinil。PTAB 在 rehearing 后认定 Voswinckel JESC 和 JAHA 已在专业会议中充分分发，构成现有技术；结合既有 treprostinil 吸入治疗公开，请求人证明 claims 1–8 显而易见。最终结果为全部无效。",
    },
    "us_0243": {
        "focus": "antibody purification ligand / obviousness",
        "patent_type": "生物制品/抗体",
        "result_cn": "全部无效",
        "summary": "要点：抗体生产纯化用 Protein A 配基的 obviousness 判断，重点是现有技术是否已经教导具体 domain、突变或组合能够提高碱清洗耐受性和抗体结合性能。本案涉及包含 Staphylococcus aureus protein A domain C 的 chromatography ligand。PTAB 认为 Linhult、Abrahmsen、Hober 等文献共同给出配基设计和改造动机，请求人证明被挑战权利要求显而易见。最终结果为全部无效。",
    },
    "us_0244": {
        "focus": "antibody purification ligand / partial outcome",
        "patent_type": "生物制品/抗体",
        "result_cn": "部分无效",
        "summary": "要点：同一抗体纯化配基案族中，具体从属限制可能影响无效范围。PTAB 认为多数 claims 中关于 Protein A domain C 配基、碱稳定性和抗体纯化用途的限制已由 Linhult、Abrahmsen、Hober 等组合教导，但 claims 4 和 17 的特定限制没有被请求人充分证明。因此本案不是简单“全案无效”，而是多数权利要求无效、部分权利要求维持。最终结果为部分无效。",
    },
    "us_0246": {
        "focus": "antibody purification ligand / partial outcome",
        "patent_type": "生物制品/抗体",
        "result_cn": "部分无效",
        "summary": "要点：对于生物工艺工具类专利，PTAB 会逐项核对每个 dependent claim 是否被现有技术组合覆盖。本案涉及同一 Protein A domain C chromatography ligand 技术。PTAB 认定 claims 1–10、12–14、16–28、30–32、34–37 已被证明显而易见，但 claims 11 和 29 未被充分证明。该案说明，即使主组合动机成立，未被文献具体覆盖的从属技术特征仍可能保留。最终结果为部分无效。",
    },
    "us_0249": {
        "focus": "ocular nutrient formulation / anticipation",
        "patent_type": "制剂/组合物",
        "result_cn": "全部无效",
        "summary": "要点：眼健康营养组合物如果只是把 zeaxanthin 与其他已知 ocular-active nutrients 组合，专利性取决于具体组分和含量是否已由既有文献公开。本案涉及用于保护眼健康或治疗眼部疾病的 zeaxanthin 口服制剂。PTAB 认为 Lang 和 Barker 等现有技术已经公开多项权利要求中的核心组合特征；虽然个别 claim 对单一文献未成立，但整体被挑战 claims 12–14、16–21、23、24 最终均被认定不可专利。最终结果为全部无效。",
    },
    "us_0254": {
        "focus": "ophthalmic atropine formulation / obviousness",
        "patent_type": "制剂/组合物",
        "result_cn": "全部无效",
        "summary": "要点：低浓度眼科制剂的 obviousness 判断，会关注活性成分浓度、pH、均匀分布、稳定性和载体是否只是常规制剂优化。本案涉及低浓度 ophthalmic agent 治疗近视或近视进展的眼科组合物。PTAB 认为 Chia 和 Akorn 已经教导低浓度阿托品眼科制剂及相关制剂参数，本领域技术人员有动机进行常规调整并具有成功预期。最终结果为全部无效。",
    },
    "us_0255": {
        "focus": "ophthalmic formulation / obviousness combinations",
        "patent_type": "制剂/组合物",
        "result_cn": "全部无效",
        "summary": "要点：眼科组合物中所谓“低浓度”“均匀分布”或可接受载体等限制，如果现有商业制剂、处方文献或稳定性文献已经给出可行方案，通常难以单独支撑创造性。本案涉及同族 ophthalmic composition。PTAB 认为 Chia、Akorn、Kondritzer、Lund、Wu 等组合足以使 claims 1–7、11–20 显而易见。最终结果为全部无效。",
    },
    "us_0256": {
        "focus": "low-dose alpha-2 agonist / inherency / anticipation",
        "patent_type": "制剂/组合物",
        "result_cn": "全部无效",
        "summary": "要点：低浓度 alpha-2 adrenergic agonist 用于优先收缩小血管时，若现有技术已经公开相同或重叠浓度和用途，权利要求中关于“preferential vasoconstriction”的功能性表述可能被视为现有组合物的自然结果。本案涉及缓解眼红、鼻塞等场景的低浓度血管收缩组合物。PTAB 虽未接受所有 anticipation 理由，但最终认为请求人证明 claims 1–6 不可专利。最终结果为全部无效。",
    },
    "us_0270": {
        "focus": "botanical extract / obviousness / process-composition link",
        "patent_type": "制备方法/中间体",
        "result_cn": "维持有效",
        "summary": "要点：植物提取物药物组合物的 obviousness 不能只证明植物来源或治疗方向已知，还要证明现有技术会引导本领域技术人员采用具体处理条件以提高特定活性成分含量。本案涉及通过高温高压处理 Gynostemma pentaphyllum extract，提高 damulin A/B 含量并用于代谢疾病。PTAB 认为 Kim、WO 178 等组合没有充分证明会得到权利要求要求的提取物组成和治疗效果。最终结果为维持有效。",
    },
    "us_0278": {
        "focus": "lentiviral globin vector / anticipation / obviousness",
        "patent_type": "用途/适应症",
        "result_cn": "维持有效",
        "summary": "要点：基因治疗载体的 anticipation 需要现有技术公开完整载体构型，而不能只公开治疗目标或部分调控元件。本案涉及编码 functional beta-globin gene 并含 beta-globin locus control region 大片段的 recombinant lentiviral vector，用于治疗 hemoglobinopathies。PTAB 认为 May Thesis、May Article、May Abstract 等没有充分公开或提示权利要求要求的完整组合，Himanen 也不能弥补缺口。最终结果为维持有效。",
    },
    "us_0297": {
        "focus": "vaccine composition / written description",
        "patent_type": "制剂/组合物",
        "result_cn": "全部无效",
        "summary": "要点：疫苗或免疫组合物的 written description 要求说明书显示发明人已经占有具体抗原、组合物和免疫用途；发现病原体序列或提出研究方向本身，不等于支持所有免疫组合物权利要求。本案涉及 porcine circovirus type 3 免疫组合物。PTAB 认为说明书未充分支持 claims 1–16 的完整范围，尤其未体现对所要求保护免疫组合物的实际占有。最终结果为全部无效。",
    },
    "us_0304": {
        "focus": "small molecule treatment / written description",
        "patent_type": "用途/适应症",
        "result_cn": "全部无效",
        "summary": "要点：小分子治疗用途或药物组合物即使具体化合物已在说明书中出现，也仍需说明书支持权利要求覆盖的治疗方法、剂量和患者范围。本案涉及 CRF1 receptor antagonist Compound 1 治疗 congenital adrenal hyperplasia。PTAB 没有依赖 anticipation 或 obviousness，而是直接基于 written description 认定 specification 未充分支持 claims 1–19 的治疗范围。最终结果为全部无效。",
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
            "summary_source": "drug_review_pilot_5",
            "summary_review_required": False,
            "patent_type": review["patent_type"],
            "patent_type_basis": "第五轮药物相关案例试点：按药物/生物制品生产、制剂、给药方案、治疗用途和 written description 风险人工复核。",
            "classification_review": {
                "recommended_patent_type": review["patent_type"],
                "reason": "第五轮药物相关案例试点；排除明显农业、日化、检测平台和器械核心案例。",
                "source": "us_drug_review_pilot_round5",
            },
            "deep_review": {
                **existing.get("deep_review", {}),
                "legal_focus": review["focus"],
                "final_result_cn": review["result_cn"],
                "drug_pilot_round": "fifth",
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
        "# 美国药物相关案例第五轮试点报告",
        "",
        f"- 试点案例数：{len(rows)}",
        "- 范围：继续优化剩余自动摘要中的药物、制剂、生物制品生产、给药方案和治疗用途案例。",
        "- 口径：突出审查标准和证据判断，避免复述程序号、当事人或 PDF 基本信息。",
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
