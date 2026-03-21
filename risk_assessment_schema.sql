-- Enhanced Risk Assessment Database Schema
-- Adds comprehensive risk assessment table

-- Create risk_assessments table
CREATE TABLE IF NOT EXISTS risk_assessments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    
    -- Individual test scores (percentage)
    financial_score DECIMAL(5,2) NOT NULL,
    knowledge_score DECIMAL(5,2) NOT NULL,
    psychological_score DECIMAL(5,2) NOT NULL,
    goals_score DECIMAL(5,2) NOT NULL,
    
    -- Overall weighted score
    total_score DECIMAL(5,2) NOT NULL,
    risk_category VARCHAR(50) NOT NULL,
    
    -- Raw responses (JSON)
    responses JSON NOT NULL,
    
    -- AI analysis results (JSON)
    ai_analysis JSON NOT NULL,
    
    -- Timestamps
    completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Foreign key
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_user_completed (user_id, completed_at DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Update users table to include latest risk assessment info (MySQL doesn't support IF NOT EXISTS in ALTER TABLE)
-- Run these separately if columns don't exist
-- ALTER TABLE users ADD COLUMN last_assessment_id INT NULL;
-- ALTER TABLE users ADD COLUMN last_assessment_date TIMESTAMP NULL;

-- Create view for quick access to user risk profiles
CREATE OR REPLACE VIEW user_risk_profiles AS
SELECT 
    u.id AS user_id,
    u.username,
    u.email,
    u.risk_tolerance,
    u.risk_score,
    ra.id AS assessment_id,
    ra.financial_score,
    ra.knowledge_score,
    ra.psychological_score,
    ra.goals_score,
    ra.total_score AS detailed_score,
    ra.risk_category,
    ra.completed_at AS assessment_date,
    DATEDIFF(CURRENT_TIMESTAMP, ra.completed_at) AS days_since_assessment
FROM users u
LEFT JOIN risk_assessments ra ON u.id = ra.user_id
WHERE ra.id = (
    SELECT MAX(id) FROM risk_assessments WHERE user_id = u.id
)
OR ra.id IS NULL;

-- Sample queries for testing

-- Get latest assessment for a user
-- SELECT * FROM risk_assessments WHERE user_id = ? ORDER BY completed_at DESC LIMIT 1;

-- Get user's assessment history
-- SELECT id, total_score, risk_category, completed_at 
-- FROM risk_assessments 
-- WHERE user_id = ? 
-- ORDER BY completed_at DESC;

-- Get all users with their latest risk profiles
-- SELECT * FROM user_risk_profiles;

-- Find users who haven't taken assessment recently
-- SELECT user_id, username, email, days_since_assessment
-- FROM user_risk_profiles
-- WHERE days_since_assessment > 180 OR days_since_assessment IS NULL;

-- Get score distribution
-- SELECT 
--     risk_category,
--     COUNT(*) as count,
--     AVG(total_score) as avg_score,
--     MIN(total_score) as min_score,
--     MAX(total_score) as max_score
-- FROM risk_assessments
-- GROUP BY risk_category
-- ORDER BY avg_score;
