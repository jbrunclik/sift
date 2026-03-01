import {
  createSource,
  deleteSource,
  getSources,
  triggerFetch,
  updateSource,
} from "../api";
import type { Source } from "../types";
import { el, formatDate } from "../utils";
import { showModal } from "./modal";
import { showToast } from "./toast";

function slugify(name: string): string {
  return name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

const ICON = {
  plus: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 5v14"/><path d="M5 12h14"/></svg>`,
  refresh: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/><path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16"/><path d="M21 21v-5h-5"/></svg>`,
  trash: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/></svg>`,
  edit: `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z"/></svg>`,
  chevron: `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 18l6-6-6-6"/></svg>`,
  brain: `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2a4 4 0 0 0-4 4v1a3 3 0 0 0-3 3 3 3 0 0 0 1 2.2A4 4 0 0 0 4 16a4 4 0 0 0 4 4h8a4 4 0 0 0 4-4 4 4 0 0 0-2-3.8A3 3 0 0 0 19 10a3 3 0 0 0-3-3V6a4 4 0 0 0-4-4Z"/><path d="M12 2v20"/></svg>`,
};

function getFaviconUrl(source: Source): string | null {
  try {
    const config = JSON.parse(source.config_json);
    const url = config.feed_url || config.page_url;
    if (!url) return null;
    const domain = new URL(url).hostname;
    return `https://www.google.com/s2/favicons?domain=${domain}&sz=32`;
  } catch {
    return null;
  }
}

function getSourceTypeBadge(source: Source): string {
  return source.source_type === "webpage" ? "WEB" : "RSS";
}

interface ExtractionRulesInfo {
  item_selector: string;
  title: { selector: string; attribute?: string | null };
  url: { selector: string; attribute?: string | null };
  date?: { selector: string; attribute?: string | null } | null;
  description?: { selector: string; attribute?: string | null } | null;
  date_format?: string | null;
}

function getExtractionRules(source: Source): {
  rules: ExtractionRulesInfo;
  learnedAt: string;
} | null {
  try {
    const config = JSON.parse(source.config_json);
    if (!config.extraction_rules) return null;
    return {
      rules: config.extraction_rules as ExtractionRulesInfo,
      learnedAt: config._rules_learned_at || "",
    };
  } catch {
    return null;
  }
}

function formatNextRun(source: Source): string {
  if (!source.last_fetched_at) return "pending";
  const dateStr = source.last_fetched_at;
  const normalized =
    dateStr.endsWith("Z") || dateStr.includes("+") ? dateStr : dateStr + "Z";
  const last = new Date(normalized).getTime();
  const next = last + source.fetch_interval_minutes * 60 * 1000;
  const now = Date.now();
  const diff = next - now;
  if (diff <= 0) return "due now";
  const mins = Math.round(diff / 60000);
  if (mins < 60) return `in ${mins}m`;
  const hours = Math.floor(mins / 60);
  const rem = mins % 60;
  return rem > 0 ? `in ${hours}h ${rem}m` : `in ${hours}h`;
}

function formatRuleField(
  rule: { selector: string; attribute?: string | null } | null | undefined
): string {
  if (!rule) return "-";
  if (rule.attribute) return `${rule.selector} [${rule.attribute}]`;
  return `${rule.selector}`;
}

export function SourceManager(): HTMLElement {
  const container = el("div", { class: "source-manager" });
  let sources: Source[] = [];
  let selectedType = "rss";

  async function load(): Promise<void> {
    sources = await getSources();
    render();
  }

  function getExistingCategories(): string[] {
    const cats = new Set<string>();
    for (const s of sources) {
      if (s.category) cats.add(s.category);
    }
    return Array.from(cats).sort();
  }

  function render(): void {
    container.innerHTML = "";

    // Add source form — card layout
    const form = el("form", { class: "source-form" });

    // Row 1: segmented control (standalone for prominence)
    const topRow = el("div", { class: "source-form-top" });
    const segmented = el("div", { class: "segmented-control" });
    const btnRss = el(
      "button",
      {
        type: "button",
        class:
          selectedType === "rss"
            ? "segmented-btn segmented-active"
            : "segmented-btn",
      },
      "RSS Feed"
    );
    const btnWeb = el(
      "button",
      {
        type: "button",
        class:
          selectedType === "webpage"
            ? "segmented-btn segmented-active"
            : "segmented-btn",
      },
      "Web Page"
    );
    segmented.appendChild(btnRss);
    segmented.appendChild(btnWeb);
    topRow.appendChild(segmented);
    form.appendChild(topRow);

    // Row 2: fields
    const row = el("div", { class: "source-form-row" });

    const nameInput = el("input", {
      type: "text",
      placeholder: "Source name",
      class: "input input-name",
    }) as HTMLInputElement;
    const urlInput = el("input", {
      type: "url",
      placeholder:
        selectedType === "webpage"
          ? "https://example.com/news"
          : "https://example.com/feed.xml",
      class: "input input-url",
    }) as HTMLInputElement;

    const categoryInput = el("input", {
      type: "text",
      placeholder: "Category",
      class: "input input-category",
      list: "category-suggestions",
    }) as HTMLInputElement;

    const datalist = document.createElement("datalist");
    datalist.id = "category-suggestions";
    for (const cat of getExistingCategories()) {
      const opt = document.createElement("option");
      opt.value = cat;
      datalist.appendChild(opt);
    }

    const addBtn = el("button", {
      type: "submit",
      class: "btn btn-primary btn-icon-text",
      title: "Add source",
    });
    addBtn.innerHTML = `${ICON.plus}<span>Add</span>`;

    // Segmented control behavior
    btnRss.addEventListener("click", () => {
      selectedType = "rss";
      btnRss.classList.add("segmented-active");
      btnWeb.classList.remove("segmented-active");
      urlInput.placeholder = "https://example.com/feed.xml";
    });
    btnWeb.addEventListener("click", () => {
      selectedType = "webpage";
      btnWeb.classList.add("segmented-active");
      btnRss.classList.remove("segmented-active");
      urlInput.placeholder = "https://example.com/news";
    });

    row.appendChild(nameInput);
    row.appendChild(urlInput);
    row.appendChild(categoryInput);
    row.appendChild(datalist);
    row.appendChild(addBtn);
    form.appendChild(row);

    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const name = nameInput.value.trim();
      const sourceUrl = urlInput.value.trim();
      if (!name || !sourceUrl) {
        showToast("Name and URL are required", "error");
        return;
      }
      const configJson =
        selectedType === "webpage"
          ? JSON.stringify({ page_url: sourceUrl })
          : JSON.stringify({ feed_url: sourceUrl });
      try {
        await createSource({
          name,
          slug: slugify(name),
          source_type: selectedType,
          config_json: configJson,
          category: categoryInput.value.trim(),
        });
        showToast("Source added", "success");
        nameInput.value = "";
        urlInput.value = "";
        categoryInput.value = "";
        load();
      } catch (err) {
        showToast(`Error: ${err}`, "error");
      }
    });

    container.appendChild(form);

    // Source list
    if (sources.length === 0) {
      container.appendChild(
        el(
          "div",
          { class: "empty-state" },
          "No sources yet. Add a source above."
        )
      );
      return;
    }

    const list = el("div", { class: "source-list" });
    for (const source of sources) {
      list.appendChild(renderSourceRow(source));
    }
    container.appendChild(list);
  }

  function openCategoryEditor(
    categoryRow: HTMLElement,
    source: Source
  ): void {
    if (categoryRow.querySelector("input")) return;

    categoryRow.innerHTML = "";
    const catInput = document.createElement("input");
    catInput.type = "text";
    catInput.className = "input input-inline";
    catInput.placeholder = "Category";
    catInput.value = source.category;
    const dl = document.getElementById("category-suggestions");
    if (dl) catInput.setAttribute("list", "category-suggestions");

    let saving = false;
    async function saveCategory(): Promise<void> {
      if (saving) return;
      saving = true;
      const newCat = catInput.value.trim();
      if (newCat !== source.category) {
        await updateSource(source.id, { category: newCat });
        showToast("Category updated", "success");
      }
      load();
    }

    catInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        saveCategory();
      }
      if (e.key === "Escape") {
        load();
      }
    });
    catInput.addEventListener("blur", () => saveCategory());

    categoryRow.appendChild(catInput);
    requestAnimationFrame(() => catInput.focus());
  }

  function renderSourceRow(source: Source): HTMLElement {
    const wrapper = el("div", { class: "source-card" });
    const row = el("div", { class: "source-row" });

    // Favicon
    const faviconUrl = getFaviconUrl(source);
    if (faviconUrl) {
      const favicon = el("img", {
        class: "source-favicon",
        width: "16",
        height: "16",
      }) as HTMLImageElement;
      favicon.src = faviconUrl;
      favicon.alt = "";
      favicon.onerror = () => favicon.remove();
      row.appendChild(favicon);
    }

    // Type badge
    const badge = el(
      "span",
      { class: `source-type-badge source-type-${source.source_type}` },
      getSourceTypeBadge(source)
    );
    row.appendChild(badge);

    // Left: name + category
    const info = el("div", { class: "source-info" });
    info.appendChild(el("span", { class: "source-name" }, source.name));

    const categoryRow = el("div", { class: "source-category-row" });
    const catLabel = el(
      "span",
      {
        class: source.category
          ? "source-category"
          : "source-category source-category-empty",
        title: "Click to edit category",
      },
      source.category || "Uncategorized"
    );
    const editIcon = el("span", { class: "source-category-edit" });
    editIcon.innerHTML = ICON.edit;
    catLabel.appendChild(editIcon);
    catLabel.addEventListener("click", () =>
      openCategoryEditor(categoryRow, source)
    );
    categoryRow.appendChild(catLabel);
    info.appendChild(categoryRow);
    row.appendChild(info);

    // Middle: fetch info
    const meta = el("div", { class: "source-meta" });
    meta.appendChild(
      el(
        "span",
        { class: "source-interval" },
        `Every ${source.fetch_interval_minutes}m`
      )
    );
    meta.appendChild(
      el(
        "span",
        { class: "source-last-fetch" },
        source.last_fetched_at
          ? `Last: ${formatDate(source.last_fetched_at)}`
          : "Never fetched"
      )
    );
    meta.appendChild(
      el(
        "span",
        { class: "source-next-run" },
        `Next: ${formatNextRun(source)}`
      )
    );
    row.appendChild(meta);

    // Right: actions
    const actions = el("div", { class: "source-actions" });

    const fetchBtn = el("button", {
      class: "btn-icon-action",
      title: `Fetch new articles from ${source.name}`,
    });
    fetchBtn.innerHTML = ICON.refresh;
    fetchBtn.addEventListener("click", async () => {
      fetchBtn.classList.add("spinning");
      fetchBtn.setAttribute("disabled", "true");
      try {
        const log = await triggerFetch(source.id);
        showToast(
          `${source.name}: ${log.items_new} new / ${log.items_found} found`,
          "success"
        );
        load();
      } catch (err) {
        showToast(`Fetch failed: ${err}`, "error");
        fetchBtn.classList.remove("spinning");
        fetchBtn.removeAttribute("disabled");
      }
    });

    const deleteBtn = el("button", {
      class: "btn-icon-action btn-icon-danger",
      title: `Remove ${source.name} and its articles`,
    });
    deleteBtn.innerHTML = ICON.trash;
    deleteBtn.addEventListener("click", async () => {
      const confirmed = await showModal({
        title: "Delete source",
        message: `Remove "${source.name}" and all its articles? This cannot be undone.`,
        confirmLabel: "Delete",
        danger: true,
      });
      if (confirmed) {
        await deleteSource(source.id);
        showToast("Source deleted", "info");
        load();
      }
    });

    actions.appendChild(fetchBtn);
    actions.appendChild(deleteBtn);
    row.appendChild(actions);
    wrapper.appendChild(row);

    // Extraction rules disclosure for web page sources
    if (source.source_type === "webpage") {
      const rulesInfo = getExtractionRules(source);
      const disclosure = el("div", { class: "source-rules-toggle" });
      const chevron = el("span", { class: "source-rules-chevron" });
      chevron.innerHTML = ICON.chevron;

      if (rulesInfo) {
        disclosure.appendChild(chevron);
        const rulesIcon = el("span", { class: "source-rules-icon" });
        rulesIcon.innerHTML = ICON.brain;
        disclosure.appendChild(rulesIcon);
        disclosure.appendChild(
          el("span", { class: "source-rules-label" }, "Extraction rules")
        );
        const learnedDate = rulesInfo.learnedAt
          ? formatDate(rulesInfo.learnedAt)
          : "";
        if (learnedDate) {
          disclosure.appendChild(
            el("span", { class: "source-rules-date" }, `Learned ${learnedDate}`)
          );
        }
      } else {
        disclosure.appendChild(chevron);
        const rulesIcon = el("span", { class: "source-rules-icon" });
        rulesIcon.innerHTML = ICON.brain;
        disclosure.appendChild(rulesIcon);
        disclosure.appendChild(
          el(
            "span",
            { class: "source-rules-label source-rules-pending" },
            "Rules not yet learned"
          )
        );
        disclosure.appendChild(
          el(
            "span",
            { class: "source-rules-hint" },
            "Will learn on first fetch"
          )
        );
      }

      // Rules detail panel (hidden by default)
      const panel = el("div", { class: "source-rules-panel" });

      if (rulesInfo) {
        const grid = el("div", { class: "rules-grid" });
        const addRow = (label: string, value: string) => {
          grid.appendChild(el("span", { class: "rules-key" }, label));
          grid.appendChild(el("code", { class: "rules-value" }, value));
        };
        addRow("Items", rulesInfo.rules.item_selector);
        addRow("Title", formatRuleField(rulesInfo.rules.title));
        addRow("URL", formatRuleField(rulesInfo.rules.url));
        if (rulesInfo.rules.date)
          addRow("Date", formatRuleField(rulesInfo.rules.date));
        if (rulesInfo.rules.date_format)
          addRow("Date format", rulesInfo.rules.date_format);
        if (rulesInfo.rules.description)
          addRow("Description", formatRuleField(rulesInfo.rules.description));
        panel.appendChild(grid);

        // Re-learn button
        const relearn = el(
          "button",
          {
            class: "btn btn-small source-rules-relearn",
            title: "Forget learned rules and re-learn on next fetch",
          },
          "Re-learn rules"
        );
        relearn.addEventListener("click", async () => {
          try {
            const config = JSON.parse(source.config_json);
            delete config.extraction_rules;
            delete config._rules_learned_at;
            await updateSource(source.id, {
              config_json: JSON.stringify(config),
            });
            showToast("Rules cleared — will re-learn on next fetch", "success");
            load();
          } catch {
            showToast("Failed to clear rules", "error");
          }
        });
        panel.appendChild(relearn);
      }

      // Toggle behavior
      disclosure.addEventListener("click", () => {
        const isOpen = wrapper.classList.toggle("source-rules-open");
        chevron.classList.toggle("rotated", isOpen);
      });

      wrapper.appendChild(disclosure);
      wrapper.appendChild(panel);
    }

    return wrapper;
  }

  load();
  return container;
}
