-- Add learning mode tracking columns to users table
ALTER TABLE users 
    ADD COLUMN tutorial_completed TINYINT(1) DEFAULT 0,
    ADD COLUMN tutorial_skipped TINYINT(1) DEFAULT 0,
    ADD COLUMN lessons_completed TEXT,
    ADD COLUMN show_onboarding TINYINT(1) DEFAULT 1;
