import {
  getPreferences,
  getTagWeights,
  resetTagWeight,
  updatePreferences,
} from "../api";
import type { TagWeight, UserPreferences } from "../types";
import { el } from "../utils";
import { showToast } from "../components/toast";

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
    container.appendChild(renderProfile(prefs, container));
    container.appendChild(renderInterests(prefs, container));
    container.appendChild(renderTagWeights(tags, container));
    container.appendChild(renderVersion(prefs));
  });
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

  const saveBtn = el("button", { class: "btn btn-primary" }, "Save profile");
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

  const saveBtn = el("button", { class: "btn btn-primary" }, "Save interests");
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

  const list = el("div", { class: "tag-weights-list" });
  for (const tag of tags) {
    const row = el("div", { class: "tag-weight-row" });

    const name = el("span", { class: "tag-weight-name" }, tag.name);
    const weight = el(
      "span",
      {
        class: `tag-weight-value ${tag.weight >= 0 ? "positive" : "negative"}`,
      },
      tag.weight >= 0 ? `+${tag.weight.toFixed(2)}` : tag.weight.toFixed(2)
    );

    const resetBtn = el("button", { class: "btn-reset" }, "Reset");
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
    row.appendChild(weight);
    row.appendChild(resetBtn);
    list.appendChild(row);
  }
  section.appendChild(list);

  return section;
}

function renderVersion(prefs: UserPreferences): HTMLElement {
  return el(
    "div",
    { class: "prefs-version" },
    `Profile version: ${prefs.profile_version}`
  );
}
