const viewport = document.getElementById("viewport");
const reportList = document.getElementById("report-list");
const compareList = document.getElementById("compare-list");
const reportCount = document.getElementById("report-count");
const compareCount = document.getElementById("compare-count");
const shell = document.getElementById("shell");
const sidebarToggle = document.getElementById("sidebar-toggle");
const scanForm = document.getElementById("scan-form");
const compareForm = document.getElementById("compare-form");
const modeScan = document.getElementById("mode-scan");
const modeCompare = document.getElementById("mode-compare");
const heroStatus = document.getElementById("hero-status");

const badge = (text, tone = "") =>
  `<span class="badge ${tone}">${escapeHtml(text)}</span>`;

const escapeHtml = (value) =>
  String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");

const formatList = (items, empty = "None") => {
  if (!items || !items.length) {
    return `<li>${escapeHtml(empty)}</li>`;
  }
  return items.map((item) => `<li>${escapeHtml(item)}</li>`).join("");
};

const formatEvidence = (items, empty = "None detected") => {
  if (!items || !items.length) {
    return `<li>${escapeHtml(empty)}</li>`;
  }
  return items
    .map(
      (item) => `
        <li>
          <strong>${escapeHtml(item.strength)}</strong> <code>${escapeHtml(item.path)}</code>
          <div class="muted">${escapeHtml(item.label)}${item.reasons?.length ? ` | ${escapeHtml(item.reasons.join(", "))}` : ""}</div>
        </li>`
    )
    .join("");
};

const formatConfidence = (score) => {
  if (!score) {
    return `<li><strong>unknown</strong> <span class="muted">No score</span></li>`;
  }
  return `<li><strong>${escapeHtml(score.level)}</strong> <span class="muted">${escapeHtml(score.score)}</span><div class="muted">${escapeHtml((score.reasons || []).join(", ") || "No reasons")}</div></li>`;
};

const confidenceTone = (level) => {
  if (level === "high") return "ok";
  if (level === "medium") return "warn";
  return "bad";
};

let reportEntries = [];
let compareEntries = [];

const createNavButton = (item, type) => {
  const button = document.createElement("button");
  button.className = "nav-item";
  button.innerHTML = `<strong>${escapeHtml(item.label)}</strong><span>${escapeHtml(item.highlight)}</span>`;
  button.addEventListener("click", () => loadEntry(item, type, button));
  return button;
};

const updateCounts = () => {
  reportCount.textContent = String(reportEntries.length);
  compareCount.textContent = String(compareEntries.length);
};

const renderNavLists = () => {
  reportList.innerHTML = "";
  compareList.innerHTML = "";

  reportEntries.forEach((item) => reportList.appendChild(createNavButton(item, "report")));
  compareEntries.forEach((item) => compareList.appendChild(createNavButton(item, "comparison")));
  updateCounts();
};

const setSidebarCollapsed = (collapsed) => {
  shell.classList.toggle("sidebar-collapsed", collapsed);
  sidebarToggle.setAttribute("aria-expanded", String(!collapsed));
  localStorage.setItem("prompt-xray-sidebar-collapsed", collapsed ? "1" : "0");
};

const setActiveButton = (button) => {
  for (const node of document.querySelectorAll(".nav-item")) {
    node.classList.remove("active");
  }
  button.classList.add("active");
};

const setMode = (mode) => {
  const compare = mode === "compare";
  modeScan.classList.toggle("active", !compare);
  modeCompare.classList.toggle("active", compare);
  scanForm.classList.toggle("hidden", compare);
  compareForm.classList.toggle("hidden", !compare);
};

const setHeroStatus = (title, subtitle = "") => {
  heroStatus.innerHTML = `<span>Status</span><strong>${escapeHtml(title)}</strong><small>${escapeHtml(subtitle)}</small>`;
};

