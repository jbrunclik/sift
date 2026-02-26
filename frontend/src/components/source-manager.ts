import {
  createSource,
  deleteSource,
  getSources,
  triggerFetch,
} from "../api";
import type { Source } from "../types";
import { el, formatDate } from "../utils";
import { showToast } from "./toast";

function slugify(name: string): string {
  return name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

export function SourceManager(): HTMLElement {
  const container = el("div", { class: "source-manager" });
  let sources: Source[] = [];

  async function load(): Promise<void> {
    sources = await getSources();
    render();
  }

  function render(): void {
    container.innerHTML = "";

    // Add source form — simple: name + feed URL
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
    const addBtn = el(
      "button",
      { type: "submit", class: "btn btn-primary" },
      "Add"
    );

    form.appendChild(nameInput);
    form.appendChild(urlInput);
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
        });
        showToast("Source added", "success");
        nameInput.value = "";
        urlInput.value = "";
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
      const row = el("div", { class: "source-row" });
      row.appendChild(el("span", { class: "source-name" }, source.name));
      row.appendChild(
        el(
          "span",
          { class: "source-last-fetch" },
          source.last_fetched_at
            ? `Last: ${formatDate(source.last_fetched_at)}`
            : "Never fetched"
        )
      );

      const fetchBtn = el(
        "button",
        { class: "btn btn-small" },
        "Fetch now"
      );
      fetchBtn.addEventListener("click", async () => {
        fetchBtn.textContent = "Fetching...";
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
          fetchBtn.textContent = "Fetch now";
          fetchBtn.removeAttribute("disabled");
        }
      });

      const deleteBtn = el(
        "button",
        { class: "btn btn-small btn-danger" },
        "Delete"
      );
      deleteBtn.addEventListener("click", async () => {
        if (confirm(`Delete source "${source.name}"?`)) {
          await deleteSource(source.id);
          showToast("Source deleted", "info");
          load();
        }
      });

      row.appendChild(fetchBtn);
      row.appendChild(deleteBtn);
      list.appendChild(row);
    }
    container.appendChild(list);
  }

  load();
  return container;
}
