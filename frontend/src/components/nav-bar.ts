import { getIssues, getVocabularyCandidates } from "../api";
import { navigate } from "../router";
import { state, subscribe } from "../state";
import { el } from "../utils";

let issueCount = 0;
let candidateCount = 0;
let pollTimer: ReturnType<typeof setInterval> | null = null;

const NAV_ICONS: Record<string, string> = {
  feed: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 11a9 9 0 0 1 9 9"/><path d="M4 4a16 16 0 0 1 16 16"/><circle cx="5" cy="19" r="1"/></svg>`,
  sources: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20"/><path d="M2 12h20"/></svg>`,
  stats: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 3v18h18"/><path d="m19 9-5 5-4-4-3 3"/></svg>`,
  tags: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2H2v10l9.29 9.29c.94.94 2.48.94 3.42 0l6.58-6.58c.94-.94.94-2.48 0-3.42L12 2Z"/><path d="M7 7h.01"/></svg>`,
  preferences: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/></svg>`,
};

async function pollIssues(): Promise<void> {
  try {
    const issues = await getIssues();
    issueCount = issues.fetch_errors + issues.scoring_errors;
  } catch {
    // Silently ignore polling errors
  }
  try {
    const candidates = await getVocabularyCandidates();
    candidateCount = candidates.length;
  } catch {
    // Silently ignore
  }
}

function makeNavLink(
  page: { path: string; label: string; title: string; badge?: boolean }
): HTMLElement {
  const link = el("a", {
    href: `#/${page.path}`,
    class: `nav-link${state.currentPage === page.path ? " active" : ""}`,
    title: page.title,
  });
  const icon = NAV_ICONS[page.path];
  if (icon) {
    link.innerHTML = icon;
    link.appendChild(document.createTextNode(` ${page.label}`));
  } else {
    link.textContent = page.label;
  }
  if (page.badge) {
    link.appendChild(el("span", { class: "nav-badge" }));
  }
  link.addEventListener("click", (e) => {
    e.preventDefault();
    navigate(page.path);
  });
  return link;
}

export function NavBar(): HTMLElement {
  const nav = el("nav", { class: "nav-bar" });

  // Start polling for issues
  pollIssues();
  if (!pollTimer) {
    pollTimer = setInterval(pollIssues, 5 * 60 * 1000);
  }

  function render(): void {
    nav.innerHTML = "";

    // Left side: logo + Feed
    const left = el("div", { class: "nav-left" });

    const brand = el("a", { class: "nav-brand", href: "#/feed" });
    brand.innerHTML = `<svg class="nav-logo" width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M12 2L2 7l10 5 10-5-10-5z" fill="currentColor" opacity="0.9"/>
      <path d="M2 17l10 5 10-5" stroke="currentColor" stroke-width="2" fill="none" opacity="0.5"/>
      <path d="M2 12l10 5 10-5" stroke="currentColor" stroke-width="2" fill="none" opacity="0.7"/>
    </svg>`;
    brand.appendChild(document.createTextNode(" Sift"));
    brand.addEventListener("click", (e) => {
      e.preventDefault();
      navigate("feed");
    });
    left.appendChild(brand);

    left.appendChild(
      makeNavLink({
        path: "feed",
        label: "Feed",
        title: "Your curated article inbox",
      })
    );
    nav.appendChild(left);

    // Right side: settings pages
    const right = el("div", { class: "nav-links" });
    const settingsPages = [
      { path: "sources", label: "Sources", title: "Manage RSS feeds" },
      {
        path: "stats",
        label: "Stats",
        badge: issueCount > 0,
        title: "System stats and health",
      },
      {
        path: "tags",
        label: "Tags",
        badge: candidateCount > 0,
        title: "Tag vocabulary management",
      },
      {
        path: "preferences",
        label: "Preferences",
        title: "Profile and scoring preferences",
      },
    ];

    for (const page of settingsPages) {
      right.appendChild(makeNavLink(page));
    }
    nav.appendChild(right);
  }

  subscribe(render);
  render();

  // Re-render when issues change
  setInterval(() => render(), 5 * 60 * 1000);

  return nav;
}