const renderReport = (report) => {
  const fileRoles = (report.file_roles_summary || [])
    .slice(0, 8)
    .map((item) => `<li><strong>${escapeHtml(item.role)}</strong> <span class="muted">${escapeHtml(item.count)}</span></li>`)
    .join("");
  const sourceRows = report.behavior_sources
    .slice(0, 8)
    .map(
      (source) => `
        <tr>
          <td><code>${escapeHtml(source.path)}</code></td>
          <td>${source.score.toFixed(2)}</td>
          <td>${escapeHtml(source.kinds.join(", "))}</td>
        </tr>`
    )
    .join("");

  const artifactItems = report.artifacts
    .slice(0, 12)
    .map(
      (artifact) => `
        <li>
          <strong>${escapeHtml(artifact.kind)}</strong> <code>${escapeHtml(artifact.path)}</code>
          <div class="muted">${escapeHtml(artifact.source_snippet || artifact.summary)}</div>
        </li>`
    )
    .join("");
  const scanLimits = report.scan_limits || {
    candidate_files_scanned: report.counts?.candidate_files || 0,
    code_files_scanned: 0,
    code_files_total: 0,
    max_code_files_per_language: 0,
    truncated_languages: [],
  };
  const evidenceSummary = report.evidence_summary || {
    path_evidence: 0,
    text_evidence: 0,
    code_evidence: 0,
    graph_evidence: 0,
    negative_evidence: 0,
  };
  const contradictions = report.contradictions || [];
  const promptRuntimeLinks = report.prompt_runtime_links || [];

  viewport.innerHTML = `
    <section class="panel">
      <div class="panel-header">
        <div>
          <p class="eyebrow">Repo Report</p>
          <h3>${escapeHtml(report.repo.name)}</h3>
          <p>${escapeHtml(report.summary.verdict)}</p>
        </div>
        <div class="badge-row">
          ${badge(report.summary.repo_family, "dark")}
          ${badge(report.summary.repo_archetype)}
          ${badge(report.summary.orchestration_model, "warn")}
          ${badge(report.summary.memory_model, "dark")}
          ${badge(`${report.overall_confidence?.level || "low"} confidence`, confidenceTone(report.overall_confidence?.level))}
        </div>
      </div>
      <div class="callout">
        <strong>${escapeHtml(report.summary.xray_call)}</strong>
        <span class="muted">Source: ${escapeHtml(report.repo.target)}</span>
      </div>
    </section>

    <section class="metrics-grid">
      <article class="metric-card">
        <div class="metric-label">Artifacts</div>
        <div class="metric-value">${escapeHtml(report.counts.artifacts)}</div>
        <div class="metric-caption">Prompt surfaces extracted</div>
      </article>
      <article class="metric-card">
        <div class="metric-label">Candidate files</div>
        <div class="metric-value">${escapeHtml(report.counts.candidate_files)}</div>
        <div class="metric-caption">Files scanned for signals</div>
      </article>
      <article class="metric-card">
        <div class="metric-label">Tooling surfaces</div>
        <div class="metric-value">${escapeHtml(report.tooling_surfaces.length)}</div>
        <div class="metric-caption">Detected ecosystem hooks</div>
      </article>
      <article class="metric-card">
        <div class="metric-label">Repo family</div>
        <div class="metric-value" style="font-size:18px;">${escapeHtml(report.summary.repo_family)}</div>
        <div class="metric-caption">Upstream structural classifier</div>
      </article>
      <article class="metric-card">
        <div class="metric-label">Commit</div>
        <div class="metric-value" style="font-size:18px;">${escapeHtml((report.repo.commit || "n/a").slice(0, 12))}</div>
        <div class="metric-caption">${escapeHtml(report.repo.source_type)} source</div>
      </article>
    </section>

    <section class="metrics-grid">
      <article class="metric-card">
        <div class="metric-label">Code evidence</div>
        <div class="metric-value">${escapeHtml(evidenceSummary.code_evidence)}</div>
        <div class="metric-caption">Runtime-facing code signals</div>
      </article>
      <article class="metric-card">
        <div class="metric-label">Graph evidence</div>
        <div class="metric-value">${escapeHtml(evidenceSummary.graph_evidence)}</div>
        <div class="metric-caption">Import and config links</div>
      </article>
      <article class="metric-card">
        <div class="metric-label">Scanned code files</div>
        <div class="metric-value">${escapeHtml(scanLimits.code_files_scanned)}</div>
        <div class="metric-caption">${escapeHtml(`${scanLimits.code_files_total} total discovered`)}</div>
      </article>
      <article class="metric-card">
        <div class="metric-label">Truncated langs</div>
        <div class="metric-value" style="font-size:18px;">${escapeHtml((scanLimits.truncated_languages || []).join(", ") || "none")}</div>
        <div class="metric-caption">Scan cap: ${escapeHtml(scanLimits.max_code_files_per_language)}</div>
      </article>
    </section>

    <section class="two-col">
      <article class="table-panel">
        <p class="eyebrow">Behavior Sources</p>
        <h3>Read these files first</h3>
        <table>
          <thead>
            <tr>
              <th>Path</th>
              <th>Score</th>
              <th>Kinds</th>
            </tr>
          </thead>
          <tbody>${sourceRows || '<tr><td colspan="3">No dominant behavior sources detected</td></tr>'}</tbody>
        </table>
      </article>

      <article class="list-panel">
        <p class="eyebrow">Missing Pieces</p>
        <h3>What the scan still calls out</h3>
        <ul>${formatList(report.missing_runtime_pieces, "No missing pieces called out")}</ul>

        <p class="eyebrow" style="margin-top:22px;">Tooling</p>
        <div class="badge-row" style="margin-top:10px;">
          ${
            report.tooling_surfaces.length
              ? report.tooling_surfaces.map((item) => badge(item, "dark")).join("")
              : badge("None detected", "dark")
          }
        </div>
      </article>
    </section>

    <section class="two-col">
      <article class="list-panel">
        <p class="eyebrow">Evidence Ladder</p>
        <h3>Why this call was made</h3>
        <strong>Runtime evidence</strong>
        <ul>${formatEvidence(report.runtime_evidence, "No runtime evidence detected")}</ul>
        <strong>Memory evidence</strong>
        <ul>${formatEvidence(report.memory_evidence, "No memory evidence detected")}</ul>
        <strong>Orchestration evidence</strong>
        <ul>${formatEvidence(report.orchestration_evidence, "No orchestration evidence detected")}</ul>
        <strong>Prompt/runtime linkage</strong>
        <ul>${
          promptRuntimeLinks.length
            ? promptRuntimeLinks
                .slice(0, 8)
                .map(
                  (link) => `
                    <li>
                      <strong>${escapeHtml(link.kind)}</strong> <code>${escapeHtml(link.source_path)}</code>
                      <div class="muted">${escapeHtml(link.target_path)}${link.reasons?.length ? ` | ${escapeHtml(link.reasons.join(", "))}` : ""}</div>
                    </li>`
                )
                .join("")
            : "<li>No runtime-to-prompt/config links detected</li>"
        }</ul>
      </article>

      <article class="list-panel">
        <p class="eyebrow">File Roles</p>
        <h3>What kind of repo this structurally is</h3>
        <ul>${fileRoles || "<li>No roles detected</li>"}</ul>
        <p class="eyebrow" style="margin-top:22px;">Evidence counts</p>
        <ul>
          <li>Path evidence: ${escapeHtml(evidenceSummary.path_evidence)}</li>
          <li>Text evidence: ${escapeHtml(evidenceSummary.text_evidence)}</li>
          <li>Code evidence: ${escapeHtml(evidenceSummary.code_evidence)}</li>
          <li>Graph evidence: ${escapeHtml(evidenceSummary.graph_evidence)}</li>
          <li>Negative evidence: ${escapeHtml(evidenceSummary.negative_evidence)}</li>
        </ul>
      </article>
    </section>

    <section class="two-col">
      <article class="list-panel">
        <p class="eyebrow">Confidence</p>
        <h3>How hard the scanner believes this call</h3>
        <strong>Repo family</strong>
        <ul>${formatConfidence(report.repo_family_confidence)}</ul>
        <strong>Repo archetype</strong>
        <ul>${formatConfidence(report.repo_archetype_confidence)}</ul>
        <strong>Orchestration</strong>
        <ul>${formatConfidence(report.orchestration_confidence)}</ul>
        <strong>Memory</strong>
        <ul>${formatConfidence(report.memory_confidence)}</ul>
        <strong>Overall</strong>
        <ul>${formatConfidence(report.overall_confidence)}</ul>
      </article>

      <article class="list-panel">
        <p class="eyebrow">Contradictions</p>
        <h3>Claim / implementation mismatches</h3>
        <ul>${formatList(contradictions, "No contradictions detected")}</ul>
      </article>
    </section>

    <section class="two-col">
      <article class="list-panel">
        <p class="eyebrow">Prompt Surface Highlights</p>
        <h3>First 12 extracted artifacts</h3>
        <ol>${artifactItems || "<li>No artifacts extracted</li>"}</ol>
      </article>

      <article class="list-panel">
        <p class="eyebrow">Real vs Packaging</p>
        <h3>How Prompt-xray splits the repo</h3>
        <strong>Real implementation</strong>
        <ul>${formatList(report.real_vs_packaging.real_implementation)}</ul>
        <strong>Prompt/config structure</strong>
        <ul>${formatList(report.real_vs_packaging.prompt_config_structure)}</ul>
        <strong>Presentation/marketing layer</strong>
        <ul>${formatList(report.real_vs_packaging.presentation_marketing_layer)}</ul>
      </article>
    </section>
  `;
};

