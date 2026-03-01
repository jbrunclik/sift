import { markRead, markUnread, sendFeedback } from "../api";
import type { Article } from "../types";
import { el, formatDate, scoreColor, truncate } from "../utils";
import { showToast } from "./toast";

function shortTitle(title: string, max = 40): string {
  if (title.length <= max) return title;
  return title.slice(0, max - 1) + "\u2026";
}

// SVG icon helpers (16x16, stroke-based, clean line style)
const ICON = {
  thumbUp: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M7 10v12"/><path d="M15 5.88 14 10h5.83a2 2 0 0 1 1.92 2.56l-2.33 8A2 2 0 0 1 17.5 22H4a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2h2.76a2 2 0 0 0 1.79-1.11L12 2a3.13 3.13 0 0 1 3 3.88Z"/></svg>`,
  thumbDown: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 14V2"/><path d="M9 18.12 10 14H4.17a2 2 0 0 1-1.92-2.56l2.33-8A2 2 0 0 1 6.5 2H20a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-2.76a2 2 0 0 0-1.79 1.11L12 22a3.13 3.13 0 0 1-3-3.88Z"/></svg>`,
  check: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><path d="m9 11 3 3L22 4"/></svg>`,
  undo: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/></svg>`,
};

export interface CardCallbacks {
  onUpdate?: () => void;
  onExit?: (card: HTMLElement, article: Article) => void;
}

