import { state } from "./state";

type RouteHandler = () => HTMLElement;

const routes: Record<string, RouteHandler> = {};

export function registerRoute(path: string, handler: RouteHandler): void {
  routes[path] = handler;
}

export function navigate(path: string): void {
  window.location.hash = `#/${path}`;
}

export function initRouter(container: HTMLElement): void {
  function render(): void {
    const hash = window.location.hash.slice(2) || "feed";
    state.currentPage = hash;
    const handler = routes[hash];
    if (handler) {
      container.innerHTML = "";
      container.appendChild(handler());
    }
  }

  window.addEventListener("hashchange", render);
  render();
}
