import { SourceManager } from "../components/source-manager";
import { el } from "../utils";

export function SourcesPage(): HTMLElement {
  const page = el("div", { class: "page page-sources" });
  page.appendChild(el("h1", {}, "Sources"));
  page.appendChild(SourceManager());
  return page;
}
