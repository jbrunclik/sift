-- Add summary language preference to user_profile
ALTER TABLE user_profile ADD COLUMN summary_language TEXT NOT NULL DEFAULT 'en';
