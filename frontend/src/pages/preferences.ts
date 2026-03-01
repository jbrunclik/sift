import {
  getPreferences,
  getTagWeights,
  resetTagWeight,
  updatePreferences,
} from "../api";
import type { TagWeight, UserPreferences } from "../types";
import { el } from "../utils";
import { showToast } from "../components/toast";

const ICON_SAVE = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/></svg>`;
const ICON_RESET = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/></svg>`;

const LANGUAGES = [
  { code: "en", label: "\uD83C\uDDEC\uD83C\uDDE7 English" },
  { code: "cs", label: "\uD83C\uDDE8\uD83C\uDDFF Czech" },
];

const DEFAULT_TAG_SHOW = 20;

export function PreferencesPage(): HTMLElement {
  const page = el("div", { class: "page page-preferences" });
  page.appendChild(el("h1", {}, "Preferences"));

  const content = el("div", { class: "preferences-content" });
  page.appendChild(content);

  load(content);
  return page;
}

function load(container: HTMLElement): void {
  Promise.all([getPreferences(), getTagWeights()]).then(([prefs, tags]) => {
    container.innerHTML = "";
    container.appendChild(renderLanguage(prefs, container));
    container.appendChild(renderProfile(prefs, container));
    container.appendChild(renderInterests(prefs, container));
    container.appendChild(renderTagWeights(tags, container));
    container.appendChild(renderVersion(prefs));
  });
}

function renderLanguage(
  prefs: UserPreferences,
  container: HTMLElement
): HTMLElement {
  const section = el("div", { class: "prefs-section" });
  section.appendChild(el("h2", {}, "Summary Language"));
  section.appendChild(
    el(
      "p",
      { class: "prefs-hint" },
      "Language for AI-generated article summaries."
    )
  );

  const pillContainer = el("div", { class: "language-pills" });
  for (const lang of LANGUAGES) {
    const pill = el("button", {
      class: `btn btn-small btn-pill${prefs.summary_language === lang.code ? " active" : ""}`,
    }, lang.label);
    pill.addEventListener("click", async () => {
      try {
        await updatePreferences({ summary_language: lang.code });
        showToast(`Language set to ${lang.label}`, "success");
        load(container);
      } catch {
        showToast("Failed to update language", "error");
      }
    });
    pillContainer.appendChild(pill);
  }
  section.appendChild(pillContainer);
  return section;
}

function renderProfile(
  prefs: UserPreferences,
  container: HTMLElement
): HTMLElement {
  const section = el("div", { class: "prefs-section" });
  section.appendChild(el("h2", {}, "Profile"));
  section.appendChild(
    el(
      "p",
      { class: "prefs-hint" },
      "Describe your interests in prose. This guides how Sift scores articles."
    )
  );

  const textarea = document.createElement("textarea");
  textarea.className = "prefs-textarea";
  textarea.rows = 4;
  textarea.value = prefs.prose_profile;
  textarea.placeholder =
    "e.g. I'm a backend engineer interested in distributed systems, Rust, and database internals...";
  section.appendChild(textarea);

  const saveBtn = el("button", { class: "btn btn-primary btn-icon-text" });
  saveBtn.innerHTML = `${ICON_SAVE}<span>Save profile</span>`;
  saveBtn.addEventListener("click", async () => {
    try {
      await updatePreferences({ prose_profile: textarea.value });
      showToast("Profile saved", "success");
      load(container);
    } catch {
      showToast("Failed to save profile", "error");
    }
  });
  section.appendChild(saveBtn);

  return section;
}

