import {
  getCosts,
  getIssueDetails,
  getScoringFailures,
  getStats,
  getTagWeights,
  triggerJob,
} from "../api";
import type { CostEntry, StatsResponse } from "../types";
import { el, formatDate } from "../utils";
import { showToast } from "../components/toast";

export function StatsPage(): HTMLElement {
  const page = el("div", { class: "page page-stats" });
  page.appendChild(el("h1", {}, "Stats"));

  const content = el("div", { class: "stats-content" });
  page.appendChild(content);

  function loadStats(): void {
    Promise.all([
      getStats(),
      getCosts(),
      getTagWeights(),
      getIssueDetails(),
      getScoringFailures(),
    ]).then(([stats, costs, tags, issueDetails, scoringFailures]) => {
        content.innerHTML = "";
        if (
          issueDetails.fetch_errors > 0 ||
          issueDetails.scoring_failures > 0
        ) {
          content.appendChild(
            renderIssuesBanner(issueDetails, scoringFailures, loadStats)
          );
        }
        content.appendChild(renderOverview(stats));
        content.appendChild(renderScoreDistribution(stats.score_distribution));
        content.appendChild(renderSchedulerJobs(stats, loadStats));
        content.appendChild(renderSourceHealth(stats));
        content.appendChild(renderCosts(costs));
        content.appendChild(renderTagCloud(tags));
      }
    );
  }
  loadStats();

  return page;
}

type ScoringFailureEntry = {
  id: number;
  title: string;
  url: string;
  source_name: string;
  score_attempts: number;
  scored_at: string | null;
  error: string | null;
};

const ICON_WARN = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><path d="M12 9v4"/><path d="M12 17h.01"/></svg>`;
const ICON_PLAY = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="6 3 20 12 6 21 6 3"/></svg>`;
const ICON_RETRY = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/><path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16"/><path d="M21 21v-5h-5"/></svg>`;

function renderIssuesBanner(
  details: {
    fetch_errors: number;
    scoring_failures: number;
    scoring_retryable: number;
    unscored: number;
  },
  failures: ScoringFailureEntry[],
  reloadPage: () => void
): HTMLElement {
  const section = el("div", { class: "issues-section" });

  // Summary bar
  const banner = el("div", { class: "issues-banner" });
  const parts: string[] = [];
  if (details.fetch_errors > 0) {
    parts.push(
      `${details.fetch_errors} fetch error${details.fetch_errors > 1 ? "s" : ""} (last 24h)`
    );
  }
  if (details.scoring_failures > 0) {
    parts.push(
      `${details.scoring_failures} scoring failure${details.scoring_failures > 1 ? "s" : ""}`
    );
  }
  if (details.unscored > 0) {
    parts.push(`${details.unscored} awaiting scoring`);
  }

  const textSpan = el("span", {}, parts.join(" \u00B7 "));
  banner.innerHTML = ICON_WARN;
  banner.appendChild(textSpan);

  // Force retry button (works regardless of attempt count)
  if (details.scoring_failures > 0) {
    const retryBtn = el(
      "button",
      { class: "btn btn-small btn-retry btn-icon-text", title: "Reset all failed articles for re-scoring (ignores retry limit)" },
    );
    retryBtn.innerHTML = `${ICON_RETRY}<span>Force Retry All</span>`;
    retryBtn.addEventListener("click", async () => {
      retryBtn.setAttribute("disabled", "true");
      retryBtn.querySelector("span")!.textContent = "Retrying\u2026";
      try {
        const res = await triggerJob("force-retry-scoring");
        showToast(res.message, "success");
        setTimeout(reloadPage, 2000);
      } catch {
        showToast("Failed to trigger retry", "error");
      } finally {
        retryBtn.removeAttribute("disabled");
        retryBtn.querySelector("span")!.textContent = "Force Retry All";
      }
    });
    banner.appendChild(retryBtn);
  }

  section.appendChild(banner);

  // Detailed failure table
  if (failures.length > 0) {
    const table = el("table", { class: "stats-table issues-table" });
    table.innerHTML = `<thead><tr>
      <th>Article</th><th>Source</th><th>Attempts</th><th>Error</th>
    </tr></thead>`;
    const tbody = el("tbody", {});
    for (const f of failures) {
      const tr = el("tr", {});
      tr.innerHTML = `
        <td><a href="${f.url}" target="_blank" rel="noopener" class="issues-article-link">${f.title}</a></td>
        <td class="text-muted">${f.source_name}</td>
        <td>${f.score_attempts}/3</td>
        <td class="text-error">${f.error ?? "\u2014"}</td>
      `;
      tbody.appendChild(tr);
    }
    table.appendChild(tbody);
    section.appendChild(table);
  }

  return section;
}