const renderComparison = (comparison) => {
  viewport.innerHTML = `
    <section class="panel">
      <p class="eyebrow">Comparison</p>
      <h3>${escapeHtml(comparison.left.name)} vs ${escapeHtml(comparison.right.name)}</h3>
      <p class="muted">This is the fastest way to explain why two AI repos that look similar from the outside are structurally different.</p>
    </section>

    <section class="comparison-headline">
      <article class="comparison-card">
        <div class="badge-row">
          ${badge(comparison.left.repo_family, "dark")}
          ${badge(comparison.left.archetype)}
          ${badge(comparison.left.orchestration, "warn")}
          ${badge(comparison.left.memory, "dark")}
          ${badge(`${comparison.left.confidence?.overall?.level || "low"} confidence`, confidenceTone(comparison.left.confidence?.overall?.level))}
        </div>
        <h4>${escapeHtml(comparison.left.name)}</h4>
        <p>${escapeHtml(comparison.left.xray_call)}</p>
      </article>
      <article class="comparison-card">
        <div class="badge-row">
          ${badge(comparison.right.repo_family, "dark")}
          ${badge(comparison.right.archetype)}
          ${badge(comparison.right.orchestration, "warn")}
          ${badge(comparison.right.memory, "dark")}
          ${badge(`${comparison.right.confidence?.overall?.level || "low"} confidence`, confidenceTone(comparison.right.confidence?.overall?.level))}
        </div>
        <h4>${escapeHtml(comparison.right.name)}</h4>
        <p>${escapeHtml(comparison.right.xray_call)}</p>
      </article>
    </section>

    <section class="compare-grid">
      <article class="metric-card">
        <div class="metric-label">Family / archetype gap</div>
        <div class="metric-value" style="font-size:20px;">${comparison.left.repo_family} / ${comparison.left.archetype}</div>
        <div class="metric-caption">${comparison.right.repo_family} / ${comparison.right.archetype}</div>
      </article>
      <article class="metric-card">
        <div class="metric-label">Artifact gap</div>
        <div class="metric-value">${escapeHtml(Math.abs(comparison.differences.artifact_gap))}</div>
        <div class="metric-caption">Difference in extracted prompt surfaces</div>
      </article>
      <article class="metric-card">
        <div class="metric-label">Runtime density gap</div>
        <div class="metric-value">${escapeHtml(Math.abs(comparison.differences.runtime_density_gap))}</div>
        <div class="metric-caption">Code + graph evidence delta</div>
      </article>
      <article class="metric-card">
        <div class="metric-label">Call basis</div>
        <div class="metric-value" style="font-size:18px;">${escapeHtml(comparison.left.call_basis)}</div>
        <div class="metric-caption">${escapeHtml(comparison.right.call_basis)}</div>
      </article>
    </section>

    <section class="two-col">
      <article class="list-panel">
        <p class="eyebrow">Top Sources</p>
        <h3>${escapeHtml(comparison.left.name)}</h3>
        <ul>${formatList(comparison.left.top_behavior_sources)}</ul>
      </article>
      <article class="list-panel">
        <p class="eyebrow">Top Sources</p>
        <h3>${escapeHtml(comparison.right.name)}</h3>
        <ul>${formatList(comparison.right.top_behavior_sources)}</ul>
      </article>
    </section>

    <section class="two-col">
      <article class="list-panel">
        <p class="eyebrow">Runtime Evidence</p>
        <h3>${escapeHtml(comparison.left.name)}</h3>
        <ul>${formatEvidence(comparison.left.runtime_evidence, "No runtime evidence detected")}</ul>
      </article>
      <article class="list-panel">
        <p class="eyebrow">Runtime Evidence</p>
        <h3>${escapeHtml(comparison.right.name)}</h3>
        <ul>${formatEvidence(comparison.right.runtime_evidence, "No runtime evidence detected")}</ul>
      </article>
    </section>

    <section class="two-col">
      <article class="list-panel">
        <p class="eyebrow">Prompt / Runtime Links</p>
        <h3>${escapeHtml(comparison.left.name)}</h3>
        <ul>${
          comparison.left.prompt_runtime_links?.length
            ? comparison.left.prompt_runtime_links
                .map(
                  (link) => `<li><strong>${escapeHtml(link.kind)}</strong> <code>${escapeHtml(link.source_path)}</code><div class="muted">${escapeHtml(link.target_path)}</div></li>`
                )
                .join("")
            : "<li>No links detected</li>"
        }</ul>
      </article>
      <article class="list-panel">
        <p class="eyebrow">Prompt / Runtime Links</p>
        <h3>${escapeHtml(comparison.right.name)}</h3>
        <ul>${
          comparison.right.prompt_runtime_links?.length
            ? comparison.right.prompt_runtime_links
                .map(
                  (link) => `<li><strong>${escapeHtml(link.kind)}</strong> <code>${escapeHtml(link.source_path)}</code><div class="muted">${escapeHtml(link.target_path)}</div></li>`
                )
                .join("")
            : "<li>No links detected</li>"
        }</ul>
      </article>
    </section>

    <section class="two-col">
      <article class="list-panel">
        <p class="eyebrow">Tooling Overlap</p>
        <h3>Shared and exclusive surfaces</h3>
        <strong>Shared</strong>
        <ul>${formatList(comparison.differences.shared_tooling)}</ul>
        <strong>${escapeHtml(comparison.left.name)} only</strong>
        <ul>${formatList(comparison.differences.left_only_tooling)}</ul>
        <strong>${escapeHtml(comparison.right.name)} only</strong>
        <ul>${formatList(comparison.differences.right_only_tooling)}</ul>
      </article>
      <article class="list-panel">
        <p class="eyebrow">Strongly Supported</p>
        <h3>What the comparison says</h3>
        <ul>
          <li>Same family: ${escapeHtml(String(comparison.differences.same_family))}</li>
          <li>Same archetype: ${escapeHtml(String(comparison.differences.same_archetype))}</li>
          <li>Same orchestration model: ${escapeHtml(String(comparison.differences.same_orchestration))}</li>
          <li>Same memory model: ${escapeHtml(String(comparison.differences.same_memory))}</li>
          <li>Confidence gap: ${escapeHtml(String(comparison.differences.confidence_gap))}</li>
          <li>Prompt density gap: ${escapeHtml(String(comparison.differences.prompt_density_gap))}</li>
        </ul>
      </article>
    </section>

    <section class="two-col">
      <article class="list-panel">
        <p class="eyebrow">Uncertainty</p>
        <h3>${escapeHtml(comparison.left.name)}</h3>
        <ul>${formatList(comparison.left.contradictions, "No contradictions detected")}</ul>
      </article>
      <article class="list-panel">
        <p class="eyebrow">Uncertainty</p>
        <h3>${escapeHtml(comparison.right.name)}</h3>
        <ul>${formatList(comparison.right.contradictions, "No contradictions detected")}</ul>
      </article>
    </section>
  `;
};

