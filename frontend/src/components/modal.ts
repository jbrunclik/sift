import { el } from "../utils";

const ICON_X = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>`;
const ICON_TRASH = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/></svg>`;
const ICON_CHECK = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>`;

export interface ModalOptions {
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  danger?: boolean;
}

export function showModal(options: ModalOptions): Promise<boolean> {
  return new Promise((resolve) => {
    const overlay = el("div", { class: "modal-overlay" });
    const dialog = el("div", { class: "modal-dialog" });

    // Header
    dialog.appendChild(el("h3", { class: "modal-title" }, options.title));

    // Body
    dialog.appendChild(el("p", { class: "modal-message" }, options.message));

    // Actions
    const actions = el("div", { class: "modal-actions" });

    const cancelBtn = el("button", { class: "modal-btn-cancel" });
    cancelBtn.innerHTML = `${ICON_X}<span>${options.cancelLabel ?? "Cancel"}</span>`;
    cancelBtn.addEventListener("click", () => {
      close(false);
    });

    const confirmIcon = options.danger ? ICON_TRASH : ICON_CHECK;
    const confirmBtn = el("button", {
      class: options.danger
        ? "modal-btn-confirm modal-btn-danger"
        : "modal-btn-confirm",
    });
    confirmBtn.innerHTML = `${confirmIcon}<span>${options.confirmLabel ?? "Confirm"}</span>`;
    confirmBtn.addEventListener("click", () => {
      close(true);
    });

    actions.appendChild(cancelBtn);
    actions.appendChild(confirmBtn);
    dialog.appendChild(actions);
    overlay.appendChild(dialog);

    // Close on overlay click
    overlay.addEventListener("click", (e) => {
      if (e.target === overlay) close(false);
    });

    // Close on Escape
    function onKey(e: KeyboardEvent): void {
      if (e.key === "Escape") close(false);
      if (e.key === "Enter") close(true);
    }
    document.addEventListener("keydown", onKey);

    function close(result: boolean): void {
      document.removeEventListener("keydown", onKey);
      overlay.classList.add("modal-closing");
      dialog.classList.add("modal-closing");
      const handler = (): void => {
        overlay.removeEventListener("animationend", handler);
        overlay.remove();
        resolve(result);
      };
      overlay.addEventListener("animationend", handler);
      // Fallback if animation doesn't fire
      setTimeout(handler, 200);
    }

    document.body.appendChild(overlay);
    // Focus the confirm button for keyboard accessibility
    requestAnimationFrame(() => confirmBtn.focus());
  });
}
