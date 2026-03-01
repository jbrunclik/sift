export interface Article {
  id: number;
  source_id: number;
  external_id: string | null;
  url: string;
  url_normalized: string;
  title: string;
  author: string | null;
  content_snippet: string | null;
  content_full: string | null;
  published_at: string | null;
  fetched_at: string;
  relevance_score: number | null;
  score_explanation: string | null;
  summary: string | null;
  scored_at: string | null;
  language: string;
  image_url: string | null;
  is_read: boolean;
  is_hidden: boolean;
  created_at: string;
  source_name: string | null;
  source_slug: string | null;
  tags: string[];
  feedback: number | null;
}

export interface Source {
  id: number;
  name: string;
  slug: string;
  source_type: string;
  config_json: string;
  enabled: boolean;
  fetch_interval_minutes: number;
  last_fetched_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface Feedback {
  id: number;
  article_id: number;
  rating: number;
  created_at: string;
}

export interface HealthResponse {
  status: string;
  database: string;
  sources_count: number;
  articles_count: number;
  unscored_count: number;
}

export interface StatsResponse {
  total_articles: number;
  scored_articles: number;
  average_score: number | null;
  total_feedback: number;
  positive_feedback: number;
  negative_feedback: number;
  sources: Record<string, unknown>[];
}

export interface UserPreferences {
  prose_profile: string;
  interests: string[];
  tag_weights: Record<string, number>;
  profile_version: number;
}

export interface TagWeight {
  name: string;
  weight: number;
}

export interface FetchLog {
  id: number;
  source_id: number;
  started_at: string;
  finished_at: string | null;
  status: string;
  items_found: number;
  items_new: number;
  error_message: string | null;
  duration_ms: number | null;
}