const addOrPromoteEntry = (collection, entry) => {
  const existingIndex = collection.findIndex((item) => item.id === entry.id);
  if (existingIndex >= 0) {
    collection.splice(existingIndex, 1);
  }
  collection.unshift(entry);
};

const renderRuntimeReport = (report, target) => {
  const entry = {
    id: `runtime-report:${target}`,
    label: report.repo.name,
    highlight: report.summary.xray_call,
    data: report,
  };
  addOrPromoteEntry(reportEntries, entry);
  renderNavLists();
  const firstButton = reportList.querySelector(".nav-item");
  if (firstButton) {
    firstButton.click();
  } else {
    renderReport(report);
  }
};

const renderRuntimeComparison = (comparison, left, right) => {
  const entry = {
    id: `runtime-compare:${left}::${right}`,
    label: `${comparison.left.name} vs ${comparison.right.name}`,
    highlight: `${comparison.left.xray_call} / ${comparison.right.xray_call}`,
    data: comparison,
  };
  addOrPromoteEntry(compareEntries, entry);
  renderNavLists();
  const firstButton = compareList.querySelector(".nav-item");
  if (firstButton) {
    firstButton.click();
  } else {
    renderComparison(comparison);
  }
};

const loadEntry = async (entry, type, button) => {
  setActiveButton(button);
  viewport.innerHTML = `<div class="empty-state"><p class="eyebrow">Loading</p><h3>${escapeHtml(entry.label)}</h3><p>Fetching ${escapeHtml(entry.path || "runtime result")}</p></div>`;
  try {
    const data = entry.data
      ? entry.data
      : await fetch(entry.path).then((response) => response.json());
    if (type === "report") {
      renderReport(data);
    } else {
      renderComparison(data);
    }
  } catch (error) {
    viewport.innerHTML = `<div class="empty-state"><p class="eyebrow">Error</p><h3>Could not load ${escapeHtml(entry.label)}</h3><p>${escapeHtml(error.message)}</p></div>`;
  }
};

