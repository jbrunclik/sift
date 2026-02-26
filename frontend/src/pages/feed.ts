import { getSources } from "../api";
import { ArticleList } from "../components/article-list";
import { SearchBar } from "../components/search-bar";
import { el } from "../utils";

export function FeedPage(): HTMLElement {
  const page = el("div", { class: "page page-feed" });

  // Toolbar: search + filters
  const toolbar = el("div", { class: "feed-toolbar" });

  let currentSearch = "";
  let currentSource = "";
  let showAll = false;
  let showUnread = false;
  let listContainer: HTMLElement;

  function reloadList(): void {
    if (listContainer) listContainer.remove();
    listContainer = ArticleList({
      search: currentSearch || undefined,
      source_slug: currentSource || undefined,
      // When searching, always show all results. Otherwise respect toggle.
      show_all: currentSearch ? true : showAll || undefined,
      unread: showUnread || undefined,
    });
    page.appendChild(listContainer);
  }

  // Search
  toolbar.appendChild(
    SearchBar((query) => {
      currentSearch = query;
      reloadList();
    })
  );

  // Source filter dropdown
  const sourceSelect = el(
    "select",
    { class: "input filter-source" }
  ) as HTMLSelectElement;

  function refreshSourceFilter(): void {
    const prev = sourceSelect.value;
    sourceSelect.innerHTML = "";
    sourceSelect.appendChild(el("option", { value: "" }, "All sources"));
    getSources().then((sources) => {
      for (const s of sources) {
        sourceSelect.appendChild(el("option", { value: s.slug }, s.name));
      }
      sourceSelect.value = prev;
    });
  }
  refreshSourceFilter();

  sourceSelect.addEventListener("change", () => {
    currentSource = sourceSelect.value;
    reloadList();
  });
  toolbar.appendChild(sourceSelect);

  // Refresh source list when page becomes visible (e.g. navigating back from sources page)
  const visibilityHandler = (): void => {
    if (!document.hidden) refreshSourceFilter();
  };
  document.addEventListener("visibilitychange", visibilityHandler);

  // Also refresh on hashchange (SPA navigation)
  const hashHandler = (): void => {
    if (location.hash === "" || location.hash === "#/" || location.hash === "#/feed") {
      refreshSourceFilter();
    }
  };
  window.addEventListener("hashchange", hashHandler);

  // Show all toggle (default: curated feed only)
  const showAllBtn = el("button", { class: "btn btn-small" }, "Show all");
  showAllBtn.addEventListener("click", () => {
    showAll = !showAll;
    showAllBtn.classList.toggle("active", showAll);
    reloadList();
  });
  toolbar.appendChild(showAllBtn);

  // Unread toggle
  const unreadBtn = el("button", { class: "btn btn-small" }, "Unread");
  unreadBtn.addEventListener("click", () => {
    showUnread = !showUnread;
    unreadBtn.classList.toggle("active", showUnread);
    reloadList();
  });
  toolbar.appendChild(unreadBtn);

  page.appendChild(toolbar);

  // Initial article list — curated (only high-relevance articles)
  listContainer = ArticleList();
  page.appendChild(listContainer);

  return page;
}
