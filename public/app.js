const state = {
  cases: [],
  labels: {},
  filters: {
    region: new Set(),
    doc_type: new Set(),
    litigation_stage: new Set(),
    patent_type: new Set(),
    legal_issues: new Set(),
  },
};

const els = {
  meta: document.getElementById("meta"),
  searchInput: document.getElementById("searchInput"),
  sortBy: document.getElementById("sortBy"),
  resultCount: document.getElementById("resultCount"),
  caseList: document.getElementById("caseList"),
  emptyState: document.getElementById("emptyState"),
  needsOcrOnly: document.getElementById("needsOcrOnly"),
  reviewedOnly: document.getElementById("reviewedOnly"),
  hasRelatedOnly: document.getElementById("hasRelatedOnly"),
  hasSuspectedRelatedOnly: document.getElementById("hasSuspectedRelatedOnly"),
  noRelatedOnly: document.getElementById("noRelatedOnly"),
  resetFilters: document.getElementById("resetFilters"),
};

const regionLabels = { CN: "中国", US: "美国" };
const reviewLabels = {
  auto_tagged: "自动标注",
  manually_reviewed: "已人工复核",
  needs_manual_review: "需人工复核",
};
const outcomeLabels = {
  invalidated: "全部无效",
  partially_invalidated: "部分无效",
  maintained: "维持有效",
  reversed: "改判",
  vacated: "撤销",
  unknown: "未识别",
};

function labelFor(bucket, value) {
  return state.labels?.[bucket]?.[value] || regionLabels[value] || value;
}

function normalize(value) {
  return String(value || "").toLowerCase();
}

function searchableText(item) {
  return [
    item.title,
    item.summary,
    item.patent_number,
    item.decision_number,
    item.proceeding_number,
    item.court_case_number,
    item.court_name,
    item.petitioner,
    item.patentee_or_patent_owner,
    ...(item.keywords || []),
    ...(item.legal_issues || []).map((tag) => `${tag} ${labelFor("legal_issues", tag)}`),
    ...(item.patent_type || []).map((tag) => `${tag} ${labelFor("patent_type", tag)}`),
    ...(item.key_holdings || []),
    ...(item.important_quotes || []),
  ].join(" ").toLowerCase();
}

function hasAllSelected(itemValues = [], selectedSet) {
  if (selectedSet.size === 0) return true;
  return [...selectedSet].every((value) => itemValues.includes(value));
}

function passesFilters(item) {
  const query = normalize(els.searchInput.value).trim();
  if (query && !searchableText(item).includes(query)) return false;
  if (state.filters.region.size && !state.filters.region.has(item.region)) return false;
  if (state.filters.doc_type.size && !state.filters.doc_type.has(item.doc_type)) return false;
  if (state.filters.litigation_stage.size && !state.filters.litigation_stage.has(item.litigation_stage || "other")) return false;
  if (!hasAllSelected(item.patent_type, state.filters.patent_type)) return false;
  if (!hasAllSelected(item.legal_issues, state.filters.legal_issues)) return false;
  if (els.needsOcrOnly.checked && !item.needs_ocr) return false;
  if (els.reviewedOnly.checked && item.review_status !== "manually_reviewed") return false;
  if (els.hasRelatedOnly.checked && !(item.related_case_ids || []).length) return false;
  if (els.hasSuspectedRelatedOnly.checked && !(item.suspected_related_cases || []).length) return false;
  if (els.noRelatedOnly.checked && ((item.related_case_ids || []).length || (item.suspected_related_cases || []).length)) return false;
  return true;
}

function sortCases(items) {
  const mode = els.sortBy.value;
  return [...items].sort((a, b) => {
    if (mode === "region") return `${a.region}${a.title}`.localeCompare(`${b.region}${b.title}`, "zh-CN");
    if (mode === "title") return String(a.title).localeCompare(String(b.title), "zh-CN");
    return String(b.updated_at || "").localeCompare(String(a.updated_at || ""));
  });
}

function makeCheckbox(containerId, bucket, value, label) {
  const container = document.getElementById(containerId);
  const wrapper = document.createElement("label");
  wrapper.className = "check";
  wrapper.innerHTML = `<input type="checkbox" value="${escapeHtml(value)}"><span>${escapeHtml(label)}</span>`;
  const input = wrapper.querySelector("input");
  input.addEventListener("change", () => {
    if (input.checked) state.filters[bucket].add(value);
    else state.filters[bucket].delete(value);
    render();
  });
  container.appendChild(wrapper);
}

function buildFilters() {
  makeCheckbox("regionFilters", "region", "CN", "中国");
  makeCheckbox("regionFilters", "region", "US", "美国");
  for (const [tag, label] of Object.entries(state.labels.doc_type || {})) makeCheckbox("docTypeFilters", "doc_type", tag, label);
  for (const [tag, label] of Object.entries(state.labels.litigation_stage || {})) makeCheckbox("litigationStageFilters", "litigation_stage", tag, label);
  for (const [tag, label] of Object.entries(state.labels.patent_type || {})) makeCheckbox("patentTypeFilters", "patent_type", tag, label);
  for (const [tag, label] of Object.entries(state.labels.legal_issues || {})) makeCheckbox("legalIssueFilters", "legal_issues", tag, label);
}

