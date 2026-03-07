import type {
  Article,
  AuthIssueEntry,
  CandidateTag,
  CostEntry,
  Feedback,
  FetchLog,
  HealthResponse,
  IssuesResponse,
  OnboardingResponse,
  PlatformInfo,
  Source,
  StatsResponse,
  TagQualityEntry,
  TagWeight,
  TestAuthResponse,
  UserPreferences,
  VocabularyTag,
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
  data: { category?: string; name?: string; enabled?: boolean; fetch_interval_minutes?: number; config_json?: string; starred?: boolean }
): Promise<Source> {
  return request<Source>(`/sources/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export function deleteSource(id: number): Promise<void> {
  return request(`/sources/${id}`, { method: "DELETE" });
}

export function getPlatforms(): Promise<PlatformInfo[]> {
  return request<PlatformInfo[]>("/sources/platforms");
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
  auth_truncations: number;
}> {
  return request("/stats/issue-details");
}

export function getScoringFailures(): Promise<
  { id: number; title: string; url: string; source_name: string; score_attempts: number; scored_at: string | null; error: string | null }[]
> {
  return request("/stats/scoring-failures");
}

// Vocabulary
export function getVocabulary(): Promise<VocabularyTag[]> {
  return request<VocabularyTag[]>("/preferences/vocabulary");
}

export function addVocabularyTag(name: string): Promise<VocabularyTag> {
  return request<VocabularyTag>("/preferences/vocabulary", {
    method: "POST",
    body: JSON.stringify({ name }),
  });
}

export function removeVocabularyTag(tagId: number): Promise<void> {
  return request(`/preferences/vocabulary/${tagId}`, { method: "DELETE" });
}

export function mergeVocabularyTags(
  sourceId: number,
  targetId: number
): Promise<void> {
  return request("/preferences/vocabulary/merge", {
    method: "POST",
    body: JSON.stringify({ source_id: sourceId, target_id: targetId }),
  });
}

export function getVocabularyCandidates(): Promise<CandidateTag[]> {
  return request<CandidateTag[]>("/preferences/vocabulary/candidates");
}

export function approveCandidate(tagId: number): Promise<void> {
  return request(`/preferences/vocabulary/candidates/${tagId}/approve`, {
    method: "POST",
  });
}

export function rejectCandidate(tagId: number): Promise<void> {
  return request(`/preferences/vocabulary/candidates/${tagId}`, {
    method: "DELETE",
  });
}

// Auth testing
export function testSourceAuth(id: number): Promise<TestAuthResponse> {
  return request<TestAuthResponse>(`/sources/${id}/test-auth`, { method: "POST" });
}

export function getAuthIssues(): Promise<AuthIssueEntry[]> {
  return request<AuthIssueEntry[]>("/stats/auth-issues");
}

// Tag quality
export function getTagQuality(): Promise<TagQualityEntry[]> {
  return request<TagQualityEntry[]>("/preferences/vocabulary/quality");
}

// Onboarding
export function postOnboarding(
  interests: string[],
  prose_profile?: string
): Promise<OnboardingResponse> {
  return request<OnboardingResponse>("/onboarding", {
    method: "POST",
    body: JSON.stringify({ interests, prose_profile: prose_profile ?? "" }),
  });
}
