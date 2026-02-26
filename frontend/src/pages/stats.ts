import { getStats } from "../api";
import { el } from "../utils";

export function StatsPage(): HTMLElement {
  const page = el("div", { class: "page page-stats" });
  page.appendChild(el("h1", {}, "Stats"));

  const content = el("div", { class: "stats-content" });
  page.appendChild(content);

  getStats().then((stats) => {
    content.innerHTML = "";

    const grid = el("div", { class: "stats-grid" });
    const cards: [string, string][] = [
      ["Total Articles", String(stats.total_articles)],
      ["Scored", String(stats.scored_articles)],
      [
        "Avg Score",
        stats.average_score !== null ? stats.average_score.toFixed(1) : "N/A",
      ],
      ["Feedback Given", String(stats.total_feedback)],
      [
        "Thumbs Up / Down",
        `${stats.positive_feedback} / ${stats.negative_feedback}`,
      ],
    ];

    for (const [label, value] of cards) {
      const card = el("div", { class: "stat-card" });
      card.appendChild(el("div", { class: "stat-value" }, value));
      card.appendChild(el("div", { class: "stat-label" }, label));
      grid.appendChild(card);
    }
    content.appendChild(grid);
  });

  return page;
}