function tagList(bucket, values = []) {
  if (!values.length) return "";
  return values.map((value) => `<span class="tag">${escapeHtml(labelFor(bucket, value))}</span>`).join("");
}

function listItems(values = []) {
  return values.slice(0, 3).map((value) => `<li>${escapeHtml(value)}</li>`).join("");
}

function escapeHtml(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function compactMeta(item) {
  const entries = [
    ["案号", item.case_number || item.court_case_number],
    ["决定号", item.decision_number],
    ["程序号", item.proceeding_number],
    ["专利号", item.patent_number],
    ["药物", item.drug_name],
    ["法院", item.court_name],
  ].filter(([, value]) => value);
  if (!entries.length) return "";
  return `<div class="meta-grid">${entries.map(([k, v]) => `<span><strong>${k}</strong>${escapeHtml(v)}</span>`).join("")}</div>`;
}

function caseCard(item) {
  const pdfLink = item.pdf_path ? `<a href="${escapeHtml(item.pdf_path)}" target="_blank" rel="noopener">打开 PDF</a>` : "";
  const duplicateCount = (item.duplicate_files || []).length;
  const relatedCount = (item.related_case_ids || []).length;
  const suspectedRelatedCount = (item.suspected_related_cases || []).length;

  return `
    <article class="case-card">
      <div class="case-head">
        <h2>${escapeHtml(item.title || item.id)}</h2>
        <div class="badges">
          <span class="badge">${escapeHtml(labelFor("doc_type", item.doc_type))}</span>
          <span class="badge">${escapeHtml(labelFor("region", item.region))}</span>
          ${item.litigation_stage ? `<span class="badge">${escapeHtml(labelFor("litigation_stage", item.litigation_stage))}</span>` : ""}
          <span class="badge">${escapeHtml(outcomeLabels[item.outcome] || item.outcome || "未识别")}</span>
          ${item.needs_ocr ? '<span class="badge warn">需 OCR</span>' : ""}
          ${duplicateCount ? `<span class="badge merge">已合并 ${duplicateCount} 个重复文件</span>` : ""}
          ${relatedCount ? `<span class="badge merge">相关案例 ${relatedCount}</span>` : ""}
          ${suspectedRelatedCount ? `<span class="badge warn">疑似相关 ${suspectedRelatedCount}</span>` : ""}
          <span class="badge">${escapeHtml(reviewLabels[item.review_status] || item.review_status)}</span>
        </div>
      </div>
      ${compactMeta(item)}
      <div class="tags">${tagList("patent_type", item.patent_type)}${tagList("legal_issues", item.legal_issues)}</div>
      <p class="summary">${escapeHtml(item.summary || "暂无摘要。")}</p>
      <div class="holdings">
        <h3>关键结论</h3>
        <ul>${listItems(item.key_holdings)}</ul>
      </div>
      <div class="links">${pdfLink}</div>
      <footer>更新：${escapeHtml(item.updated_at || "")}</footer>
    </article>
  `;
}

function render() {
  const filtered = sortCases(state.cases.filter(passesFilters));
  els.resultCount.textContent = filtered.length;
  els.caseList.innerHTML = filtered.map(caseCard).join("");
  els.emptyState.hidden = filtered.length !== 0;
}

function resetFilters() {
  els.searchInput.value = "";
  els.needsOcrOnly.checked = false;
  els.reviewedOnly.checked = false;
  els.hasRelatedOnly.checked = false;
  els.hasSuspectedRelatedOnly.checked = false;
  els.noRelatedOnly.checked = false;
  for (const set of Object.values(state.filters)) set.clear();
  document.querySelectorAll(".filters input[type='checkbox']").forEach((input) => {
    input.checked = false;
  });
  render();
}

async function init() {
  try {
    let response = await fetch("data/cases.json", { cache: "no-store" });
    if (!response.ok) response = await fetch("cases_index.json", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    state.cases = data.cases || [];
    state.labels = data.tag_labels || {};
    els.meta.textContent =
      `已加载 ${state.cases.length} 个入库文档。` +
      `排除 ${data.excluded_total || 0} 个，` +
      `自动关联 ${data.related_total || 0} 组，` +
      `疑似关联 ${data.suspected_related_total || 0} 组。`;
    buildFilters();
    render();
  } catch (error) {
    els.meta.textContent = "无法加载 cases_index.json。请先运行 scripts/ingest.py，或用本地静态服务器打开。";
    els.emptyState.hidden = false;
    els.emptyState.textContent = error.message;
  }
}

els.searchInput.addEventListener("input", render);
els.sortBy.addEventListener("change", render);
els.needsOcrOnly.addEventListener("change", render);
els.reviewedOnly.addEventListener("change", render);
els.hasRelatedOnly.addEventListener("change", render);
els.hasSuspectedRelatedOnly.addEventListener("change", render);
els.noRelatedOnly.addEventListener("change", render);
els.resetFilters.addEventListener("click", resetFilters);

init();
