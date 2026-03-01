import { getSources, markRead, markUnread, sendFeedback } from "../api";
import { ArticleList } from "../components/article-list";
import { SearchBar } from "../components/search-bar";
import { showToast } from "../components/toast";
import { el } from "../utils";

const TRAINING_KEY = "sift-training-mode";

function getTrainingMode(): boolean {
  return localStorage.getItem(TRAINING_KEY) === "true";
}

function setTrainingMode(on: boolean): void {
  localStorage.setItem(TRAINING_KEY, String(on));
}

export function FeedPage(): HTMLElement {
  const page = el("div", { class: "page page-feed" });

  const toolbar = el("div", { class: "feed-toolbar" });

  let currentSearch = "";
  let currentSource = "";
  let trainingMode = getTrainingMode();
  let listContainer: HTMLElement;

  function reloadList(): void {
    if (listContainer) listContainer.remove();
    listContainer = ArticleList({
      search: currentSearch || undefined,
      source_slug: currentSource || undefined,
      // Training mode: show all scores; Normal: curated only (score >= 7)
      // When searching, always show all results
      show_all: currentSearch ? true : trainingMode || undefined,
      // Always show unread only (inbox behavior)
      unread: true,
      onInboxCount: updateTabTitle,
    });
    page.appendChild(listContainer);
  }

  function updateTabTitle(count: number): void {
    document.title = count > 0 ? `[${count}] Sift` : "Sift";
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

  // Refresh source list when page becomes visible
  const visibilityHandler = (): void => {
    if (!document.hidden) refreshSourceFilter();
  };
  document.addEventListener("visibilitychange", visibilityHandler);

  const hashHandler = (): void => {
    if (location.hash === "" || location.hash === "#/" || location.hash === "#/feed") {
      refreshSourceFilter();
    }
  };
  window.addEventListener("hashchange", hashHandler);

  // Training mode toggle
  const trainingBtn = el(
    "button",
    { class: `btn btn-training${trainingMode ? " active" : ""}` }
  );
  trainingBtn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="m16 12-4-4-4 4"/><path d="M12 16V8"/></svg> Train`;
  trainingBtn.title = "Training mode: show all articles for fine-tuning your preferences (t)";
  trainingBtn.addEventListener("click", () => {
    trainingMode = !trainingMode;
    setTrainingMode(trainingMode);
    trainingBtn.classList.toggle("active", trainingMode);
    reloadList();
  });
  toolbar.appendChild(trainingBtn);

  page.appendChild(toolbar);

  // Initial article list — inbox: curated + unread
  listContainer = ArticleList({
    show_all: trainingMode || undefined,
    unread: true,
    onInboxCount: updateTabTitle,
  });
  page.appendChild(listContainer);

  // Keyboard shortcuts
  function getListAPI(): {
    moveDown: () => void;
    moveUp: () => void;
    getFocusedArticle: () => { id: number; url: string; feedback: number | null; is_read: boolean } | null;
    getFocusedCard: () => HTMLElement | null;
  } | null {
    const list = page.querySelector("[data-list-id='article-list']");
    if (!list) return null;
    return (list as unknown as Record<string, unknown>).__list as ReturnType<typeof getListAPI>;
  }

  function handleKeyDown(e: KeyboardEvent): void {
    // Skip if in input/textarea/select
    const tag = (e.target as HTMLElement).tagName;
    if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;

    const api = getListAPI();
    if (!api) return;

    switch (e.key) {
      case "j": {
        e.preventDefault();
        api.moveDown();
        break;
      }
      case "k": {
        e.preventDefault();
        api.moveUp();
        break;
      }
      case "o":
      case "Enter": {
        // Delegate to the card's title link — its click handler
        // already handles upvote + exit animation
        const card = api.getFocusedCard();
        if (card) {
          e.preventDefault();
          const link = card.querySelector<HTMLAnchorElement>(".card-title");
          if (link) link.click();
        }
        break;
      }
      case "u": {
        const article = api.getFocusedArticle();
        const card = api.getFocusedCard();
        if (article && card) {
          e.preventDefault();
          const newRating = article.feedback === 1 ? 0 : 1;
          sendFeedback(article.id, newRating).then(() => {
            if (newRating !== 0) {
              showToast("Liked", "success", {
                label: "Undo",
                onClick: async () => {
                  await sendFeedback(article.id, 0);
                  await markUnread(article.id);
                  reloadList();
                },
              });
              card.classList.add("exiting");
              setTimeout(() => reloadList(), 300);
            } else {
              reloadList();
            }
          });
        }
        break;
      }
      case "d": {
        const article = api.getFocusedArticle();
        const card = api.getFocusedCard();
        if (article && card) {
          e.preventDefault();
          const newRating = article.feedback === -1 ? 0 : -1;
          sendFeedback(article.id, newRating).then(() => {
            if (newRating !== 0) {
              showToast("Dismissed", "info", {
                label: "Undo",
                onClick: async () => {
                  await sendFeedback(article.id, 0);
                  await markUnread(article.id);
                  reloadList();
                },
              });
              card.classList.add("exiting");
              setTimeout(() => reloadList(), 300);
            } else {
              reloadList();
            }
          });
        }
        break;
      }
      case "e":
      case "m": {
        const article = api.getFocusedArticle();
        const card = api.getFocusedCard();
        if (article && card) {
          e.preventDefault();
          if (article.is_read) {
            markUnread(article.id).then(() => {
              article.is_read = false;
              reloadList();
            });
          } else {
            markRead(article.id).then(() => {
              showToast("Read", "info", {
                label: "Undo",
                onClick: async () => {
                  await markUnread(article.id);
                  reloadList();
                },
              });
              card.classList.add("exiting");
              setTimeout(() => reloadList(), 300);
            });
          }
        }
        break;
      }
      case "t": {
        e.preventDefault();
        trainingMode = !trainingMode;
        setTrainingMode(trainingMode);
        trainingBtn.classList.toggle("active", trainingMode);
        reloadList();
        break;
      }
      case "?": {
        e.preventDefault();
        showHelpOverlay();
        break;
      }
    }
  }

  document.addEventListener("keydown", handleKeyDown);

  // Cleanup: remove global listeners when this page element is removed from the DOM
  const cleanupObserver = new MutationObserver(() => {
    if (!page.isConnected) {
      document.removeEventListener("visibilitychange", visibilityHandler);
      window.removeEventListener("hashchange", hashHandler);
      document.removeEventListener("keydown", handleKeyDown);
      cleanupObserver.disconnect();
    }
  });
  cleanupObserver.observe(document.body, { childList: true, subtree: true });

  return page;
}

function showHelpOverlay(): void {
  // Remove existing
  document.querySelector(".help-overlay")?.remove();

  const overlay = el("div", { class: "help-overlay" });
  overlay.addEventListener("click", () => overlay.remove());
  document.addEventListener("keydown", function handler(e) {
    if (e.key === "Escape" || e.key === "?") {
      overlay.remove();
      document.removeEventListener("keydown", handler);
    }
  });

  const panel = el("div", { class: "help-panel" });
  panel.innerHTML = `
    <h2>Keyboard Shortcuts</h2>
    <div class="help-grid">
      <div class="help-row"><kbd>j</kbd><span>Next article</span></div>
      <div class="help-row"><kbd>k</kbd><span>Previous article</span></div>
      <div class="help-row"><kbd>o</kbd> / <kbd>Enter</kbd><span>Open in new tab</span></div>
      <div class="help-row"><kbd>u</kbd><span>Upvote</span></div>
      <div class="help-row"><kbd>d</kbd><span>Downvote</span></div>
      <div class="help-row"><kbd>e</kbd> / <kbd>m</kbd><span>Mark as read</span></div>
      <div class="help-row"><kbd>t</kbd><span>Toggle training mode</span></div>
      <div class="help-row"><kbd>?</kbd><span>Show this help</span></div>
    </div>
    <p class="help-dismiss">Press <kbd>Esc</kbd> or <kbd>?</kbd> to close</p>
  `;
  overlay.appendChild(panel);
  document.body.appendChild(overlay);
}
