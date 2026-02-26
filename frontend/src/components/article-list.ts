import { getArticles } from "../api";
import type { Article } from "../types";
import { el } from "../utils";
import { ArticleCard } from "./article-card";

export function ArticleList(params?: {
  source_slug?: string;
  search?: string;
  show_all?: boolean;
  unread?: boolean;
}): HTMLElement {
  const container = el("div", { class: "article-list" });
  let articles: Article[] = [];
  let offset = 0;
  const limit = 30;
  let loading = false;
  let hasMore = true;
  let sentinel: HTMLElement | null = null;

  async function loadMore(): Promise<void> {
    if (loading || !hasMore) return;
    loading = true;

    try {
      const newArticles = await getArticles({
        limit,
        offset,
        source_slug: params?.source_slug,
        search: params?.search,
        show_all: params?.show_all,
        unread: params?.unread,
      });

      articles = [...articles, ...newArticles];
      offset += newArticles.length;
      if (newArticles.length < limit) hasMore = false;

      render();
    } catch (err) {
      console.error("Failed to load articles:", err);
    } finally {
      loading = false;
    }
  }

  function render(): void {
    // Remove all children except the sentinel
    while (container.firstChild) {
      if (container.firstChild === sentinel) break;
      container.removeChild(container.firstChild);
    }

    if (articles.length === 0 && !loading) {
      const empty = el(
        "div",
        { class: "empty-state" },
        "Nothing curated yet. Add sources and wait for scoring, or click \"Show all\" to browse."
      );
      container.insertBefore(empty, sentinel);
      return;
    }

    // Insert cards before the sentinel
    for (const article of articles) {
      container.insertBefore(ArticleCard(article, () => render()), sentinel);
    }

    if (hasMore && !sentinel) {
      const loadMoreBtn = el(
        "button",
        { class: "btn-load-more" },
        "Load more"
      );
      loadMoreBtn.addEventListener("click", () => loadMore());
      container.insertBefore(loadMoreBtn, sentinel);
    }
  }

  // Create sentinel once, keep it alive across renders
  sentinel = el("div", { class: "scroll-sentinel" });
  container.appendChild(sentinel);

  const observer = new IntersectionObserver(
    (entries) => {
      if (entries[0]?.isIntersecting && hasMore && !loading) {
        loadMore();
      }
    },
    { rootMargin: "200px" }
  );
  observer.observe(sentinel);

  // Initial load
  loadMore();

  return container;
}
