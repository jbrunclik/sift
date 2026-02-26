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
  type: "success" | "error" | "info" = "info"
): void {
  const container = getContainer();
  const toast = el("div", { class: `toast toast-${type}` }, message);
  container.appendChild(toast);

  // Auto-remove after 3s
  setTimeout(() => {
    toast.classList.add("toast-exit");
    setTimeout(() => toast.remove(), 300);
  }, 3000);
}
