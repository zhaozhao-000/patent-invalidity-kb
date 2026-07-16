from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
US_CASES = ROOT / "public" / "data" / "us_cases.json"
US_OVERRIDES = ROOT / "data" / "manual_overrides" / "us_overrides.json"
REPORT_MD = ROOT / "reports" / "us_deep_review_pilot.md"
REPORT_CSV = ROOT / "reports" / "us_deep_review_pilot.csv"

PILOT_IDS = [
    "us_0332",
    "us_0333",
    "us_0329",
    "us_0318",
    "us_0303",
    "us_0302",
    "us_0301",
    "us_0276",
    "us_0268",
    "us_0248",
]


DEEP_REVIEWS: dict[str, dict[str, str]] = {
    "us_0332": {
        "patent_type": "其他",
        "technology_context": "涉案专利涉及 NGS 场景下的靶向核酸序列富集和高效率文库构建，核心不是治疗药物，而是测序样本制备和文库制备工具。",
        "core_dispute": "核心争点是 Meyer 文献中的 3' 端片段、broken-T primer 和 SMART/anchored PCR 流程，是否公开或使显而易见 claim 1 要求的 enrichment 步骤。",
        "petitioner_arguments": "请求人主张 Meyer 的 3' end fragments 经后续 PCR 后相对其他 cDNA fragments 得到富集，并据此挑战 claims 1-3 and 5-22 的新颖性和显而易见性。",
        "patent_owner_arguments": "专利权人强调 Meyer 的 broken-T 设计只是解决 454 测序中 poly-A/T 同聚物导致的读数识别问题，不能证明物理文库中目标片段比例提高。",
        "tribunal_reasoning": "PTAB 接受 Dr. Meyer 关于 broken-T sequence 的解释，认为 16% reads 只能说明测序读数中 3' 端片段被合理代表，不能作为 enrichment 的定量证据；Meyer 未公开 claim 1 的 enrichment 限制，Siebert、Kelley、Caruccio、Bronner 也未补足该缺陷。",
        "outcome_reason": "请求人未能以优势证据证明 claims 1-3 and 5-22 不可专利，最终结果为维持有效。",
        "learning_points": "应区分 sequencing read representation 和 physical library enrichment。PTAB 不会把数据输出层面的 read 改善，直接等同于权利要求中的样本文库富集步骤。",
    },
    "us_0333": {
        "patent_type": "其他",
        "technology_context": "涉案专利与 us_0332 同族，涉及 NGS 靶向富集和文库生成方法，属于测序工具和样本制备技术，而非药物专利。",
        "core_dispute": "争点仍是 Meyer 是否公开权利要求要求的 enrichment，以及补充文献是否能弥补该核心限制。",
        "petitioner_arguments": "请求人将 Meyer 的 SMART/anchored PCR、broken-T primer 和后续测序读数解释为对目标序列或片段的富集，并提出新颖性和显而易见性挑战。",
        "patent_owner_arguments": "专利权人反驳称 Meyer 解决的是 454 测序读数质量和同聚物问题，不是提高物理样本中目标片段比例；相关组合文献只补充从属限制。",
        "tribunal_reasoning": "PTAB 认为请求人没有证明 Meyer 满足独立权利要求的核心 enrichment 限制。在独立权利要求基础缺失的情况下，针对从属权利要求的组合理由也不能成立。",
        "outcome_reason": "请求人未证明被挑战权利要求不可专利，最终结果为维持有效。",
        "learning_points": "同族 IPR 的学习价值在于：当主引用文献无法满足独立权利要求的核心技术步骤时，补充文献只教导从属特征通常不能挽救显而易见性组合。",
    },
    "us_0329": {
        "patent_type": "其他",
        "technology_context": "涉案专利题为 System and sensor array，核心是传感器阵列和生物分子指纹识别系统，属于检测平台或分析工具，不是药物本身。",
        "core_dispute": "争点在于现有技术是否公开或使显而易见用于识别生物分子指纹、分配标签并对应生物状态的系统和传感器阵列要素。",
        "petitioner_arguments": "请求人试图用现有传感器、检测和数据分析文献覆盖系统组件及标签分配功能，并主张相关权利要求不可专利。",
        "patent_owner_arguments": "专利权人围绕系统结构、传感器阵列与生物状态识别之间的对应关系，以及现有技术组合缺口进行抗辩。",
        "tribunal_reasoning": "PTAB 对不同权利要求分别评价，认为部分权利要求的要素和组合理由得到证明，另一些权利要求仍存在现有技术未充分覆盖或组合动机不足的问题。",
        "outcome_reason": "最终结果为部分无效：部分权利要求被证明不可专利，部分权利要求未被证明不可专利。",
        "learning_points": "系统检测类专利中，结果标签、传感器阵列和生物状态之间的功能性限定是否被现有技术具体教导，是比关键词匹配更重要的判断点。",
    },
    "us_0318": {
        "patent_type": "其他",
        "technology_context": "涉案专利涉及 multiplex sequencing 中维护核酸模板完整性和识别模板的方法，属于测序工作流和样本标识技术。",
        "core_dispute": "争点集中在现有技术是否公开保持模板完整性、识别核酸模板及多重测序流程中的关键步骤，并是否有充分组合理由。",
        "petitioner_arguments": "请求人依赖测序和核酸模板处理文献，主张相关步骤已被公开或可由本领域技术人员组合得到。",
        "patent_owner_arguments": "专利权人强调权利要求关注模板完整性和识别的一体化流程，现有技术没有按权利要求方式解决该问题。",
        "tribunal_reasoning": "PTAB 认为请求人没有充分证明现有技术满足关键流程限制，或组合后能达到权利要求要求的模板完整性和识别效果。",
        "outcome_reason": "请求人未证明被挑战权利要求不可专利，最终结果为维持有效。",
        "learning_points": "测序流程类案件不能只按关键词匹配。摘要应说明现有技术缺在哪个流程环节，以及该缺口为什么影响新颖性或显而易见性结论。",
    },
    "us_0303": {
        "patent_type": "用途/适应症",
        "technology_context": "涉案专利涉及 II 型 anti-CD20 抗体与选择性 BCL-2 inhibitor 的联合治疗方案，属于药物联合治疗和适应症类专利。",
        "core_dispute": "本案是对同一 PGR 的 rehearing 或更正型决定，核心在于最终书面决定中个别权利要求的不可专利结论是否需要因依附关系和书面描述分析而调整。",
        "petitioner_arguments": "请求人围绕说明书不足以支持 written description，挑战联合治疗给药方案及相关从属权利要求。",
        "patent_owner_arguments": "专利权人请求复审或更正，主张最终决定中关于从属权利要求的处理与其所依附权利要求的结论不一致。",
        "tribunal_reasoning": "PTAB 重点处理最终书面决定中的结论一致性问题，而不是重新全面审理所有实体争点；其分析围绕从属权利要求是否应随独立或上位权利要求的书面描述结论调整。",
        "outcome_reason": "最终结果为部分无效：部分权利要求被认定不可专利，部分权利要求未被证明不可专利或维持原处理。",
        "learning_points": "rehearing 决定通常不是重审所有实体问题，而是纠正或确认最终书面决定中的具体法律和逻辑处理。",
    },
    "us_0302": {
        "patent_type": "用途/适应症",
        "technology_context": "本案涉及 II 型 anti-CD20 抗体与选择性 BCL-2 inhibitor 的联合治疗，用于血液肿瘤等适应症场景。",
        "core_dispute": "法律争点是 written description：说明书是否足以表明发明人已经占有了权利要求要求保护的联合治疗范围。",
        "petitioner_arguments": "请求人主张原始披露没有充分描述被要求保护的联合治疗范围，特别是具体组合、剂量或患者治疗方案的广度。",
        "patent_owner_arguments": "专利权人依赖说明书实施例、临床和药理背景及本领域知识，主张本领域技术人员能够从原始披露识别该联合治疗发明。",
        "tribunal_reasoning": "PTAB 的判断重点不是 anti-CD20 抗体和 BCL-2 inhibitor 是否分别已知，也不是二者是否可以作为治疗方向被讨论，而是原始说明书是否把具体联合治疗方案、剂量范围和患者治疗方案与被要求保护的权利要求范围建立了足够对应关系。PTAB 没有接受从说明书中零散摘取多个披露再拼接出完整权利要求范围的做法。",
        "outcome_reason": "最终结果为部分无效：部分权利要求被认定不可专利，部分权利要求维持有效。",
        "learning_points": "§112 written description 的关键不是组合疗法是否有前景，而是原始说明书是否清楚表明发明人占有了权利要求的完整范围。",
        "summary_override": "要点：本案涉及 II 型 anti-CD20 抗体与选择性 BCL-2 inhibitor 的联合治疗。对于 written description，PTAB 重点考察说明书是否足以表明发明人已经占有了权利要求要求保护的联合治疗范围。单独公开两个药物或其各自用途，并不当然意味着说明书支持具体联合方案、剂量范围或患者治疗方案；也不能通过从说明书不同位置零散摘取内容，再拼接出完整权利要求范围。PTAB 对不同权利要求分别判断：部分权利要求与原始说明书披露之间缺乏足够对应关系，因此无效；部分权利要求仍能从说明书获得支持，因此维持有效。最终结果为部分无效。",
    },
    "us_0301": {
        "patent_type": "生物制品/抗体",
        "technology_context": "涉案专利题为 Engineered virus，核心属于工程化病毒、生物制品或载体技术。",
        "core_dispute": "争点在于请求人是否证明说明书支持、可实施性或现有技术挑战足以覆盖工程化病毒权利要求的具体结构和功能限制。",
        "petitioner_arguments": "请求人主张被挑战权利要求范围过宽，说明书或现有技术不足以支持专利权人主张的有效范围。",
        "patent_owner_arguments": "专利权人强调专利披露的工程化病毒构建和功能特征足以支撑权利要求，本领域技术人员能够理解和实施。",
        "tribunal_reasoning": "PTAB 认为请求人未能以优势证据证明关键无效理由成立，对工程化病毒相关限制的证明不足。",
        "outcome_reason": "请求人未证明被挑战权利要求不可专利，最终结果为维持有效。",
        "learning_points": "工程化病毒或载体类案件应重点看结构改造、功能效果和说明书支持之间的对应关系，而不应仅按 virus 关键词贴标签。",
    },
    "us_0276": {
        "patent_type": "用途/适应症",
        "technology_context": "涉案专利涉及 II 型 anti-CD20 antibody 与 selective Bcl-2 inhibitor 的组合治疗，属于药物联合用途和治疗方案。",
        "core_dispute": "核心争点是现有技术是否会使本领域技术人员有动机采用该抗体与 Bcl-2 抑制剂组合，并对疗效和安全性具有合理成功预期。",
        "petitioner_arguments": "请求人依赖既有抗 CD20 抗体、Bcl-2 抑制剂和血液肿瘤治疗资料，主张组合治疗显而易见。",
        "patent_owner_arguments": "专利权人强调组合治疗在疗效、毒性和患者反应方面存在不确定性，现有技术不足以提供合理成功预期。",
        "tribunal_reasoning": "PTAB 认为请求人未充分证明组合动机和合理成功预期，尤其不能用事后知识把两个药物机制简单拼接为显而易见的治疗方案。",
        "outcome_reason": "请求人未证明被挑战权利要求不可专利，最终结果为维持有效。",
        "learning_points": "药物组合疗法 obviousness 中，组合动机和 reasonable expectation of success 必须基于申请日前证据，而不是基于组合本身后来的成功。",
    },
    "us_0268": {
        "patent_type": "其他",
        "technology_context": "涉案专利题为 Methods for extracting solute from a source material，核心是从原料中提取溶质的工艺或设备方法，不是药物活性成分、制剂或治疗用途本身。",
        "core_dispute": "争点在于现有提取技术是否公开权利要求中的提取步骤、装置配置或工艺条件，以及请求人的组合理由是否充分。",
        "petitioner_arguments": "请求人主张相关提取工艺在现有技术中已经公开或可由本领域技术人员组合得到。",
        "patent_owner_arguments": "专利权人强调权利要求限定的提取流程和条件组合并非现有技术直接公开，请求人组合存在缺口。",
        "tribunal_reasoning": "PTAB 认为请求人未能充分证明关键工艺限制被公开或组合后自然得到，因此无效挑战未达到优势证据标准。",
        "outcome_reason": "请求人未证明被挑战权利要求不可专利，最终结果为维持有效。",
        "learning_points": "严格药物分类下，这类提取工艺如果没有指向具体药物活性成分或药物制剂，应归为“其他”，避免误导为药物专利。",
    },
    "us_0248": {
        "patent_type": "制备方法/中间体",
        "technology_context": "涉案专利涉及含 Staphylococcus aureus protein A domain C 的 chromatography ligand，用于抗体分离和纯化，属于生物制品生产纯化工具。",
        "core_dispute": "争点在于 Protein A 结构域、层析配体及抗体纯化用途相关权利要求是否被现有文献公开或显而易见。",
        "petitioner_arguments": "请求人依赖 Protein A 结构域和层析纯化文献，主张相关配体设计及其用于抗体分离的用途已被教导。",
        "patent_owner_arguments": "专利权人强调特定 domain C 配体结构、稳定性或纯化性能并非现有技术简单替换即可得到。",
        "tribunal_reasoning": "PTAB 对不同权利要求分别评价，部分权利要求因现有技术教导充分而不可专利，部分权利要求仍因特定结构或性能限制未被充分证明而存活。",
        "outcome_reason": "最终结果为部分无效：部分权利要求被认定不可专利，部分权利要求维持有效。",
        "learning_points": "分类不宜简单标为“抗体”，应关注真正保护对象是抗体纯化用层析配体。",
    },
}


