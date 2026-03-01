import type {
  Article,
  CostEntry,
  Feedback,
  FetchLog,
  HealthResponse,
  IssuesResponse,
  Source,
  StatsResponse,
  TagWeight,
  UserPreferences,
} from "./types";

const BASE = "/api";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status}: ${body}`);
  }
  return res.json();
}

// Articles
export function getArticles(params?: {
  limit?: number;
  offset?: number;
  min_score?: number;
  source_slug?: string;
  search?: string;
  show_all?: boolean;
  unread?: boolean;
}): Promise<Article[]> {
  const qs = new URLSearchParams();
  if (params?.limit != null) qs.set("limit", String(params.limit));
  if (params?.offset != null) qs.set("offset", String(params.offset));
  if (params?.min_score != null) qs.set("min_score", String(params.min_score));
  if (params?.source_slug) qs.set("source_slug", params.source_slug);
  if (params?.search) qs.set("search", params.search);
  if (params?.show_all) qs.set("show_all", "true");
  if (params?.unread) qs.set("unread", "true");
  const q = qs.toString();
  return request<Article[]>(`/articles${q ? `?${q}` : ""}`);
}

export function getArticle(id: number): Promise<Article> {
  return request<Article>(`/articles/${id}`);
}

export function markRead(id: number): Promise<void> {
  return request(`/articles/${id}/read`, { method: "POST" });
}

export function markUnread(id: number): Promise<void> {
  return request(`/articles/${id}/unread`, { method: "POST" });
}

export function hideArticle(id: number): Promise<void> {
  return request(`/articles/${id}/hide`, { method: "POST" });
}

// Sources
export function getSources(): Promise<Source[]> {
  return request<Source[]>("/sources");
}

export function createSource(source: {
  name: string;
  slug: string;
  source_type: string;
  config_json: string;
  category?: string;
}): Promise<Source> {
  return request<Source>("/sources", {
    method: "POST",
    body: JSON.stringify(source),
  });
}

export function updateSource(
  id: number,
  data: { category?: string; name?: string; enabled?: boolean; fetch_interval_minutes?: number }
): Promise<Source> {
  return request<Source>(`/sources/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export function deleteSource(id: number): Promise<void> {
  return request(`/sources/${id}`, { method: "DELETE" });
}

export function triggerFetch(id: number): Promise<FetchLog> {
  return request<FetchLog>(`/sources/${id}/fetch`, { method: "POST" });
}

// Feedback
export function sendFeedback(
  articleId: number,
  rating: number
): Promise<Feedback> {
  return request<Feedback>("/feedback", {
    method: "POST",
    body: JSON.stringify({ article_id: articleId, rating }),
  });
}

// Preferences
export function getPreferences(): Promise<UserPreferences> {
  return request<UserPreferences>("/preferences");
}

export function updatePreferences(
  data: { prose_profile?: string; interests?: string[]; summary_language?: string }
): Promise<UserPreferences> {
  return request<UserPreferences>("/preferences", {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export function getTagWeights(): Promise<TagWeight[]> {
  return request<TagWeight[]>("/preferences/tags");
}

export function resetTagWeight(name: string): Promise<void> {
  return request(`/preferences/tags/${encodeURIComponent(name)}`, {
    method: "DELETE",
  });
}

// Health & Stats
export function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>("/health");
}

export function getStats(): Promise<StatsResponse> {
  return request<StatsResponse>("/stats");
}

export function getIssues(): Promise<IssuesResponse> {
  return request<IssuesResponse>("/stats/issues");
}

export function getCosts(): Promise<CostEntry[]> {
  return request<CostEntry[]>("/stats/costs");
}

// Job triggers
export function triggerJob(
  job: "fetch" | "score" | "cleanup" | "retry-scoring" | "force-retry-scoring"
): Promise<{ status: string; message: string }> {
  return request(`/jobs/${job}`, { method: "POST" });
}

export function getIssueDetails(): Promise<{
  fetch_errors: number;
  scoring_failures: number;
  scoring_retryable: number;
  unscored: number;
}> {
  return request("/stats/issue-details");
}

export function getScoringFailures(): Promise<
  { id: number; title: string; url: string; source_name: string; score_attempts: number; scored_at: string | null; error: string | null }[]
> {
  return request("/stats/scoring-failures");
}