export function ArticleCard(
  article: Article,
  callbacks?: CardCallbacks
): HTMLElement {
  const card = el("article", {
    class: `article-card${article.is_read ? " read" : ""}${article.feedback === 1 ? " feedback-positive" : ""}${article.feedback === -1 ? " feedback-negative" : ""}`,
    tabindex: "-1",
  });
  card.dataset.articleId = String(article.id);

  function animateOut(cb: () => void): void {
    card.classList.add("exiting");
    const handler = (): void => {
      card.removeEventListener("transitionend", handler);
      cb();
    };
    card.addEventListener("transitionend", handler);
    // Fallback if transitionend doesn't fire
    setTimeout(handler, 350);
  }

  function exitCard(): void {
    if (callbacks?.onExit) {
      animateOut(() => callbacks.onExit!(card, article));
    }
  }

  // Header: score + source + date
  const header = el("div", { class: "card-header" });

  if (article.relevance_score !== null && article.relevance_score >= 0) {
    const score = el(
      "span",
      { class: "score-badge" },
      article.relevance_score.toFixed(1)
    );
    score.style.color = scoreColor(article.relevance_score);
    score.style.backgroundColor = `color-mix(in srgb, ${scoreColor(article.relevance_score)} 12%, transparent)`;
    if (article.score_explanation) {
      score.title = article.score_explanation;
    }
    header.appendChild(score);
  }

  if (article.source_name) {
    header.appendChild(
      el("span", { class: "source-label" }, article.source_name)
    );
  }

  header.appendChild(
    el("span", { class: "date-label" }, formatDate(article.published_at))
  );

  card.appendChild(header);

  // Title (link)
  const titleLink = el(
    "a",
    {
      class: "card-title",
      href: article.url,
      target: "_blank",
      rel: "noopener",
    },
    article.title
  );
  titleLink.addEventListener("click", async () => {
    // Clicking an article = positive signal (user found it interesting)
    if (article.feedback !== 1) {
      await sendFeedback(article.id, 1);
      article.feedback = 1;
      article.is_read = true;
      exitCard();
    } else if (!article.is_read) {
      await markRead(article.id);
      article.is_read = true;
      exitCard();
    }
  });
  card.appendChild(titleLink);

  // Summary or snippet
  const text = article.summary || article.content_snippet;
  if (text) {
    card.appendChild(
      el("p", { class: "card-snippet" }, truncate(text, 200))
    );
  }

  // Tags
  if (article.tags.length > 0) {
    const tagsContainer = el("div", { class: "card-tags" });
    for (const tag of article.tags) {
      tagsContainer.appendChild(el("span", { class: "tag-chip" }, tag));
    }
    card.appendChild(tagsContainer);
  }

  // Actions: feedback + read toggle
  const actions = el("div", { class: "card-actions" });

  // Thumbs up
  const thumbUp = el("button", {
    class: `btn-feedback btn-up${article.feedback === 1 ? " active" : ""}`,
    title: "More like this (u)",
  });
  thumbUp.innerHTML = ICON.thumbUp;
  thumbUp.addEventListener("click", async () => {
    const newRating = article.feedback === 1 ? 0 : 1;
    await sendFeedback(article.id, newRating);
    const prevFeedback = article.feedback;
    article.feedback = newRating || null;
    if (newRating !== 0) {
      showToast(`Liked: ${shortTitle(article.title)}`, "success", {
        label: "Undo",
        onClick: async () => {
          await sendFeedback(article.id, 0);
          await markUnread(article.id);
          article.feedback = prevFeedback;
          article.is_read = false;
          callbacks?.onUpdate?.();
        },
      });
      exitCard();
    } else {
      callbacks?.onUpdate?.();
    }
  });

  // Thumbs down
  const thumbDown = el("button", {
    class: `btn-feedback btn-down${article.feedback === -1 ? " active" : ""}`,
    title: "Less like this (d)",
  });
  thumbDown.innerHTML = ICON.thumbDown;
  thumbDown.addEventListener("click", async () => {
    const newRating = article.feedback === -1 ? 0 : -1;
    await sendFeedback(article.id, newRating);
    const prevFeedback = article.feedback;
    article.feedback = newRating || null;
    if (newRating !== 0) {
      showToast(`Dismissed: ${shortTitle(article.title)}`, "info", {
        label: "Undo",
        onClick: async () => {
          await sendFeedback(article.id, 0);
          await markUnread(article.id);
          article.feedback = prevFeedback;
          article.is_read = false;
          callbacks?.onUpdate?.();
        },
      });
      exitCard();
    } else {
      callbacks?.onUpdate?.();
    }
  });

  // Read toggle
  const readBtn = el("button", {
    class: "btn-feedback btn-read-toggle",
    title: article.is_read ? "Mark unread" : "Mark read (e)",
  });
  readBtn.innerHTML = article.is_read ? ICON.undo : ICON.check;
  readBtn.addEventListener("click", async () => {
    if (article.is_read) {
      await markUnread(article.id);
      article.is_read = false;
      callbacks?.onUpdate?.();
    } else {
      await markRead(article.id);
      article.is_read = true;
      showToast(`Read: ${shortTitle(article.title)}`, "info", {
        label: "Undo",
        onClick: async () => {
          await markUnread(article.id);
          article.is_read = false;
          callbacks?.onUpdate?.();
        },
      });
      exitCard();
    }
  });

  // Core actions: up, read, down
  actions.appendChild(thumbUp);
  actions.appendChild(readBtn);
  actions.appendChild(thumbDown);

  // Spacer to push secondary actions right
  const spacer = el("span", { class: "card-actions-spacer" });
  actions.appendChild(spacer);


  // "Why?" button (subtle, secondary)
  if (article.score_explanation) {
    const whyBtn = el("button", { class: "btn-feedback btn-why", title: "Score explanation" });
    whyBtn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><path d="M12 17h.01"/></svg>`;
    let explanationPanel: HTMLElement | null = null;
    whyBtn.addEventListener("click", () => {
      if (explanationPanel) {
        explanationPanel.remove();
        explanationPanel = null;
        whyBtn.classList.remove("active");
      } else {
        explanationPanel = el(
          "div",
          { class: "score-explanation" },
          article.score_explanation!
        );
        card.appendChild(explanationPanel);
        whyBtn.classList.add("active");
      }
    });
    actions.appendChild(whyBtn);
  }

  card.appendChild(actions);

  return card;
}