PRIOR_ART_CONTEXT: dict[str, str] = {
    "us_0332": "主要现有技术 Meyer 公开了利用 SMART/anchored PCR 和 broken-T primer 处理 cDNA 3' 端片段，并用于 454 测序；请求人试图把该流程解释为对目标片段的 enrichment。",
    "us_0333": "主要现有技术 Meyer 同样公开了 cDNA 3' 端片段处理、broken-T primer 和后续测序流程；补充文献主要用于说明 PCR 或测序中的附加步骤。",
    "us_0329": "现有技术主要涉及传感器阵列、生物分子检测和数据标签分配系统；请求人据此主张传感器检测结果与生物状态识别之间的对应关系已被公开或容易组合。",
    "us_0318": "现有技术公开了多重测序、核酸模板处理和样本识别相关流程；争议在于这些文献是否真正公开保持模板完整性并完成权利要求限定的识别步骤。",
    "us_0303": "现有技术和原始披露围绕 II 型 anti-CD20 抗体、BCL-2 抑制剂及其在血液肿瘤治疗中的用途；本决定主要处理最终书面决定中部分权利要求结论是否需要调整。",
    "us_0302": "现有技术背景包括 anti-CD20 抗体、选择性 BCL-2 inhibitor 及二者在血液肿瘤治疗中的潜在联合用途；争议焦点不是两个靶点是否分别已知，而是原始说明书是否支持被要求保护的联合治疗范围。",
    "us_0301": "现有技术涉及工程化病毒、病毒载体构建及相关功能改造；争议在于这些披露是否足以破坏或削弱专利中具体工程化病毒方案的有效性。",
    "us_0276": "现有技术公开了 anti-CD20 抗体用于 B 细胞相关肿瘤治疗，也公开了 BCL-2 抑制剂的抗肿瘤用途；请求人据此主张二者联用具有组合动机和合理成功预期。",
    "us_0268": "现有技术公开了从原料中提取溶质的工艺和设备条件；争议在于这些公开是否覆盖权利要求中特定提取流程和条件组合。",
    "us_0248": "现有技术公开了 Protein A 结构域与抗体层析纯化用途；请求人据此主张含 domain C 的层析配体及其抗体纯化用途已被教导或显而易见。",
}


