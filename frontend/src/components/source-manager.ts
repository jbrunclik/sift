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
};

function getFaviconUrl(source: Source): string | null {
  try {
    const config = JSON.parse(source.config_json);
    const feedUrl = config.feed_url;
    if (!feedUrl) return null;
    const domain = new URL(feedUrl).hostname;
    return `https://www.google.com/s2/favicons?domain=${domain}&sz=32`;
  } catch {
    return null;
  }
}

function formatNextRun(source: Source): string {
  if (!source.last_fetched_at) return "pending";
  const dateStr = source.last_fetched_at;
  const normalized = dateStr.endsWith("Z") || dateStr.includes("+") ? dateStr : dateStr + "Z";
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

export function SourceManager(): HTMLElement {
  const container = el("div", { class: "source-manager" });
  let sources: Source[] = [];

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

    // Add source form
    const form = el("form", { class: "source-form" });
    const nameInput = el("input", {
      type: "text",
      placeholder: "Name (e.g. iDNES)",
      class: "input",
    }) as HTMLInputElement;
    const urlInput = el("input", {
      type: "url",
      placeholder: "Feed URL (e.g. https://example.com/rss.xml)",
      class: "input input-wide",
    }) as HTMLInputElement;

    // Category input with datalist for autocomplete
    const categoryInput = el("input", {
      type: "text",
      placeholder: "Category (optional)",
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
      title: "Add this RSS feed as a source",
    });
    addBtn.innerHTML = `${ICON.plus}<span>Add</span>`;

    form.appendChild(nameInput);
    form.appendChild(urlInput);
    form.appendChild(categoryInput);
    form.appendChild(datalist);
    form.appendChild(addBtn);

    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const name = nameInput.value.trim();
      const feedUrl = urlInput.value.trim();
      if (!name || !feedUrl) {
        showToast("Name and feed URL are required", "error");
        return;
      }
      try {
        await createSource({
          name,
          slug: slugify(name),
          source_type: "rss",
          config_json: JSON.stringify({ feed_url: feedUrl }),
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
          "No sources yet. Add an RSS feed above."
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
    // Prevent double opening
    if (categoryRow.querySelector("input")) return;

    categoryRow.innerHTML = "";
    const catInput = document.createElement("input");
    catInput.type = "text";
    catInput.className = "input input-inline";
    catInput.placeholder = "Category";
    catInput.value = source.category;
    // Attach to existing datalist if present
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
    // Delay focus to avoid immediate blur
    requestAnimationFrame(() => catInput.focus());
  }

  function renderSourceRow(source: Source): HTMLElement {
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

    // Left: name + category
    const info = el("div", { class: "source-info" });
    info.appendChild(el("span", { class: "source-name" }, source.name));

    const categoryRow = el("div", { class: "source-category-row" });
    // Show category label (or "Uncategorized" placeholder) — always clickable to edit
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
    // Pencil icon (visible on row hover)
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

    return row;
  }

  load();
  return container;
}