function renderOverview(stats: StatsResponse): HTMLElement {
  const section = el("div", { class: "stats-section" });
  const grid = el("div", { class: "stats-grid" });
  const cards: [string, string][] = [
    ["Inbox", String(stats.inbox_count)],
    ["Total Articles", String(stats.total_articles)],
    ["Scored", String(stats.scored_articles)],
    [
      "Avg Score",
      stats.average_score !== null ? stats.average_score.toFixed(1) : "N/A",
    ],
    ["Feedback", String(stats.total_feedback)],
    [
      "Up / Down",
      `${stats.positive_feedback} / ${stats.negative_feedback}`,
    ],
  ];

  for (const [label, value] of cards) {
    const card = el("div", { class: "stat-card" });
    card.appendChild(el("div", { class: "stat-value" }, value));
    card.appendChild(el("div", { class: "stat-label" }, label));
    grid.appendChild(card);
  }
  section.appendChild(grid);
  return section;
}

function renderScoreDistribution(distribution: number[]): HTMLElement {
  const section = el("div", { class: "stats-section" });
  section.appendChild(el("h2", {}, "Score Distribution"));

  if (!distribution || distribution.length === 0) {
    section.appendChild(el("p", { class: "text-muted" }, "No scored articles yet."));
    return section;
  }

  const maxVal = Math.max(...distribution, 1);
  const chartHeight = 120;
  const barWidth = 32;
  const gap = 4;
  const svgWidth = distribution.length * (barWidth + gap);

  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", `0 0 ${svgWidth} ${chartHeight + 24}`);
  svg.setAttribute("class", "score-chart");
  svg.style.width = "100%";
  svg.style.maxWidth = `${svgWidth}px`;

  for (let i = 0; i < distribution.length; i++) {
    const count = distribution[i];
    const barHeight = maxVal > 0 ? (count / maxVal) * chartHeight : 0;
    const x = i * (barWidth + gap);
    const y = chartHeight - barHeight;

    const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    rect.setAttribute("x", String(x));
    rect.setAttribute("y", String(y));
    rect.setAttribute("width", String(barWidth));
    rect.setAttribute("height", String(Math.max(barHeight, 1)));
    rect.setAttribute("rx", "4");
    const hue =
      i >= 7
        ? "var(--color-success)"
        : i >= 4
          ? "var(--color-score-mid)"
          : "var(--color-score-low)";
    rect.setAttribute("fill", hue);
    rect.setAttribute("opacity", "0.8");
    svg.appendChild(rect);

    if (count > 0) {
      const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
      text.setAttribute("x", String(x + barWidth / 2));
      text.setAttribute("y", String(y - 4));
      text.setAttribute("text-anchor", "middle");
      text.setAttribute("class", "chart-label");
      text.textContent = String(count);
      svg.appendChild(text);
    }

    const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
    label.setAttribute("x", String(x + barWidth / 2));
    label.setAttribute("y", String(chartHeight + 16));
    label.setAttribute("text-anchor", "middle");
    label.setAttribute("class", "chart-axis-label");
    label.textContent = String(i);
    svg.appendChild(label);
  }

  section.appendChild(svg);
  return section;
}

function formatJobDetails(details: string): string {
  try {
    const obj = JSON.parse(details) as Record<string, unknown>;
    return Object.entries(obj)
      .map(([k, v]) => `<span class="detail-pill"><span class="detail-key">${k}</span>${v}</span>`)
      .join(" ");
  } catch {
    return `<span class="text-muted">${details}</span>`;
  }
}

const JOB_DISPLAY: [string, "fetch" | "score" | "cleanup", string][] = [
  ["fetch_all", "fetch", "Fetch new articles from all sources"],
  ["score", "score", "Score all unscored articles with AI"],
  ["cleanup", "cleanup", "Remove old articles and prune data"],
];

function renderSchedulerJobs(
  stats: StatsResponse,
  reloadPage: () => void
): HTMLElement {
  const section = el("div", { class: "stats-section" });
  section.appendChild(el("h2", {}, "Background Jobs"));

  const table = el("table", { class: "stats-table" });
  table.innerHTML = `<thead><tr>
    <th>Job</th><th>Last Run</th><th>Next Run</th><th>Status</th><th>Details</th><th></th>
  </tr></thead>`;
  const tbody = el("tbody", {});

  // Build lookup from scheduler_jobs
  const jobMap = new Map(
    (stats.scheduler_jobs ?? []).map((j) => [j.job_name, j])
  );

  for (const [dbName, triggerName, tooltip] of JOB_DISPLAY) {
    const job = jobMap.get(dbName);
    const tr = el("tr", {});

    const statusClass = !job
      ? ""
      : job.last_status === "error"
        ? "status-error"
        : job.last_status === "success"
          ? "status-ok"
          : "status-running";

    const statusDot = job ? `<span class="status-dot ${statusClass}"></span>` : "";
    const statusText = job?.last_status ?? "\u2014";

    // Next run
    const nextRun = job?.next_run_at ? formatDate(job.next_run_at) : "\u2014";

    // Render details as key-value pills if JSON, otherwise plain text
    let detailsHtml = "";
    if (job?.last_error) {
      detailsHtml = `<span class="text-error">${job.last_error}</span>`;
    } else if (job?.last_details) {
      detailsHtml = formatJobDetails(job.last_details);
    }

    tr.innerHTML = `
      <td class="font-medium">${dbName}</td>
      <td>${job?.last_run_at ? formatDate(job.last_run_at) : "Never"}</td>
      <td>${nextRun}</td>
      <td class="status-cell">${statusDot}${statusText}</td>
      <td>${detailsHtml}</td>
    `;

    // Run button in the row
    const actionTd = document.createElement("td");
    const btn = el(
      "button",
      { class: "btn btn-small btn-trigger btn-icon-text", title: tooltip },
    );
    btn.innerHTML = `${ICON_PLAY}<span>Run</span>`;
    btn.addEventListener("click", async () => {
      btn.setAttribute("disabled", "true");
      btn.querySelector("span")!.textContent = "Running\u2026";
      try {
        const res = await triggerJob(triggerName);
        showToast(res.message, "success");
        setTimeout(reloadPage, 3000);
      } catch {
        showToast(`Failed to trigger ${dbName}`, "error");
      } finally {
        btn.removeAttribute("disabled");
        btn.querySelector("span")!.textContent = "Run";
      }
    });
    actionTd.appendChild(btn);
    tr.appendChild(actionTd);

    tbody.appendChild(tr);
  }

  table.appendChild(tbody);
  section.appendChild(table);
  return section;
}

