# ADR-007: Vanilla TypeScript frontend (no framework)

## Status
Accepted

## Context
The UI is simple: a feed of cards, a source manager, and a stats page. Frameworks like React or Vue add build complexity and bundle size for minimal benefit here.

## Decision
Use Vite + vanilla TypeScript. Component functions return `HTMLElement`. Hash-based SPA router. Proxy-based reactive store.

## Consequences
- Tiny bundle (~10KB JS, ~7KB CSS)
- No framework to keep updated
- Manual DOM manipulation is fine for this scale
- If the UI grows significantly more complex, may reconsider
