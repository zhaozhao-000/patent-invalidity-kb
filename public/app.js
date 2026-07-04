const currentScript = document.currentScript;
const jurisdiction = currentScript?.dataset.jurisdiction || "cn";
const dataFile = currentScript?.dataset.file || "data/cases.json";

const state = {
  cases: [],
  labels: {},
  filters: {
    patent_type: new Set(),
    legal_points: new Set(),
    us_legal_points: new Set(),
    proceeding_type: new Set(),
  },
};

const els = {
  meta: document.getElementById("meta"),
  searchInput: document.getElementById("searchInput"),
  sortBy: document.getElementById("sortBy"),
  resultCount: document.getElementById("resultCount"),
  caseList: document.getElementById("caseList"),
  emptyState: document.getElementById("emptyState"),
  reviewRequiredOnly: document.getElementById("reviewRequiredOnly"),
  resetFilters: document.getElementById("resetFilters"),
};

function normalize(value) {
  return String(value || "").toLowerCase();
}

function asArray(value) {
  if (Array.isArray(value)) return value;
  if (!value) return [];
  return [value];
}

function labelFor(bucket, value) {
  return state.labels?.[bucket]?.[value] || value;
}

function escapeHtml(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function searchableText(item) {
  const legalValues = jurisdiction === "us" ? item.us_legal_points : item.legal_points;
  return [
    item.title,
    item.summary,
    item.patent_number,
    item.decision_number,
    item.proceeding_number,
    item.petitioner,
    item.patent_owner,
    item.drug_name,
    item.patent_type,
    item.status,
    item.outcome,
    item.proceeding_type,
    ...asArray(legalValues).map((tag) => `${tag} ${labelFor(jurisdiction === "us" ? "us_legal_points" : "legal_points", tag)}`),
  ].join(" ").toLowerCase();
}

function hasSelected(value, selectedSet) {
  if (!selectedSet.size) return true;
  return selectedSet.has(value);
}

function hasAllSelected(values, selectedSet) {
  if (!selectedSet.size) return true;
  const list = asArray(values);
  return [...selectedSet].every((value) => list.includes(value));
}

function passesFilters(item) {
  const query = normalize(els.searchInput.value).trim();
  if (query && !searchableText(item).includes(query)) return false;
  if (!hasSelected(item.patent_type, state.filters.patent_type)) return false;
  if (jurisdiction === "us") {
    if (!hasAllSelected(item.us_legal_points, state.filters.us_legal_points)) return false;
    if (!hasSelected(item.proceeding_type, state.filters.proceeding_type)) return false;
  } else if (!hasAllSelected(item.legal_points, state.filters.legal_points)) {
    return false;
  }
  if (els.reviewRequiredOnly?.checked && !item.review_required) return false;
  return true;
}

function sortCases(items) {
  const mode = els.sortBy?.value || "updated_at_desc";
  return [...items].sort((a, b) => {
    if (mode === "title") return String(a.title).localeCompare(String(b.title), "zh-CN");
    return String(b.case_id || "").localeCompare(String(a.case_id || ""), "zh-CN");
  });
}

function makeCheckbox(containerId, bucket, value, label) {
  const container = document.getElementById(containerId);
  if (!container || !value) return;
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

function uniqueValues(field) {
  const values = new Set();
  for (const item of state.cases) {
    for (const value of asArray(item[field])) {
      if (value) values.add(value);
    }
  }
  return [...values].sort((a, b) => String(labelFor(field, a)).localeCompare(String(labelFor(field, b)), "zh-CN"));
}

function buildFilters() {
  for (const value of uniqueValues("patent_type")) makeCheckbox("patentTypeFilters", "patent_type", value, value);
  if (jurisdiction === "us") {
    for (const value of uniqueValues("proceeding_type")) makeCheckbox("proceedingTypeFilters", "proceeding_type", value, value);
    for (const value of uniqueValues("us_legal_points")) makeCheckbox("legalIssueFilters", "us_legal_points", value, labelFor("us_legal_points", value));
  } else {
    for (const value of uniqueValues("legal_points")) makeCheckbox("legalIssueFilters", "legal_points", value, labelFor("legal_points", value));
  }
}

function tagList(bucket, values) {
  return asArray(values).map((value) => `<span class="tag">${escapeHtml(labelFor(bucket, value))}</span>`).join("");
}

function metaGrid(entries) {
  const rows = entries.filter(([, value]) => value);
  if (!rows.length) return "";
  return `<div class="meta-grid">${rows.map(([key, value]) => `<span><strong>${escapeHtml(key)}</strong>${escapeHtml(value)}</span>`).join("")}</div>`;
}

function confidenceBadge(item) {
  if (!item.review_required) return '<span class="badge merge">已自动入库</span>';
  return '<span class="badge warn">待复核</span>';
}

function cnCard(item) {
  return `
    <article class="case-card">
      <div class="case-head">
        <h2>${escapeHtml(item.title || item.case_id)}</h2>
        <div class="badges">
          <span class="badge">中国</span>
          <span class="badge">${escapeHtml(item.status || "待确认")}</span>
          ${confidenceBadge(item)}
        </div>
      </div>
      ${metaGrid([
        ["决定号", item.decision_number],
        ["专利号", item.patent_number],
        ["专利类型", item.patent_type],
        ["药物", item.drug_name],
      ])}
      <div class="tags">${tagList("legal_points", item.legal_points)}</div>
      <p class="summary">${escapeHtml(item.summary || "暂无摘要。")}</p>
      <div class="links">${item.pdf ? `<a href="${escapeHtml(item.pdf)}" target="_blank" rel="noopener">打开 PDF</a>` : ""}</div>
    </article>
  `;
}

function usCard(item) {
  const ob = item.orange_book_match || {};
  const drugLine = [item.drug_name, ob.active_ingredient].filter(Boolean).join(" / ");
  return `
    <article class="case-card">
      <div class="case-head">
        <h2>${escapeHtml(item.title || item.case_id)}</h2>
        <div class="badges">
          <span class="badge">US</span>
          <span class="badge">${escapeHtml(item.proceeding_type || "Unknown")}</span>
          <span class="badge">${escapeHtml(item.outcome || "unknown")}</span>
          ${confidenceBadge(item)}
        </div>
      </div>
      ${metaGrid([
        ["Patent No.", item.patent_number],
        ["Proceeding No.", item.proceeding_number],
        ["Petitioner", item.petitioner],
        ["Patent Owner", item.patent_owner],
        ["Patent Type", item.patent_type],
        ["Drug / Active", drugLine],
        ["Orange Book", ob.matched ? `${ob.product_name || "matched"} (${ob.application_number || ""})` : "no match"],
      ])}
      <div class="tags">${tagList("us_legal_points", item.us_legal_points)}</div>
      <p class="summary">${escapeHtml(item.summary || "No summary.")}</p>
      <div class="links">${item.pdf ? `<a href="${escapeHtml(item.pdf)}" target="_blank" rel="noopener">Open PDF</a>` : ""}</div>
    </article>
  `;
}

function render() {
  const filtered = sortCases(state.cases.filter(passesFilters));
  els.resultCount.textContent = filtered.length;
  els.caseList.innerHTML = filtered.map((item) => (jurisdiction === "us" ? usCard(item) : cnCard(item))).join("");
  els.emptyState.hidden = filtered.length !== 0;
}

function resetFilters() {
  els.searchInput.value = "";
  if (els.reviewRequiredOnly) els.reviewRequiredOnly.checked = false;
  for (const set of Object.values(state.filters)) set.clear();
  document.querySelectorAll(".filters input[type='checkbox']").forEach((input) => {
    input.checked = false;
  });
  render();
}

async function init() {
  try {
    const response = await fetch(dataFile, { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}: ${dataFile}`);
    const data = await response.json();
    state.cases = data.cases || [];
    state.labels = data.tag_labels || {};
    els.meta.textContent = `已加载 ${state.cases.length} 个${jurisdiction === "us" ? "美国" : "中国"}案例。`;
    buildFilters();
    render();
  } catch (error) {
    els.meta.textContent = `无法加载数据文件：${dataFile}`;
    els.emptyState.hidden = false;
    els.emptyState.textContent = error.message;
  }
}

els.searchInput?.addEventListener("input", render);
els.sortBy?.addEventListener("change", render);
els.reviewRequiredOnly?.addEventListener("change", render);
els.resetFilters?.addEventListener("click", resetFilters);

init();
