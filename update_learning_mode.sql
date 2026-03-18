-- Add learning mode tracking columns to users table
ALTER TABLE users ADD COLUMN IF NOT EXISTS tutorial_completed BOOLEAN DEFAULT FALSE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS tutorial_skipped BOOLEAN DEFAULT FALSE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS lessons_completed TEXT DEFAULT '[]';
ALTER TABLE users ADD COLUMN IF NOT EXISTS show_onboarding BOOLEAN DEFAULT TRUE;
