import { NavBar } from "./components/nav-bar";
import { FeedPage } from "./pages/feed";
import { PreferencesPage } from "./pages/preferences";
import { SourcesPage } from "./pages/sources";
import { StatsPage } from "./pages/stats";
import { TagsPage } from "./pages/tags";
import { initRouter, registerRoute } from "./router";

const app = document.getElementById("app")!;

// Nav bar
app.appendChild(NavBar());

// Page container
const pageContainer = document.createElement("main");
pageContainer.className = "page-container";
app.appendChild(pageContainer);

// Register routes
registerRoute("feed", FeedPage);
registerRoute("sources", SourcesPage);
registerRoute("stats", StatsPage);
registerRoute("tags", TagsPage);
registerRoute("preferences", PreferencesPage);

// Start router
initRouter(pageContainer);