LEGAL_POINT_SUMMARY_OVERRIDES: dict[str, str] = {
    "us_0332": "要点：对于 anticipation 或 obviousness，PTAB 不仅看现有技术是否出现了相似实验步骤，还要判断该步骤是否公开了权利要求中具有专利性意义的技术限制。本案中，Meyer 公开了 SMART/anchored PCR、broken-T primer 和 454 测序中的 3' 端片段处理，但 PTAB 认为这些内容只能说明测序读数层面的代表性改善，不能证明样本文库中目标核酸序列相对于其他片段发生了 enrichment。请求人不能把 read representation 等同于 physical library enrichment，也不能用补充文献弥补主引用文献缺失的核心限制。最终结果为维持有效。",
    "us_0333": "要点：当独立权利要求的核心技术限制没有被主引用文献公开时，针对从属权利要求的补充文献通常不能单独挽救 anticipation 或 obviousness 挑战。本案中，Meyer 虽然公开了 cDNA 3' 端片段处理、broken-T primer 和测序流程，但未证明权利要求要求的 enrichment。PTAB 因此认为，请求人关于从属特征的组合理由不能弥补独立权利要求核心限制的缺失。最终结果为维持有效。",
    "us_0329": "要点：对于系统或检测平台类权利要求，obviousness 判断不能只看现有技术是否分别公开传感器、检测和数据分析模块，还要看现有技术是否给出将这些模块按照权利要求方式关联起来的具体教导。本案中，PTAB 对传感器阵列、标签分配和生物状态识别之间的对应关系逐项判断，认为部分权利要求的组合理由成立，部分权利要求仍缺少充分公开或组合动机。最终结果为部分无效。",
    "us_0318": "要点：对于测序流程类方法权利要求，anticipation 或 obviousness 的关键在于现有技术是否公开了权利要求限定的流程关系和技术效果，而不是是否出现了相同的测序关键词。本案中，请求人依赖多重测序和核酸模板处理文献，但 PTAB 认为其未充分证明现有技术满足维护模板完整性并完成模板识别的关键流程限制。最终结果为维持有效。",
    "us_0303": "要点：rehearing 决定的重点通常不是重新审理全部无效理由，而是检查最终书面决定中是否存在需要纠正的法律或逻辑处理。本案仍围绕 written description 展开，但 PTAB 主要处理从属权利要求结论是否应当随其依附的上位权利要求进行调整。对于此类决定，阅读重点应放在 PTAB 是否纠正了权利要求之间的结论一致性，而不是把它当作新的完整实体审查。最终结果为部分无效。",
    "us_0302": "要点：本案涉及 II 型 anti-CD20 抗体与选择性 BCL-2 inhibitor 的联合治疗。对于 written description，PTAB 重点考察说明书是否足以表明发明人已经占有了权利要求要求保护的联合治疗范围。单独公开两个药物或其各自用途，并不当然意味着说明书支持具体联合方案、剂量范围或患者治疗方案；也不能通过从说明书不同位置零散摘取内容，再拼接出完整权利要求范围。PTAB 对不同权利要求分别判断：部分权利要求与原始说明书披露之间缺乏足够对应关系，因此无效；部分权利要求仍能从说明书获得支持，因此维持有效。最终结果为部分无效。",
    "us_0301": "要点：对于工程化病毒或载体类权利要求，说明书支持、enablement 或现有技术挑战不能只停留在“病毒载体技术已知”的层面，而要对应到权利要求限定的具体结构改造和功能效果。本案中，请求人未能以优势证据证明专利披露不足以支持或实施被要求保护的工程化病毒方案，也未能证明现有技术覆盖关键限制。最终结果为维持有效。",
    "us_0276": "要点：药物联合治疗的 obviousness 判断，不能仅因两个药物或两个靶点分别已知，就当然认定其联用显而易见。PTAB 重点考察申请日前现有技术是否给出明确组合动机，以及本领域技术人员是否会对疗效和安全性具有 reasonable expectation of success。本案中，请求人未能充分证明 anti-CD20 antibody 与 Bcl-2 inhibitor 联用具有足够组合动机和合理成功预期。最终结果为维持有效。",
    "us_0268": "要点：对于工艺或设备方法权利要求，obviousness 分析应当落实到具体流程、装置配置和工艺条件，而不能只因现有技术同属“提取”领域就认定容易组合。本案中，请求人未能证明现有提取技术公开或自然导向权利要求中的特定步骤和条件组合，PTAB 因此认为无效挑战未达到优势证据标准。最终结果为维持有效。",
    "us_0248": "要点：对于生物制品生产纯化材料类专利，obviousness 判断应聚焦真正的保护对象及其结构和性能限制，而不是简单按“抗体纯化”概括。本案中，现有技术公开了 Protein A 结构域和抗体层析纯化用途，但 PTAB 对特定 domain C 层析配体的结构、稳定性和纯化性能限制分别判断，认定部分权利要求被现有技术充分教导，部分权利要求仍未被充分证明。最终结果为部分无效。",
}


