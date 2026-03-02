import { getPreferences, postOnboarding } from "../api";
import { showToast } from "./toast";
import { el } from "../utils";

const ONBOARDING_DISMISSED_KEY = "sift-onboarding-dismissed";

/**
 * Check if the user needs onboarding and show the modal if so.
 * Called when the feed page loads.
 */
export async function maybeShowOnboarding(): Promise<void> {
  if (localStorage.getItem(ONBOARDING_DISMISSED_KEY)) return;

  try {
    const prefs = await getPreferences();
    if (prefs.profile_version > 0) return;
  } catch {
    return;
  }

  showOnboardingModal();
}

function showOnboardingModal(): void {
  const overlay = el("div", { class: "modal-overlay onboarding-overlay" });
  const dialog = el("div", { class: "modal-dialog onboarding-dialog" });

  // Header
  dialog.appendChild(
    el("h3", { class: "modal-title" }, "Welcome to Sift")
  );
  dialog.appendChild(
    el(
      "p",
      { class: "modal-message" },
      "Tell Sift what topics interest you. These will seed your preference profile "
        + "so the AI can score articles for you from the start."
    )
  );

  // Interest pills area
  const pillsContainer = el("div", { class: "onboarding-pills" });
  const interests: string[] = [];

  function renderPills(): void {
    pillsContainer.innerHTML = "";
    for (const interest of interests) {
      const pill = el("span", { class: "onboarding-pill" });
      pill.appendChild(document.createTextNode(interest));
      const removeBtn = el("button", { class: "onboarding-pill-x" });
      removeBtn.innerHTML = `<svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>`;
      removeBtn.addEventListener("click", () => {
        const idx = interests.indexOf(interest);
        if (idx >= 0) interests.splice(idx, 1);
        renderPills();
      });
      pill.appendChild(removeBtn);
      pillsContainer.appendChild(pill);
    }
  }

  dialog.appendChild(pillsContainer);

  // Input row
  const inputRow = el("div", { class: "onboarding-input-row" });
  const input = document.createElement("input");
  input.type = "text";
  input.className = "prefs-input onboarding-input";
  input.placeholder = "Type a topic and press Enter (e.g. rust, machine learning, security)";

  function addInterest(): void {
    const value = input.value.trim().toLowerCase();
    if (value && !interests.includes(value)) {
      interests.push(value);
      renderPills();
    }
    input.value = "";
  }

  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      addInterest();
    }
  });
  inputRow.appendChild(input);
  dialog.appendChild(inputRow);

  // Actions
  const actions = el("div", { class: "modal-actions" });

  const skipBtn = el("button", { class: "modal-btn-cancel" }, "Skip");
  skipBtn.addEventListener("click", () => close(false));

  const saveBtn = el("button", { class: "modal-btn-confirm" });
  saveBtn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg><span>Get Started</span>`;
  saveBtn.addEventListener("click", () => close(true));

  actions.appendChild(skipBtn);
  actions.appendChild(saveBtn);
  dialog.appendChild(actions);

  overlay.appendChild(dialog);

  // Close on overlay click
  overlay.addEventListener("click", (e) => {
    if (e.target === overlay) close(false);
  });

  function onKey(e: KeyboardEvent): void {
    if (e.key === "Escape") close(false);
  }
  document.addEventListener("keydown", onKey);

  async function close(submit: boolean): Promise<void> {
    document.removeEventListener("keydown", onKey);

    if (submit && interests.length > 0) {
      try {
        const result = await postOnboarding(interests);
        showToast(
          `Profile seeded with ${result.tags_seeded} topic${result.tags_seeded !== 1 ? "s" : ""}`,
          "success"
        );
      } catch {
        showToast("Failed to save preferences", "error");
      }
    }

    // Remember dismissal so we don't show again
    localStorage.setItem(ONBOARDING_DISMISSED_KEY, "true");

    overlay.classList.add("modal-closing");
    dialog.classList.add("modal-closing");
    const handler = (): void => {
      overlay.removeEventListener("animationend", handler);
      overlay.remove();
    };
    overlay.addEventListener("animationend", handler);
    setTimeout(handler, 200);
  }

  document.body.appendChild(overlay);
  requestAnimationFrame(() => input.focus());
}
