import { debounce, el } from "../utils";

export function SearchBar(
  onSearch: (query: string) => void
): HTMLElement {
  const container = el("div", { class: "search-bar" });
  const input = el("input", {
    type: "text",
    placeholder: "Search articles...",
    class: "search-input",
  });

  const debouncedSearch = debounce((...args: unknown[]) => {
    onSearch(args[0] as string);
  }, 300);

  input.addEventListener("input", () => {
    debouncedSearch(input.value);
  });

  container.appendChild(input);
  return container;
}
