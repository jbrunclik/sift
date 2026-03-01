import { getArticles } from "../api";
import type { Article } from "../types";
import { el } from "../utils";
import { ArticleCard } from "./article-card";

export interface ArticleListOptions {
  source_slug?: string;
  search?: string;
  show_all?: boolean;
  unread?: boolean;
  onInboxCount?: (count: number) => void;
}

export function ArticleList(params?: ArticleListOptions): HTMLElement {
  const container = el("div", { class: "article-list" });
  let articles: Article[] = [];
  let offset = 0;
  const limit = 30;
  let loading = false;
  let hasMore = true;
  let sentinel: HTMLElement | null = null;
  let focusedIndex = -1;

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
    } catch (err) {
      console.error("Failed to load articles:", err);
    } finally {
      loading = false;
    }

    render();
  }

  function removeArticle(card: HTMLElement, article: Article): void {
    const idx = articles.indexOf(article);
    if (idx >= 0) articles.splice(idx, 1);
    card.remove();

    // Update inbox count
    params?.onInboxCount?.(articles.length);

    // Focus management: move to next card, or previous
    const cards = container.querySelectorAll<HTMLElement>(".article-card:not(.exiting)");
    if (cards.length > 0) {
      const newIdx = Math.min(idx, cards.length - 1);
      focusedIndex = newIdx;
      cards[newIdx].classList.add("focused");
      cards[newIdx].scrollIntoView({ block: "nearest" });
    } else {
      focusedIndex = -1;
      // Check if empty
      if (articles.length === 0 && !hasMore) {
        render();
      }
    }
  }

  function render(): void {
    // Remove all children except the sentinel
    while (container.firstChild) {
      if (container.firstChild === sentinel) break;
      container.removeChild(container.firstChild);
    }

    if (articles.length === 0 && !loading) {
      const empty = el("div", { class: "empty-state" });
      const illustration = el("div", { class: "empty-illustration" });
      illustration.innerHTML = `<svg width="120" height="120" viewBox="0 0 120 120" fill="none" xmlns="http://www.w3.org/2000/svg">
        <circle cx="60" cy="60" r="50" stroke="var(--color-border)" stroke-width="2" fill="var(--color-surface)" />
        <path d="M40 65 L55 78 L82 45" stroke="var(--color-primary)" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" fill="none" />
        <circle cx="60" cy="60" r="36" stroke="var(--color-primary)" stroke-width="1.5" opacity="0.2" fill="none" />
      </svg>`;
      empty.appendChild(illustration);
      empty.appendChild(
        el("div", { class: "empty-title" }, "You\u2019re all caught up!")
      );
      empty.appendChild(
        el(
          "div",
          { class: "empty-text" },
          "No unread articles right now. Check back later or add more sources."
        )
      );
      container.insertBefore(empty, sentinel);
      return;
    }

    params?.onInboxCount?.(articles.length);

    for (const article of articles) {
      container.insertBefore(
        ArticleCard(article, {
          onUpdate: () => render(),
          onExit: (card, art) => removeArticle(card, art),
        }),
        sentinel
      );
    }
  }

  // Focus management for keyboard navigation
  function getFocusableCards(): HTMLElement[] {
    return Array.from(
      container.querySelectorAll<HTMLElement>(".article-card:not(.exiting)")
    );
  }

  function setFocused(idx: number): void {
    const cards = getFocusableCards();
    if (cards.length === 0) return;
    // Clear previous focus
    for (const c of cards) c.classList.remove("focused");
    focusedIndex = Math.max(0, Math.min(idx, cards.length - 1));
    const card = cards[focusedIndex];
    card.classList.add("focused");
    card.scrollIntoView({ block: "nearest" });
  }

  function getFocusedArticle(): Article | null {
    const cards = getFocusableCards();
    if (focusedIndex < 0 || focusedIndex >= cards.length) return null;
    const id = Number(cards[focusedIndex].dataset.articleId);
    return articles.find((a) => a.id === id) ?? null;
  }

  function getFocusedCard(): HTMLElement | null {
    const cards = getFocusableCards();
    if (focusedIndex < 0 || focusedIndex >= cards.length) return null;
    return cards[focusedIndex];
  }

  // Expose navigation API for keyboard shortcuts
  container.dataset.listId = "article-list";
  (container as unknown as Record<string, unknown>).__list = {
    moveDown: () => setFocused(focusedIndex + 1),
    moveUp: () => setFocused(Math.max(0, focusedIndex - 1)),
    getFocusedArticle,
    getFocusedCard,
  };

  // Create sentinel once
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