const postJson = async (url, payload) => {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`;
    try {
      const details = await response.json();
      message = details.detail || message;
    } catch {
      // ignore parse error
    }
    throw new Error(message);
  }

  return response.json();
};

const init = async () => {
  const collapsed = localStorage.getItem("prompt-xray-sidebar-collapsed") === "1";
  setSidebarCollapsed(collapsed);

  sidebarToggle.addEventListener("click", () => {
    setSidebarCollapsed(!shell.classList.contains("sidebar-collapsed"));
  });

  modeScan.addEventListener("click", () => setMode("scan"));
  modeCompare.addEventListener("click", () => setMode("compare"));
  setMode("scan");

  scanForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(scanForm);
    const target = String(formData.get("target") || "").trim();
    if (!target) return;

    setHeroStatus("Running scan", target);
    viewport.innerHTML = `<div class="empty-state"><p class="eyebrow">Scanning</p><h3>${escapeHtml(target)}</h3><p>Prompt-xray is analyzing the repo.</p></div>`;
    try {
      const report = await postJson("/api/scan", {
        target,
        max_file_size_kb: Number(formData.get("max_file_size_kb") || 1024),
        max_code_files_per_language: Number(formData.get("max_code_files_per_language") || 400),
        include_snippets: formData.get("include_snippets") === "on",
      });
      setHeroStatus(report.summary.xray_call, report.summary.verdict);
      renderRuntimeReport(report, target);
    } catch (error) {
      setHeroStatus("Scan failed", error.message);
      viewport.innerHTML = `<div class="empty-state"><p class="eyebrow">Error</p><h3>Scan failed</h3><p>${escapeHtml(error.message)}</p></div>`;
    }
  });

  compareForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(compareForm);
    const left = String(formData.get("left") || "").trim();
    const right = String(formData.get("right") || "").trim();
    if (!left || !right) return;

    setHeroStatus("Running compare", `${left} vs ${right}`);
    viewport.innerHTML = `<div class="empty-state"><p class="eyebrow">Comparing</p><h3>${escapeHtml(left)} vs ${escapeHtml(right)}</h3><p>Prompt-xray is building a structural diff.</p></div>`;
    try {
      const comparison = await postJson("/api/compare", {
        left,
        right,
        max_file_size_kb: Number(formData.get("max_file_size_kb") || 1024),
        max_code_files_per_language: Number(formData.get("max_code_files_per_language") || 400),
        include_snippets: formData.get("include_snippets") === "on",
      });
      setHeroStatus(
        `${comparison.left.xray_call} / ${comparison.right.xray_call}`,
        `${comparison.left.name} vs ${comparison.right.name}`
      );
      renderRuntimeComparison(comparison, left, right);
    } catch (error) {
      setHeroStatus("Compare failed", error.message);
      viewport.innerHTML = `<div class="empty-state"><p class="eyebrow">Error</p><h3>Compare failed</h3><p>${escapeHtml(error.message)}</p></div>`;
    }
  });

  const manifest = await fetch("/api/manifest").then((response) => response.json());
  reportEntries = manifest.reports.slice();
  compareEntries = manifest.comparisons.slice();
  renderNavLists();

  const firstCompare = compareList.querySelector(".nav-item");
  const firstReport = reportList.querySelector(".nav-item");
  if (firstCompare) {
    firstCompare.click();
  } else if (firstReport) {
    firstReport.click();
  }
};

init().catch((error) => {
  viewport.innerHTML = `<div class="empty-state"><p class="eyebrow">Boot Error</p><h3>UI failed to load</h3><p>${escapeHtml(error.message)}</p></div>`;
});
