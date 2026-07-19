from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
US_CASES = ROOT / "public" / "data" / "us_cases.json"
US_OVERRIDES = ROOT / "data" / "manual_overrides" / "us_overrides.json"
REPORT_MD = ROOT / "reports" / "us_drug_review_pilot_round8.md"
REPORT_CSV = ROOT / "reports" / "us_drug_review_pilot_round8.csv"


CASES: dict[str, dict[str, str]] = {
    "us_0214": {
        "category": "检测设备/生物分子检测",
        "result_cn": "全部无效",
        "summary": "要点：本案核心不是药物本身，而是用于检测 biomolecules 的 bioassay optical detection apparatus。对这类检测设备专利，PTAB 的审查重点通常落在光学检测结构、信号采集和系统组合是否已被现有技术公开或显而易见。本案应作为检测设备案例保留，不应归入生物制品或药物制剂分类。最终结果为全部无效。",
    },
    "us_0215": {
        "category": "检测设备/生物分子检测",
        "result_cn": "维持有效",
        "summary": "要点：本案同样涉及 bioassay optical detection apparatus，但 PTAB 未认定请求人完成不可专利证明。学习重点在于：检测设备或系统组合即使包含生物分子检测场景，也不能直接按药物专利处理；需要看请求人是否逐项证明光学检测结构、样本处理和读出方式被现有技术公开或可组合。最终结果为维持有效。",
    },
    "us_0225": {
        "category": "农业/植物乙烯反应",
        "result_cn": "全部无效",
        "summary": "要点：本案涉及 counteracting ethylene response in plants 的 formulation、制备和使用方法，技术场景是植物处理和农业应用，不是人体用药或创新药核心专利。虽然标题中有 formulation，但不能机械归入药物制剂；分类应服从真实应用对象。最终结果为全部无效。",
    },
    "us_0227": {
        "category": "医疗器械/眼科手术切口",
        "result_cn": "全部无效",
        "summary": "要点：本案涉及 creating ocular surgical and relaxing incisions 的方法和装置，核心是眼科手术设备或手术控制方案，不是药物、晶型或制剂。即使文书中出现医疗场景，也应区分药物专利与器械/手术方法专利。最终结果为全部无效。",
    },
    "us_0228": {
        "category": "医疗器械/眼科手术切口",
        "result_cn": "全部无效",
        "summary": "要点：本案与眼科手术切口装置和方法相关，重点是装置结构、切口参数或操作流程的现有技术比对。它不属于创新药企重点关注的化合物、抗体、用途、制剂或晶型专利，应归入其他。最终结果为全部无效。",
    },
    "us_0231": {
        "category": "遗传病检测",
        "result_cn": "待人工确认",
        "summary": "要点：本案标题显示为 methods for detection of genetic disorders，属于诊断检测方法而非治疗性药物专利。后续如果团队需要研究诊断方法的 101、102、103 或样本检测逻辑，可单独复核；在药物专利数据库中不应误标为生物制品/抗体。最终结果需要人工复核。",
    },
    "us_0235": {
        "category": "遗传病检测",
        "result_cn": "待人工确认",
        "summary": "要点：本案属于 genetic disorders detection 同族检测方法案例，核心价值在诊断检测流程、检测位点或数据判读是否被现有技术公开，而不是药物治疗方案。按当前药企学习目标，应归入其他并进入必要复核。最终结果需要人工复核。",
    },
    "us_0236": {
        "category": "农业/动物育种",
        "result_cn": "全部无效",
        "summary": "要点：本案涉及使用 sex-selected sperm cells 提高 swine 育种遗传进展，属于动物育种和农业技术，不是药物、抗体、制剂或用途专利。分类纠偏的关键是不能仅因出现生物学材料就归为生物制品/抗体。最终结果为全部无效。",
    },
    "us_0237": {
        "category": "遗传病检测",
        "result_cn": "待人工确认",
        "summary": "要点：本案为 genetic disorders detection 方向，主要关注检测方法或诊断流程的可专利性，而非药物治疗或药物产品保护。建议在当前创新药专利库中作为其他类保留，最终结论待人工复核。最终结果需要人工复核。",
    },
    "us_0238": {
        "category": "遗传病检测",
        "result_cn": "维持有效",
        "summary": "要点：本案属于遗传病检测方法案例，PTAB 未证明被挑战权利要求不可专利。对本库而言，重点是分类纠偏：诊断检测方法不应自动归入药物用途或生物制品。最终结果为维持有效。",
    },
    "us_0239": {
        "category": "遗传病检测",
        "result_cn": "维持有效",
        "summary": "要点：本案与 genetic disorders detection 相关，学习价值主要在诊断检测权利要求如何与现有技术比对，而不是药物专利法律点。当前分类应为其他，避免误导为创新药核心专利。最终结果为维持有效。",
    },
    "us_0242": {
        "category": "遗传病检测",
        "result_cn": "维持有效",
        "summary": "要点：本案仍属于遗传病检测方法同族案例，PTAB 未认定请求人证明不可专利。对药企检索而言，它不是化合物、抗体、制剂、用途或晶型案例，应作为其他类处理。最终结果为维持有效。",
    },
    "us_0267": {
        "category": "测序数据/duplex consensus sequencing",
        "result_cn": "维持有效",
        "summary": "要点：本案涉及 massively parallel DNA sequencing 中通过 duplex consensus sequencing 降低错误率，核心是测序数据准确性和读段一致性，不是药物产品本身。PTAB 未证明被挑战权利要求不可专利。最终结果为维持有效。",
    },
    "us_0271": {
        "category": "测序数据/duplex consensus sequencing",
        "result_cn": "全部无效",
        "summary": "要点：本案同样围绕 duplex consensus sequencing 降低测序错误率，审查重点在测序读段、错误校正和数据处理流程是否由现有技术教导。它属于研究工具/测序技术，不应归入生物制品或药物方法。最终结果为全部无效。",
    },
    "us_0274": {
        "category": "遗传变异检测系统",
        "result_cn": "维持有效",
        "summary": "要点：本案涉及 detecting genetic variants 的方法和系统，属于分子诊断或测序检测平台。对药企学习库而言，重点不是治疗药物保护，而是诊断检测系统的权利要求如何被挑战。最终结果为维持有效。",
    },
    "us_0279": {
        "category": "遗传分析系统",
        "result_cn": "全部无效",
        "summary": "要点：本案标题为 methods and systems for genetic analysis，属于遗传分析和检测系统，不是抗体或生物药产品。分类应按真实技术对象归入其他；若后续研究平台诊断专利，可再单独深挖其现有技术组合理由。最终结果为全部无效。",
    },
    "us_0280": {
        "category": "遗传分析系统",
        "result_cn": "全部无效",
        "summary": "要点：本案为 genetic analysis 系统/方法同族案例，技术核心在检测、分析和数据处理流程。它不属于创新药核心专利类型，不能仅因含有 genetic 或 biological 字样就归为生物制品/抗体。最终结果为全部无效。",
    },
    "us_0283": {
        "category": "单细胞核酸分析",
        "result_cn": "待人工确认",
        "summary": "要点：本案涉及 analyzing nucleic acids from single cells，属于单细胞核酸分析或测序工具。它可能与药物研发工具有关，但并不保护药物、抗体、制剂、晶型或治疗用途本身。最终结果需要人工复核。",
    },
    "us_0284": {
        "category": "单细胞核酸分析",
        "result_cn": "全部无效",
        "summary": "要点：本案涉及 single-cell nucleic acid analysis，审查重点应是样本分离、条形码/标签、扩增和测序分析流程是否被现有技术公开或组合。它属于测序工具平台，不应标为生物制品/抗体。最终结果为全部无效。",
    },
    "us_0285": {
        "category": "单细胞核酸分析",
        "result_cn": "全部无效",
        "summary": "要点：本案属于单细胞核酸分析同族案例，法律学习点在研究工具方法的 obviousness/anticipation 比对，而不是药物专利保护策略。分类纠偏为其他。最终结果为全部无效。",
    },
    "us_0291": {
        "category": "粪便样本处理/检测",
        "result_cn": "全部无效",
        "summary": "要点：本案涉及 fecal sample processing and analysis，包括血液检测，属于样本处理和诊断检测技术。它不保护药物活性成分或治疗用途，应归入其他。最终结果为全部无效。",
    },
    "us_0316": {
        "category": "农业/转基因玉米检测",
        "result_cn": "维持有效",
        "summary": "要点：本案涉及 corn event TC1507 及其检测方法，核心是农业生物技术和转基因事件检测，不是药物专利。即便包含 composition 或 detection language，也应按应用领域归入其他。最终结果为维持有效。",
    },
    "us_0317": {
        "category": "鼻用消费产品/非药物应用",
        "result_cn": "全部无效",
        "summary": "要点：本案标题为 electrostatically charged multi-acting nasal application, product, and method，现阶段更适合作为鼻用产品或非药物应用案例，而非创新药制剂。除非人工复核确认其保护对象是治疗性药物组合物，否则不应归入制剂/组合物。最终结果为全部无效。",
    },
    "us_0319": {
        "category": "多重测序/核酸模板识别",
        "result_cn": "全部无效",
        "summary": "要点：本案涉及 multiplex sequencing reaction 中维持核酸模板完整性和识别的技术，属于测序工作流或研究工具。分类纠偏重点是：核酸模板处理不等于核酸药物或生物制品。最终结果为全部无效。",
    },
    "us_0320": {
        "category": "日化/除臭组合物",
        "result_cn": "全部无效",
        "summary": "要点：本案涉及 deodorant compositions，属于日化或个人护理组合物，不是创新药制剂。虽然形式上是 composition，但药物分类不能只看词面，应看其用途和监管/治疗属性。最终结果为全部无效。",
    },
    "us_0321": {
        "category": "日化/除臭组合物",
        "result_cn": "全部无效",
        "summary": "要点：本案与 deodorant compositions 相关，属于个人护理产品组合物。对创新药企案例库而言，它不是药物制剂，应归入其他；如后续需要研究组合物显而易见性，可另作非药物案例处理。最终结果为全部无效。",
    },
    "us_0323": {
        "category": "日化/止汗除臭组合物",
        "result_cn": "全部无效",
        "summary": "要点：本案涉及 antiperspirant and deodorant compositions，核心是日化产品配方而非治疗性药物制剂。分类纠偏为其他，避免在药物制剂检索中产生噪音。最终结果为全部无效。",
    },
    "us_0324": {
        "category": "日化/止汗除臭组合物",
        "result_cn": "全部无效",
        "summary": "要点：本案属于 antiperspirant/deodorant compositions 同族案例，重点是个人护理组合物的现有技术比对。它不是药物制剂或适应症用途专利。最终结果为全部无效。",
    },
    "us_0325": {
        "category": "粪便样本处理/检测",
        "result_cn": "全部无效",
        "summary": "要点：本案涉及 fecal sample processing and analysis，属于诊断样本处理与检测方向，不是生物制品/抗体。分类应归入其他；后续若关注诊断检测专利，可再单独复核检测步骤和现有技术组合。最终结果为全部无效。",
    },
    "us_0326": {
        "category": "核酸调控分析/RACR",
        "result_cn": "维持有效",
        "summary": "要点：本案涉及 regulation analysis by cis reactivity, RACR，属于核酸调控分析或研究工具技术。它不是晶型、盐或溶剂合物专利，原分类明显偏离技术对象。最终结果为维持有效。",
    },
    "us_0327": {
        "category": "遗传标记评估",
        "result_cn": "维持有效",
        "summary": "要点：本案涉及 evaluating genetic markers 的方法和组合物，主要是遗传标记检测/评估技术。它不保护抗体或生物药产品，应归入其他。最终结果为维持有效。",
    },
    "us_0328": {
        "category": "多重生化检测信号编码",
        "result_cn": "维持有效",
        "summary": "要点：本案涉及 multiplexed biochemical assays 中的 signal encoding and decoding，属于检测平台和信号处理技术。它不是药物制剂；分类应为其他。最终结果为维持有效。",
    },
    "us_0330": {
        "category": "日化/除臭组合物",
        "result_cn": "全部无效",
        "summary": "要点：本案涉及 deodorant compositions，属于个人护理组合物。对本项目的创新药专利学习目标而言，应从药物分类中剔除，避免误导为制剂专利。最终结果为全部无效。",
    },
    "us_0331": {
        "category": "测序读段去重/数据识别",
        "result_cn": "全部无效",
        "summary": "要点：本案涉及 duplicate sequencing read 的识别，核心是测序数据处理和读段去重，不是药物或生物制品。分类纠偏为其他；若学习其法律点，应关注算法/检测流程与现有技术的对应关系。最终结果为全部无效。",
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
        confidence.update({"summary": 0.82, "patent_type": 0.92})
        deep_review = {
            **existing.get("deep_review", {}),
            "technology_context": review["category"],
            "final_result_cn": review["result_cn"],
            "drug_pilot_round": "eighth_non_drug_correction",
        }
        overrides[case_id] = {
            **existing,
            "summary": review["summary"],
            "summary_source": "non_drug_correction_round8",
            "summary_review_required": review["result_cn"] == "待人工确认",
            "patent_type": "其他",
            "secondary_patent_types": [],
            "patent_type_basis": "第八轮非药物核心案例纠偏：检测、测序、设备、农业、日化或研究工具不归入创新药核心药物分类。",
            "drug_name": "非药物核心技术",
            "drug_name_confidence": "not_drug_core",
            "drug_info": {
                **case.get("drug_info", {}),
                **existing.get("drug_info", {}),
                "drug_name": "",
                "active_ingredient": "",
                "product_name": "非药物核心技术",
                "source": "manual_review_round8",
                "confidence": 0.85,
                "review_required": review["result_cn"] == "待人工确认",
            },
            "classification_review": {
                "recommended_patent_type": "其他",
                "reason": f"第八轮纠偏：{review['category']}，不是化合物、抗体、用途、制剂、晶型或制备方法等创新药核心专利类型。",
                "source": "us_drug_review_pilot_round8",
            },
            "deep_review": deep_review,
            "confidence": confidence,
            "review_required": review["result_cn"] == "待人工确认",
        }
        rows.append(
            {
                "case_id": case_id,
                "patent_number": case.get("patent_number", ""),
                "proceeding_number": case.get("proceeding_number", ""),
                "patent_title": case.get("patent_title") or case.get("title") or "",
                "old_patent_type": case.get("patent_type", ""),
                "new_patent_type": "其他",
                "category": review["category"],
                "result_cn": review["result_cn"],
                "summary": review["summary"],
            }
        )

    write_json(US_OVERRIDES, overrides)
    REPORT_MD.write_text(render_markdown(rows), encoding="utf-8")
    write_csv(rows)


def render_markdown(rows: list[dict[str, Any]]) -> str:
    lines = [
        "# 美国案例第八轮试点：非药物核心案例纠偏",
        "",
        f"- 处理案例数：{len(rows)}",
        "- 处理目标：把检测、测序、设备、农业、日化、研究工具类案例从药物分类中清出，统一归为“其他”。",
        "- 原则：不是只看标题里的 composition、method、biomolecule、genetic 等词，而是看专利真正保护的技术对象。",
        "- 说明：这些案例仍可保留在数据库中，但不作为创新药核心专利案例优先学习。",
        "",
    ]
    for row in rows:
        lines.extend(
            [
                f"## {row['case_id']} - {row['patent_title']}",
                "",
                f"- 程序号：{row['proceeding_number']}",
                f"- 专利号：{row['patent_number']}",
                f"- 原分类：{row['old_patent_type']}",
                f"- 新分类：{row['new_patent_type']}",
                f"- 技术方向：{row['category']}",
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
                "old_patent_type",
                "new_patent_type",
                "category",
                "result_cn",
                "summary",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
