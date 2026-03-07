import {
  createSource,
  deleteSource,
  getAuthIssues,
  getPlatforms,
  getSources,
  testSourceAuth,
  triggerFetch,
  updateSource,
} from "../api";
import type { AuthIssueEntry, PlatformInfo, Source } from "../types";
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
  starOutline: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>`,
  starFilled: `<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>`,
  lock: `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>`,
  save: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/></svg>`,
};

const PLATFORM_ICONS: Record<string, string> = {
  hackernews: `<svg width="20" height="20" viewBox="0 0 256 256" fill="none"><rect width="256" height="256" rx="4" fill="#ff6600"/><path d="M128 148.3 92.4 72h-22l52 108v52h11.2v-52l52-108h-22z" fill="#fff"/></svg>`,
};

const PLATFORM_DOMAINS: Record<string, string> = {
  hackernews: "news.ycombinator.com",
};

function getFaviconUrl(source: Source): string | null {
  try {
    // Platform sources: use known domain
    const platformDomain = PLATFORM_DOMAINS[source.source_type];
    if (platformDomain) {
      return `https://www.google.com/s2/favicons?domain=${platformDomain}&sz=32`;
    }
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
  if (source.source_type === "hackernews") return "HN";
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
  let platforms: PlatformInfo[] = [];
  let authIssueMap = new Map<number, AuthIssueEntry>();
  let selectedType = "rss";

  async function load(): Promise<void> {
    const [s, ai, p] = await Promise.all([getSources(), getAuthIssues(), getPlatforms()]);
    sources = s;
    platforms = p;
    authIssueMap = new Map(ai.map((e) => [e.source_id, e]));
    render();
  }

  function getExistingCategories(): string[] {
    const cats = new Set<string>();
    for (const s of sources) {
      if (s.category) cats.add(s.category);
    }
    return Array.from(cats).sort();
  }

  function renderPlatformCard(platform: PlatformInfo): HTMLElement {
    const card = el("div", {
      class: `platform-card${platform.source ? " enabled" : ""}`,
    });

    // Header — always visible: chevron, icon, name, on/off toggle
    const header = el("div", { class: "platform-header" });

    const chevron = el("span", { class: "platform-chevron" });
    chevron.innerHTML = ICON.chevron;
    header.appendChild(chevron);

    const iconEl = el("div", { class: "platform-icon" });
    iconEl.innerHTML = PLATFORM_ICONS[platform.icon] || "";
    header.appendChild(iconEl);

    const info = el("div", { class: "platform-info" });
    info.appendChild(el("span", { class: "platform-name" }, platform.display_name));
    if (platform.source) {
      info.appendChild(
        el("span", { class: "platform-status-hint" },
          platform.source.last_fetched_at
            ? `Last: ${formatDate(platform.source.last_fetched_at)}`
            : "Never fetched"
        )
      );
    } else {
      info.appendChild(el("span", { class: "platform-status-hint" }, platform.description));
    }
    header.appendChild(info);

    // On/off toggle switch
    const toggle = el("label", { class: "platform-toggle" });
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = !!platform.source;
    toggle.appendChild(checkbox);
    toggle.appendChild(el("span", { class: "platform-toggle-slider" }));
    // Stop click from toggling the disclosure
    toggle.addEventListener("click", (e) => e.stopPropagation());
    checkbox.addEventListener("change", async (e) => {
      e.stopPropagation();
      if (checkbox.checked) {
        // Enable
        const defaultConfig: Record<string, string | number> = {};
        for (const f of platform.config_fields) {
          if (f.default != null) defaultConfig[f.key] = f.default;
        }
        try {
          await createSource({
            name: platform.display_name,
            slug: platform.source_type,
            source_type: platform.source_type,
            config_json: JSON.stringify(defaultConfig),
            category: "",
          });
          showToast(`${platform.display_name} enabled`, "success");
          load();
        } catch (err) {
          checkbox.checked = false;
          showToast(`Error: ${err}`, "error");
        }
      } else {
        // Disable
        const confirmed = await showModal({
          title: "Disable platform",
          message: `Disable "${platform.display_name}" and remove all its articles? This cannot be undone.`,
          confirmLabel: "Disable",
          danger: true,
        });
        if (confirmed && platform.source) {
          await deleteSource(platform.source.id);
          showToast(`${platform.display_name} disabled`, "info");
          load();
        } else {
          checkbox.checked = true; // revert
        }
      }
    });
    header.appendChild(toggle);

    // Toggle disclosure on header click
    header.addEventListener("click", () => {
      const isOpen = card.classList.toggle("platform-open");
      chevron.classList.toggle("rotated", isOpen);
    });

    card.appendChild(header);

    // Collapsible body — config + status + actions (only when enabled)
    if (platform.source) {
      const body = el("div", { class: "platform-body" });

      const configSection = el("div", { class: "platform-config" });
      const currentConfig = (() => {
        try { return JSON.parse(platform.source!.config_json); } catch { return {}; }
      })();

      for (const field of platform.config_fields) {
        const fieldEl = el("div", { class: "platform-field" });
        fieldEl.appendChild(el("label", {}, field.label));

        if (field.type === "select" && field.options) {
          const select = document.createElement("select");
          select.className = "input";
          select.dataset.key = field.key;
          for (const opt of field.options) {
            const option = document.createElement("option");
            option.value = opt;
            option.textContent = opt;
            if ((currentConfig[field.key] ?? field.default) === opt) option.selected = true;
            select.appendChild(option);
          }
          fieldEl.appendChild(select);
        } else {
          const input = document.createElement("input");
          input.type = field.type === "number" ? "number" : "text";
          input.className = "input";
          input.dataset.key = field.key;
          if (field.min != null) input.min = String(field.min);
          if (field.max != null) input.max = String(field.max);
          input.value = String(currentConfig[field.key] ?? field.default ?? "");
          fieldEl.appendChild(input);
        }
        configSection.appendChild(fieldEl);
      }
      body.appendChild(configSection);

      // Footer: status (left) + actions (right) on one row
      const footer = el("div", { class: "platform-footer" });

      const status = el("div", { class: "platform-status" });
      status.appendChild(
        el("span", { class: "source-interval" },
          `Every ${platform.source.fetch_interval_minutes}m`)
      );
      status.appendChild(
        el("span", { class: "source-last-fetch" },
          platform.source.last_fetched_at
            ? `Last: ${formatDate(platform.source.last_fetched_at)}`
            : "Never fetched"
        )
      );
      status.appendChild(
        el("span", { class: "source-next-run" },
          `Next: ${formatNextRun(platform.source)}`)
      );
      footer.appendChild(status);

      const actions = el("div", { class: "platform-actions" });

      const saveBtn = el("button", {
        class: "btn-icon-action",
        title: "Save configuration",
      });
      saveBtn.innerHTML = ICON.save;
      saveBtn.addEventListener("click", async () => {
        const newConfig: Record<string, string | number> = { ...currentConfig };
        const inputs = configSection.querySelectorAll<HTMLInputElement | HTMLSelectElement>("input, select");
        inputs.forEach((inp) => {
          const key = inp.dataset.key;
          if (!key) return;
          newConfig[key] = inp.type === "number" ? Number(inp.value) : inp.value;
        });
        try {
          await updateSource(platform.source!.id, { config_json: JSON.stringify(newConfig) });
          showToast("Config saved", "success");
          load();
        } catch (err) {
          showToast(`Error: ${err}`, "error");
        }
      });
      actions.appendChild(saveBtn);

      const fetchBtn = el("button", {
        class: "btn-icon-action",
        title: `Fetch new articles from ${platform.display_name}`,
      });
      fetchBtn.innerHTML = ICON.refresh;
      fetchBtn.addEventListener("click", async () => {
        fetchBtn.classList.add("spinning");
        fetchBtn.setAttribute("disabled", "true");
        try {
          const log = await triggerFetch(platform.source!.id);
          showToast(
            `${platform.display_name}: ${log.items_new} new / ${log.items_found} found`,
            "success"
          );
          load();
        } catch (err) {
          showToast(`Fetch failed: ${err}`, "error");
          fetchBtn.classList.remove("spinning");
          fetchBtn.removeAttribute("disabled");
        }
      });
      actions.appendChild(fetchBtn);

      footer.appendChild(actions);
      body.appendChild(footer);
      card.appendChild(body);
    }

    return card;
  }

  function render(): void {
    container.innerHTML = "";

    // Platforms section
    if (platforms.length > 0) {
      const section = el("div", { class: "platforms-section" });
      section.appendChild(el("h3", { class: "section-heading" }, "Platforms"));
      const grid = el("div", { class: "platform-grid" });
      for (const p of platforms) {
        grid.appendChild(renderPlatformCard(p));
      }
      section.appendChild(grid);
      container.appendChild(section);
    }

    // Custom sources heading
    container.appendChild(el("h3", { class: "section-heading" }, "Custom Sources"));

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

    // Source list (exclude platform sources shown as cards above)
    const customSources = sources.filter(
      (s) => !platforms.some((p) => p.source_type === s.source_type)
    );

    if (customSources.length === 0) {
      container.appendChild(
        el(
          "div",
          { class: "empty-state" },
          "No custom sources yet. Add a source above."
        )
      );
      return;
    }

    const list = el("div", { class: "source-list" });
    for (const source of customSources) {
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

    const starBtn = el("button", {
      class: `btn-icon-action btn-icon-star${source.starred ? " starred" : ""}`,
      title: source.starred ? "Unstar source (stop showing all articles)" : "Star source (show all articles in inbox)",
    });
    starBtn.innerHTML = source.starred ? ICON.starFilled : ICON.starOutline;
    starBtn.addEventListener("click", async () => {
      try {
        await updateSource(source.id, { starred: !source.starred });
        showToast(source.starred ? `Unstarred ${source.name}` : `Starred ${source.name}`, "success");
        load();
      } catch (err) {
        showToast(`Error: ${err}`, "error");
      }
    });
    actions.appendChild(starBtn);

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

    // Authentication disclosure (all source types)
    {
      const hasAuth = (() => {
        try {
          const config = JSON.parse(source.config_json);
          return Boolean(config.auth_cookie);
        } catch {
          return false;
        }
      })();

      const authDisclosure = el("div", { class: "source-rules-toggle source-auth-toggle" });
      const authChevron = el("span", { class: "source-rules-chevron" });
      authChevron.innerHTML = ICON.chevron;
      authDisclosure.appendChild(authChevron);

      const lockIcon = el("span", { class: "source-rules-icon" });
      lockIcon.innerHTML = ICON.lock;
      authDisclosure.appendChild(lockIcon);

      const authIssue = authIssueMap.get(source.id);

      if (hasAuth) {
        authDisclosure.appendChild(
          el("span", { class: "source-rules-label" }, "Authentication")
        );
        if (authIssue && authIssue.truncated_count > 0) {
          authDisclosure.appendChild(
            el(
              "span",
              { class: "source-rules-date source-auth-warning" },
              `${authIssue.truncated_count} truncated (expired cookies?)`
            )
          );
        } else {
          authDisclosure.appendChild(
            el("span", { class: "source-rules-date source-auth-status" }, "Cookies configured")
          );
        }
      } else {
        authDisclosure.appendChild(
          el("span", { class: "source-rules-label source-rules-pending" }, "Authentication")
        );
        authDisclosure.appendChild(
          el("span", { class: "source-rules-hint" }, "Not configured")
        );
      }

      // Auth panel (hidden by default)
      const authPanel = el("div", { class: "source-auth-panel" });

      const cookieLabel = el("label", { class: "source-auth-label" }, "Cookie header");
      authPanel.appendChild(cookieLabel);

      const currentCookie = (() => {
        try {
          return JSON.parse(source.config_json).auth_cookie || "";
        } catch {
          return "";
        }
      })();

      const textarea = document.createElement("textarea");
      textarea.className = "input source-auth-textarea";
      textarea.placeholder = "paywall_session=abc; user_id=123";
      textarea.rows = 3;
      textarea.value = currentCookie;
      authPanel.appendChild(textarea);

      const authActions = el("div", { class: "source-auth-actions" });

      const saveBtn = el("button", { class: "btn btn-small btn-primary" }, "Save");
      saveBtn.addEventListener("click", async () => {
        try {
          const config = JSON.parse(source.config_json);
          const val = textarea.value.trim();
          if (val) {
            config.auth_cookie = val;
          } else {
            delete config.auth_cookie;
          }
          await updateSource(source.id, { config_json: JSON.stringify(config) });
          showToast("Authentication saved", "success");
          load();
        } catch {
          showToast("Failed to save authentication", "error");
        }
      });
      authActions.appendChild(saveBtn);

      const testBtn = el("button", { class: "btn btn-small" }, "Test");
      testBtn.addEventListener("click", async () => {
        testBtn.textContent = "Testing\u2026";
        testBtn.setAttribute("disabled", "true");
        try {
          // Save first so the test uses current textarea value
          const config = JSON.parse(source.config_json);
          const val = textarea.value.trim();
          if (val) {
            config.auth_cookie = val;
          } else {
            delete config.auth_cookie;
          }
          await updateSource(source.id, { config_json: JSON.stringify(config) });

          const result = await testSourceAuth(source.id);
          if (result.status === "ok") {
            showToast(`Auth OK — ${result.content_length} chars extracted`, "success");
          } else if (result.status === "truncated") {
            showToast(`Truncated (${result.content_length} chars) — ${result.message}`, "error");
          } else {
            showToast(result.message, "error");
          }
        } catch (err) {
          showToast(`Test failed: ${err}`, "error");
        } finally {
          testBtn.textContent = "Test";
          testBtn.removeAttribute("disabled");
        }
      });
      authActions.appendChild(testBtn);

      authPanel.appendChild(authActions);

      // Toggle behavior
      authDisclosure.addEventListener("click", () => {
        const isOpen = wrapper.classList.toggle("source-auth-open");
        authChevron.classList.toggle("rotated", isOpen);
      });

      wrapper.appendChild(authDisclosure);
      wrapper.appendChild(authPanel);
    }

    return wrapper;
  }

  load();
  return container;
}
