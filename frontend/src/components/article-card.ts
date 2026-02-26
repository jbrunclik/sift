import { markRead, markUnread, sendFeedback } from "../api";
import type { Article } from "../types";
import { el, formatDate, scoreColor, truncate } from "../utils";
import { showToast } from "./toast";

const CURATED_THRESHOLD = 7.0;

export function ArticleCard(
  article: Article,
  onUpdate?: () => void
): HTMLElement {
  const card = el("article", {
    class: `article-card${article.is_read ? " read" : ""}${article.feedback === 1 ? " feedback-positive" : ""}${article.feedback === -1 ? " feedback-negative" : ""}`,
  });

  // Header: score + source + date
  const header = el("div", { class: "card-header" });

  if (article.relevance_score !== null) {
    const score = el(
      "span",
      { class: "score-badge" },
      article.relevance_score.toFixed(1)
    );
    score.style.backgroundColor = scoreColor(article.relevance_score);
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
    if (!article.is_read) {
      await markRead(article.id);
      article.is_read = true;
      card.classList.add("read");
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
    title: "Interesting",
  });
  thumbUp.textContent = "\u25B2";
  thumbUp.addEventListener("click", async () => {
    const newRating = article.feedback === 1 ? 0 : 1;
    await sendFeedback(article.id, newRating);
    article.feedback = newRating || null;
    onUpdate?.();
  });

  // Thumbs down
  const thumbDown = el("button", {
    class: `btn-feedback btn-down${article.feedback === -1 ? " active" : ""}`,
    title: "Not interesting",
  });
  thumbDown.textContent = "\u25BC";
  thumbDown.addEventListener("click", async () => {
    const newRating = article.feedback === -1 ? 0 : -1;
    await sendFeedback(article.id, newRating);
    article.feedback = newRating || null;
    onUpdate?.();
  });

  // "Missed" button: shown on articles below curated threshold.
  // This is a strong positive signal — "Sift should have shown me this."
  const isBelowThreshold =
    article.relevance_score !== null &&
    article.relevance_score < CURATED_THRESHOLD;

  if (isBelowThreshold && article.feedback !== 1) {
    const missedBtn = el("button", {
      class: "btn-feedback btn-missed",
      title: "Should have been in my feed",
    });
    missedBtn.textContent = "Missed";
    missedBtn.addEventListener("click", async () => {
      await sendFeedback(article.id, 1);
      article.feedback = 1;
      showToast("Noted \u2014 Sift will learn from this", "success");
      onUpdate?.();
    });
    actions.appendChild(missedBtn);
  }

  // Read toggle
  const readBtn = el("button", {
    class: "btn-read-toggle",
    title: article.is_read ? "Mark unread" : "Mark read",
  });
  readBtn.textContent = article.is_read ? "\u25CB" : "\u25CF";
  readBtn.addEventListener("click", async () => {
    if (article.is_read) {
      await markUnread(article.id);
      article.is_read = false;
    } else {
      await markRead(article.id);
      article.is_read = true;
    }
    onUpdate?.();
  });

  actions.appendChild(thumbUp);
  actions.appendChild(thumbDown);
  actions.appendChild(readBtn);
  card.appendChild(actions);

  return card;
}