function renderInterests(
  prefs: UserPreferences,
  container: HTMLElement
): HTMLElement {
  const section = el("div", { class: "prefs-section" });
  section.appendChild(el("h2", {}, "Interests"));
  section.appendChild(
    el(
      "p",
      { class: "prefs-hint" },
      "Comma-separated topics. These are passed to the scoring model."
    )
  );

  const input = document.createElement("input");
  input.type = "text";
  input.className = "prefs-input";
  input.value = prefs.interests.join(", ");
  input.placeholder = "e.g. rust, distributed systems, linux kernel";
  section.appendChild(input);

  const saveBtn = el("button", { class: "btn btn-primary btn-icon-text" });
  saveBtn.innerHTML = `${ICON_SAVE}<span>Save interests</span>`;
  saveBtn.addEventListener("click", async () => {
    const interests = input.value
      .split(",")
      .map((s) => s.trim())
      .filter((s) => s.length > 0);
    try {
      await updatePreferences({ interests });
      showToast("Interests saved", "success");
      load(container);
    } catch {
      showToast("Failed to save interests", "error");
    }
  });
  section.appendChild(saveBtn);

  return section;
}

function renderTagWeights(
  tags: TagWeight[],
  container: HTMLElement
): HTMLElement {
  const section = el("div", { class: "prefs-section" });
  section.appendChild(el("h2", {}, "Learned Tag Weights"));
  section.appendChild(
    el(
      "p",
      { class: "prefs-hint" },
      "These weights are learned from your feedback. Positive = interesting, negative = not."
    )
  );

  if (tags.length === 0) {
    section.appendChild(
      el(
        "p",
        { class: "prefs-empty" },
        "No tag weights yet. Give feedback on articles to start learning."
      )
    );
    return section;
  }

  let showAll = false;
  const visibleTags = tags.slice(0, DEFAULT_TAG_SHOW);
  const maxWeight = Math.max(...tags.map((t) => Math.abs(t.weight)), 0.01);

  const list = el("div", { class: "tag-weights-list" });

  function renderTags(): void {
    list.innerHTML = "";
    const toShow = showAll ? tags : visibleTags;
    for (const tag of toShow) {
      const row = el("div", { class: "tag-weight-row" });

      const name = el("span", { class: "tag-weight-name" }, tag.name);

      const barContainer = el("div", { class: "tag-weight-bar" });
      const barFill = el("div", {
        class: `tag-weight-bar-fill ${tag.weight >= 0 ? "positive" : "negative"}`,
      });
      const pct = Math.round((Math.abs(tag.weight) / maxWeight) * 100);
      barFill.style.width = `${pct}%`;
      barContainer.appendChild(barFill);

      const weight = el(
        "span",
        {
          class: `tag-weight-value ${tag.weight >= 0 ? "positive" : "negative"}`,
        },
        tag.weight >= 0 ? `+${tag.weight.toFixed(2)}` : tag.weight.toFixed(2)
      );

      const resetBtn = el("button", { class: "btn-reset" });
      resetBtn.innerHTML = ICON_RESET;
      resetBtn.addEventListener("click", async () => {
        try {
          await resetTagWeight(tag.name);
          showToast(`Reset "${tag.name}"`, "success");
          load(container);
        } catch {
          showToast("Failed to reset tag", "error");
        }
      });

      row.appendChild(name);
      row.appendChild(barContainer);
      row.appendChild(weight);
      row.appendChild(resetBtn);
      list.appendChild(row);
    }
  }
  renderTags();
  section.appendChild(list);

  if (tags.length > DEFAULT_TAG_SHOW) {
    const ICON_EXPAND = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m6 9 6 6 6-6"/></svg>`;
    const ICON_COLLAPSE = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m18 15-6-6-6 6"/></svg>`;
    const toggleBtn = el("button", { class: "btn btn-small btn-icon-text" });
    toggleBtn.innerHTML = `${ICON_EXPAND}<span>Show all (${tags.length})</span>`;
    toggleBtn.addEventListener("click", () => {
      showAll = !showAll;
      const icon = showAll ? ICON_COLLAPSE : ICON_EXPAND;
      const label = showAll
        ? `Show top ${DEFAULT_TAG_SHOW}`
        : `Show all (${tags.length})`;
      toggleBtn.innerHTML = `${icon}<span>${label}</span>`;
      renderTags();
    });
    section.appendChild(toggleBtn);
  }

  return section;
}

function renderVersion(prefs: UserPreferences): HTMLElement {
  return el(
    "div",
    { class: "prefs-version" },
    `Profile version: ${prefs.profile_version}`
  );
}