def outcome_cn(outcome: str) -> str:
    normalized = (outcome or "").lower()
    if "not unpatentable" in normalized:
        return "维持有效"
    if normalized == "mixed" or ("unpatentable" in normalized and "not" in normalized):
        return "部分无效"
    if "unpatentable" in normalized:
        return "全部无效"
    return outcome or "待确认"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def clean_text(value: str, limit: int = 500) -> str:
    value = re.sub(r"\s+", " ", value or "").strip()
    return value[:limit].rstrip(" ,;。")


def find_evidence(text: str, needles: list[str], limit: int = 360) -> str:
    low = text.lower()
    for needle in needles:
        idx = low.find(needle.lower())
        if idx >= 0:
            start = max(0, idx - 120)
            return clean_text(text[start : idx + limit], limit)
    return ""


def summary_from_review(review: dict[str, Any]) -> str:
    if review.get("summary_override"):
        return str(review["summary_override"])
    parts = [
        "要点：",
        review["technology_context"],
        review["prior_art_context"],
        review["core_dispute"],
        review["tribunal_reasoning"],
        review["outcome_reason"],
    ]
    return "".join(parts)


def main() -> None:
    data = load_json(US_CASES)
    cases = data.get("cases", data) if isinstance(data, dict) else data
    by_id = {case["case_id"]: case for case in cases}
    overrides = load_json(US_OVERRIDES) if US_OVERRIDES.exists() else {}
    rows: list[dict[str, Any]] = []

    for case_id in PILOT_IDS:
        case = by_id[case_id]
        review: dict[str, Any] = dict(DEEP_REVIEWS[case_id])
        parsed_path = ROOT / str(case.get("parsed_markdown", ""))
        parsed_text = parsed_path.read_text(encoding="utf-8", errors="ignore") if parsed_path.exists() else ""
        review["case_id"] = case_id
        review["patent_title"] = case.get("patent_title") or case.get("title") or ""
        review["patent_number"] = case.get("patent_number", "")
        review["proceeding_number"] = case.get("proceeding_number", "")
        review["challenged_claims"] = case.get("challenged_claims", "")
        review["outcome"] = case.get("outcome", "")
        review["final_result_cn"] = outcome_cn(review["outcome"])
        review["prior_art_context"] = PRIOR_ART_CONTEXT.get(case_id, "")
        review["evidence"] = find_evidence(
            parsed_text,
            [
                "not persuaded",
                "written description",
                "reasonable expectation of success",
                "motivation to combine",
                "not shown",
                "ORDERED",
            ],
        )
        review["classification_review"] = {
            "recommended_patent_type": review["patent_type"],
            "reason": "严格药物分类试点：按专利真正保护对象分类；测序、检测、传感器、提取设备等非药物核心技术归“其他”。",
            "source": "us_deep_review_pilot",
        }
        review["summary_cn"] = LEGAL_POINT_SUMMARY_OVERRIDES.get(case_id, summary_from_review(review))

        prior_override = overrides.get(case_id, {})
        overrides[case_id] = {
            **prior_override,
            "summary": review["summary_cn"],
            "summary_source": "deep_review_pilot",
            "summary_review_required": False,
            "patent_type": review["patent_type"],
            "patent_type_basis": review["classification_review"]["reason"],
            "classification_review": review["classification_review"],
            "deep_review": {
                key: review.get(key, "")
                for key in [
                    "technology_context",
                    "prior_art_context",
                    "challenged_claims",
                    "core_dispute",
                    "petitioner_arguments",
                    "patent_owner_arguments",
                    "tribunal_reasoning",
                    "outcome_reason",
                    "final_result_cn",
                    "evidence",
                ]
            },
            "confidence": {
                **case.get("confidence", {}),
                "summary": 0.9,
                "patent_type": 0.9,
            },
        }
        rows.append(review)

    write_json(US_OVERRIDES, overrides)
    REPORT_MD.parent.mkdir(parents=True, exist_ok=True)
    REPORT_MD.write_text(render_markdown(rows), encoding="utf-8")
    write_csv(rows)