function renderSourceHealth(stats: StatsResponse): HTMLElement {
  const section = el("div", { class: "stats-section" });
  section.appendChild(el("h2", {}, "Source Health"));

  if (stats.sources.length === 0) {
    section.appendChild(
      el("p", { class: "text-muted" }, "No sources configured.")
    );
    return section;
  }

  const table = el("table", { class: "stats-table" });
  table.innerHTML = `<thead><tr>
    <th>Source</th><th>Category</th><th>Articles</th>
    <th>Interval</th><th>Last Fetch</th>
  </tr></thead>`;
  const tbody = el("tbody", {});

  for (const s of stats.sources) {
    const tr = el("tr", {});
    const name = String(s.name ?? "");
    const category = String(s.category ?? "");
    const articleCount = String(s.article_count ?? 0);
    const interval = String(s.fetch_interval_minutes ?? 30);
    const lastFetch = s.last_fetched_at
      ? formatDate(String(s.last_fetched_at))
      : "Never";
    const enabled = Boolean(s.enabled);
    const statusClass = enabled ? "status-ok" : "status-error";
    tr.innerHTML = `
      <td><span class="status-dot ${statusClass}"></span>${name}</td>
      <td class="text-muted">${category}</td>
      <td>${articleCount}</td>
      <td>${interval}m</td>
      <td>${lastFetch}</td>
    `;
    tbody.appendChild(tr);
  }
  table.appendChild(tbody);
  section.appendChild(table);
  return section;
}

function renderCosts(costs: CostEntry[]): HTMLElement {
  const section = el("div", { class: "stats-section" });
  section.appendChild(el("h2", {}, "LLM Costs"));

  if (costs.length === 0) {
    section.appendChild(
      el("p", { class: "text-muted" }, "No scoring data yet.")
    );
    return section;
  }

  const table = el("table", { class: "stats-table" });
  table.innerHTML = `<thead><tr>
    <th>Month</th><th>Model</th><th>Batches</th>
    <th>Tokens In</th><th>Tokens Out</th><th>Cost (USD)</th>
  </tr></thead>`;
  const tbody = el("tbody", {});

  for (const c of costs) {
    const tr = el("tr", {});
    tr.innerHTML = `
      <td>${c.month}</td>
      <td class="font-mono">${c.model}</td>
      <td>${c.batches}</td>
      <td>${c.tokens_in.toLocaleString()}</td>
      <td>${c.tokens_out.toLocaleString()}</td>
      <td class="font-mono">$${c.cost_usd.toFixed(4)}</td>
    `;
    tbody.appendChild(tr);
  }
  table.appendChild(tbody);
  section.appendChild(table);
  return section;
}

function renderTagCloud(
  tags: { name: string; weight: number }[]
): HTMLElement {
  const section = el("div", { class: "stats-section" });
  section.appendChild(el("h2", {}, "Top Tags"));

  const top = tags.slice(0, 20);
  if (top.length === 0) {
    section.appendChild(el("p", { class: "text-muted" }, "No tags yet."));
    return section;
  }

  const maxWeight = Math.max(...top.map((t) => Math.abs(t.weight)), 0.1);
  const cloud = el("div", { class: "tag-cloud" });

  for (const tag of top) {
    const size = 0.8 + (Math.abs(tag.weight) / maxWeight) * 0.2;
    const chip = el("span", { class: "tag-cloud-item" }, tag.name);
    chip.style.fontSize = `${size}rem`;
    if (tag.weight > 0) chip.classList.add("positive");
    else if (tag.weight < 0) chip.classList.add("negative");
    chip.title = `Weight: ${tag.weight >= 0 ? "+" : ""}${tag.weight.toFixed(2)}`;
    cloud.appendChild(chip);
  }

  section.appendChild(cloud);
  return section;
}
