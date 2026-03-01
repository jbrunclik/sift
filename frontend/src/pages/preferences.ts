import {
  getPreferences,
  updatePreferences,
} from "../api";
import type { UserPreferences } from "../types";
import { el } from "../utils";
import { showToast } from "../components/toast";

const ICON_SAVE = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/></svg>`;

const LANGUAGES = [
  { code: "en", label: "\uD83C\uDDEC\uD83C\uDDE7 English" },
  { code: "cs", label: "\uD83C\uDDE8\uD83C\uDDFF Czech" },
];

export function PreferencesPage(): HTMLElement {
  const page = el("div", { class: "page page-preferences" });
  page.appendChild(el("h1", {}, "Preferences"));

  const content = el("div", { class: "preferences-content" });
  page.appendChild(content);

  load(content);
  return page;
}

function load(container: HTMLElement): void {
  getPreferences().then((prefs) => {
    container.innerHTML = "";
    container.appendChild(renderLanguage(prefs, container));
    container.appendChild(renderProfile(prefs, container));
    container.appendChild(renderInterests(prefs, container));
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

function renderVersion(prefs: UserPreferences): HTMLElement {
  return el(
    "div",
    { class: "prefs-version" },
    `Profile version: ${prefs.profile_version}`
  );
}