def render_markdown(rows: list[dict[str, Any]]) -> str:
    lines = [
        "# 美国案例深度阅读试点报告",
        "",
        f"- 试点案例数：{len(rows)}",
        "- 范围：仅美国 10 个试点案例；未重新 OCR；未修改中国摘要。",
        "- 口径：严格药物分类，非药物核心技术归“其他/待确认”。",
        "",
    ]
    for row in rows:
        lines.extend(
            [
                f"## {row['case_id']} - {row['patent_title']}",
                "",
                f"- 程序号：{row.get('proceeding_number', '')}",
                f"- 专利号：{row.get('patent_number', '')}",
                f"- 被挑战权利要求：{row.get('challenged_claims', '')}",
                f"- 结果：{row.get('final_result_cn', '')}",
                f"- 建议专利类型：{row['patent_type']}",
                f"- {row.get('summary_cn', '')}",
                f"- 技术背景：{row['technology_context']}",
                f"- 现有技术：{row['prior_art_context']}",
                f"- 核心争点：{row['core_dispute']}",
                f"- 请求人主张：{row['petitioner_arguments']}",
                f"- 专利权人抗辩：{row['patent_owner_arguments']}",
                f"- PTAB/法院判断：{row['tribunal_reasoning']}",
                f"- 最终结果理由：{row['outcome_reason']}",
                f"- 证据摘录：{row.get('evidence', '')}",
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
        "challenged_claims",
        "outcome",
        "final_result_cn",
        "patent_type",
        "technology_context",
        "prior_art_context",
        "core_dispute",
        "tribunal_reasoning",
        "evidence",
    ]
    REPORT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with REPORT_CSV.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


if __name__ == "__main__":
    main()
