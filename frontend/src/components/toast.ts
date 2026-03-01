import { el } from "../utils";

let toastContainer: HTMLElement | null = null;

function getContainer(): HTMLElement {
  if (!toastContainer) {
    toastContainer = el("div", { class: "toast-container" });
    document.body.appendChild(toastContainer);
  }
  return toastContainer;
}

export function showToast(
  message: string,
  type: "success" | "error" | "info" = "info",
  action?: { label: string; onClick: () => void }
): void {
  const container = getContainer();
  const toast = el("div", { class: `toast toast-${type}` });

  const msgSpan = el("span", { class: "toast-message" }, message);
  toast.appendChild(msgSpan);

  if (action) {
    const actionBtn = el("button", { class: "toast-action" }, action.label);
    actionBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      action.onClick();
      toast.remove();
    });
    toast.appendChild(actionBtn);
  }

  container.appendChild(toast);

  // Auto-remove after 5s
  setTimeout(() => {
    toast.classList.add("toast-exit");
    setTimeout(() => toast.remove(), 300);
  }, 5000);
}
