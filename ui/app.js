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

  viewport.innerHTML = `
    <section class="panel">
      <div class="panel-header">
        <div>
          <p class="eyebrow">Repo Report</p>
          <h3>${escapeHtml(report.repo.name)}</h3>
          <p>${escapeHtml(report.summary.verdict)}</p>
        </div>
        <div class="badge-row">
          ${badge(report.summary.repo_archetype)}
          ${badge(report.summary.orchestration_model, "warn")}
          ${badge(report.summary.memory_model, "dark")}
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
        <div class="metric-label">Commit</div>
        <div class="metric-value" style="font-size:18px;">${escapeHtml((report.repo.commit || "n/a").slice(0, 12))}</div>
        <div class="metric-caption">${escapeHtml(report.repo.source_type)} source</div>
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
          ${badge(comparison.left.archetype)}
          ${badge(comparison.left.orchestration, "warn")}
          ${badge(comparison.left.memory, "dark")}
        </div>
        <h4>${escapeHtml(comparison.left.name)}</h4>
        <p>${escapeHtml(comparison.left.xray_call)}</p>
      </article>
      <article class="comparison-card">
        <div class="badge-row">
          ${badge(comparison.right.archetype)}
          ${badge(comparison.right.orchestration, "warn")}
          ${badge(comparison.right.memory, "dark")}
        </div>
        <h4>${escapeHtml(comparison.right.name)}</h4>
        <p>${escapeHtml(comparison.right.xray_call)}</p>
      </article>
    </section>

    <section class="compare-grid">
      <article class="metric-card">
        <div class="metric-label">Archetype gap</div>
        <div class="metric-value" style="font-size:24px;">${comparison.left.archetype} vs ${comparison.right.archetype}</div>
      </article>
      <article class="metric-card">
        <div class="metric-label">Artifact gap</div>
        <div class="metric-value">${escapeHtml(Math.abs(comparison.differences.artifact_gap))}</div>
        <div class="metric-caption">Difference in extracted prompt surfaces</div>
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
        <p class="eyebrow">Summary</p>
        <h3>What the comparison says</h3>
        <ul>
          <li>Same archetype: ${escapeHtml(String(comparison.differences.same_archetype))}</li>
          <li>Same orchestration model: ${escapeHtml(String(comparison.differences.same_orchestration))}</li>
          <li>Same memory model: ${escapeHtml(String(comparison.differences.same_memory))}</li>
        </ul>
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
