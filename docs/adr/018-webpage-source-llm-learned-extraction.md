# ADR-018: Web page source with LLM-learned extraction rules

## Status
Accepted

## Context
Sift only supports RSS feeds as sources. Many useful content sources (e.g. municipal document listings, news pages without RSS) don't provide structured feeds. We need a generic "web page" source type that can extract news items from arbitrary HTML pages.

Two approaches were considered:
1. **Per-fetch LLM extraction**: Send the full HTML to Gemini on every fetch and ask it to extract articles. Simple but expensive and slow.
2. **Learn-once, reuse**: On the first fetch, ask Gemini to generate CSS selectors and extraction rules. Store the rules. On subsequent fetches, use BeautifulSoup with the stored rules — no LLM call needed.

## Decision
Use the **learn-once approach** (option 2). On first fetch, clean the HTML (remove scripts/styles/SVGs, truncate to ~20K chars) and send it to Gemini with a structured output schema. The LLM returns CSS selectors for the repeating item container, title, URL, date, and description. These rules are stored in the source's `config_json` as `extraction_rules`.

Key design choices:
- **Pydantic structured output** (`ExtractionRules` schema) ensures the LLM returns well-formed selectors that can be validated and serialized
- **Automatic re-learning**: if extraction returns 0 items and the rules are >24h old, re-learn automatically (handles page structure changes)
- **Cost tracking**: LLM rule-learning calls are logged to `scoring_logs` with `batch_size=0` to distinguish from scoring calls
- **`source_id` parameter on `BaseSource`**: the webpage plugin needs to write learned rules back to the DB, requiring knowledge of its own source ID
- **Relative URL resolution**: `urljoin(base_url, href)` handles both relative and absolute URLs in extracted items
- **Date format learning**: the LLM provides a `strftime` format string alongside the date selector, enabling correct parsing of locale-specific formats (e.g. `%d.%m.%Y` for Czech dates)

## Consequences
- Adds a new source type `webpage` alongside `rss`, extending Sift beyond RSS-only sources
- First fetch of a new web page source incurs one Gemini API call (~$0.001) to learn rules
- Subsequent fetches are pure HTML parsing with BeautifulSoup — fast and free
- Rules may break if the source page changes structure; automatic re-learning mitigates this
- The `source_id` parameter added to `BaseSource.__init__()` is optional and backward-compatible
- Frontend gains a source type selector (RSS Feed / Web Page) with appropriate UI badges
