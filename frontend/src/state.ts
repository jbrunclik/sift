import type { Article, Source } from "./types";

export interface AppState {
  articles: Article[];
  sources: Source[];
  loading: boolean;
  currentPage: string;
  searchQuery: string;
  filterSource: string;
  showUnreadOnly: boolean;
}

type Listener = () => void;

const listeners: Set<Listener> = new Set();

const initialState: AppState = {
  articles: [],
  sources: [],
  loading: false,
  currentPage: "feed",
  searchQuery: "",
  filterSource: "",
  showUnreadOnly: false,
};

export const state: AppState = new Proxy(initialState, {
  set(target, prop, value) {
    (target as unknown as Record<string | symbol, unknown>)[prop] = value;
    listeners.forEach((fn) => fn());
    return true;
  },
});

export function subscribe(fn: Listener): () => void {
  listeners.add(fn);
  return () => listeners.delete(fn);
}
