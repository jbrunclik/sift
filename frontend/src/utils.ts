export function el<K extends keyof HTMLElementTagNameMap>(
  tag: K,
  attrs?: Record<string, string>,
  ...children: (Node | string)[]
): HTMLElementTagNameMap[K] {
  const element = document.createElement(tag);
  if (attrs) {
    for (const [key, value] of Object.entries(attrs)) {
      if (key === "class") {
        element.className = value;
      } else {
        element.setAttribute(key, value);
      }
    }
  }
  for (const child of children) {
    if (typeof child === "string") {
      element.appendChild(document.createTextNode(child));
    } else {
      element.appendChild(child);
    }
  }
  return element;
}

export function formatDate(dateStr: string | null): string {
  if (!dateStr) return "";
  // SQLite stores UTC dates without timezone suffix — ensure JS parses as UTC
  const normalized = dateStr.endsWith("Z") || dateStr.includes("+") ? dateStr : dateStr + "Z";
  const d = new Date(normalized);
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();

  // Future dates
  if (diffMs < 0) {
    const futureMins = Math.floor(-diffMs / 60000);
    if (futureMins < 1) return "now";
    if (futureMins < 60) return `in ${futureMins}m`;
    const futureHrs = Math.floor(futureMins / 60);
    if (futureHrs < 24) return `in ${futureHrs}h`;
    const futureDays = Math.floor(futureHrs / 24);
    return `in ${futureDays}d`;
  }

  // Past dates
  const diffMin = Math.floor(diffMs / 60000);
  const diffHr = Math.floor(diffMin / 60);
  const diffDay = Math.floor(diffHr / 24);

  if (diffMin < 1) return "just now";
  if (diffMin < 60) return `${diffMin}m ago`;
  if (diffHr < 24) return `${diffHr}h ago`;
  if (diffDay < 7) return `${diffDay}d ago`;
  return d.toLocaleDateString();
}

export function debounce<T extends (...args: unknown[]) => void>(
  fn: T,
  ms: number
): (...args: Parameters<T>) => void {
  let timer: ReturnType<typeof setTimeout>;
  return (...args: Parameters<T>) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), ms);
  };
}

export function truncate(str: string, maxLen: number): string {
  if (str.length <= maxLen) return str;
  return str.slice(0, maxLen - 1) + "\u2026";
}

export function scoreColor(score: number | null): string {
  if (score === null) return "var(--color-muted)";
  if (score >= 7) return "var(--color-score-high)";
  if (score >= 4) return "var(--color-score-mid)";
  return "var(--color-score-low)";
}
