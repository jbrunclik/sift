import { navigate } from "../router";
import { state, subscribe } from "../state";
import { el } from "../utils";

export function NavBar(): HTMLElement {
  const nav = el("nav", { class: "nav-bar" });

  function render(): void {
    nav.innerHTML = "";
    const brand = el("a", { class: "nav-brand", href: "#/feed" }, "Sift");
    brand.addEventListener("click", (e) => {
      e.preventDefault();
      navigate("feed");
    });
    nav.appendChild(brand);

    const links = el("div", { class: "nav-links" });
    const pages = [
      { path: "feed", label: "Feed" },
      { path: "sources", label: "Sources" },
      { path: "stats", label: "Stats" },
    ];

    for (const page of pages) {
      const link = el(
        "a",
        {
          href: `#/${page.path}`,
          class: `nav-link${state.currentPage === page.path ? " active" : ""}`,
        },
        page.label
      );
      link.addEventListener("click", (e) => {
        e.preventDefault();
        navigate(page.path);
      });
      links.appendChild(link);
    }
    nav.appendChild(links);
  }

  subscribe(render);
  render();
  return nav;
}
