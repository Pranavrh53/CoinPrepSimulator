-- RAG-Powered AI Learning Assistant Database Schema
-- Run this after database.sql to add learning system tables

USE crypto_tracker;

-- Learning Profiles: Track user skill level and learning patterns
CREATE TABLE IF NOT EXISTS learning_profiles (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT UNIQUE NOT NULL,
    skill_level ENUM('beginner', 'intermediate', 'advanced') DEFAULT 'beginner',
    total_trades INT DEFAULT 0,
    winning_trades INT DEFAULT 0,
    losing_trades INT DEFAULT 0,
    win_rate DECIMAL(5, 2) DEFAULT 0.00,
    avg_profit_per_trade DECIMAL(15, 2) DEFAULT 0.00,
    avg_loss_per_trade DECIMAL(15, 2) DEFAULT 0.00,
    uses_stop_loss_percent DECIMAL(5, 2) DEFAULT 0.00,
    avg_leverage_used DECIMAL(5, 2) DEFAULT 1.00,
    biggest_mistake VARCHAR(100),
    weak_areas TEXT, -- JSON array: ["risk_management", "stop_loss", "psychology"]
    completed_lessons TEXT, -- JSON array of lesson IDs
    quiz_scores TEXT, -- JSON: {"risk_basics": 85, "stop_loss": 70}
    total_learning_time INT DEFAULT 0, -- in minutes
    last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Knowledge Documents: Store metadata about RAG content
CREATE TABLE IF NOT EXISTS knowledge_documents (
    id INT AUTO_INCREMENT PRIMARY KEY,
    doc_id VARCHAR(100) UNIQUE NOT NULL, -- Unique identifier for ChromaDB
    title VARCHAR(255) NOT NULL,
    category ENUM('crypto_basics', 'trading_strategies', 'risk_management', 'psychology', 'case_studies', 'common_mistakes') NOT NULL,
    subcategory VARCHAR(100),
    file_path VARCHAR(500) NOT NULL,
    content_preview TEXT, -- First 200 chars for quick reference
    difficulty ENUM('beginner', 'intermediate', 'advanced') DEFAULT 'beginner',
    word_count INT DEFAULT 0,
    indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_category (category),
    INDEX idx_difficulty (difficulty)
);

-- AI Conversations: Log all AI interactions for improvement
CREATE TABLE IF NOT EXISTS ai_conversations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    session_id VARCHAR(100) NOT NULL,
    user_question TEXT NOT NULL,
    user_skill_level ENUM('beginner', 'intermediate', 'advanced'),
    retrieved_docs TEXT, -- JSON array of doc_ids used
    ai_response TEXT NOT NULL,
    response_time_ms INT, -- Track API performance
    user_rating TINYINT, -- 1-5 stars, optional feedback
    user_feedback TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_user_session (user_id, session_id),
    INDEX idx_created (created_at)
);

-- Learning Progress: Track lesson completion and quiz results
CREATE TABLE IF NOT EXISTS learning_progress (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    content_type ENUM('lesson', 'quiz', 'challenge', 'trade_analysis') NOT NULL,
    content_id VARCHAR(100) NOT NULL, -- lesson ID, quiz ID, etc.
    status ENUM('not_started', 'in_progress', 'completed') DEFAULT 'not_started',
    score INT, -- For quizzes: 0-100
    time_spent INT DEFAULT 0, -- in seconds
    attempts INT DEFAULT 0,
    completed_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE KEY unique_user_content (user_id, content_type, content_id),
    INDEX idx_user_progress (user_id, status)
);

-- Trade Mistakes: Log specific errors for personalized learning
CREATE TABLE IF NOT EXISTS trade_mistakes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    transaction_id INT,
    mistake_type ENUM('no_stop_loss', 'high_leverage', 'emotional_trading', 'poor_timing', 'no_research', 'overtrading', 'fomo', 'panic_sell') NOT NULL,
    severity ENUM('minor', 'moderate', 'severe') DEFAULT 'moderate',
    loss_amount DECIMAL(15, 2),
    ai_analysis TEXT, -- Generated lesson from this mistake
    learned TINYINT(1) DEFAULT 0, -- Did user improve after?
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (transaction_id) REFERENCES transactions(id) ON DELETE SET NULL,
    INDEX idx_user_mistakes (user_id, learned)
);

-- Daily Challenges: Personalized tasks based on weak areas
CREATE TABLE IF NOT EXISTS daily_challenges (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    challenge_date DATE NOT NULL,
    challenge_type VARCHAR(50) NOT NULL, -- "use_stop_loss", "reduce_leverage", etc.
    description TEXT NOT NULL,
    target_metric VARCHAR(100), -- What to measure
    target_value DECIMAL(15, 2),
    current_value DECIMAL(15, 2) DEFAULT 0,
    completed TINYINT(1) DEFAULT 0,
    reward_crypto_bucks DECIMAL(15, 2) DEFAULT 100.00,
    expires_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE KEY unique_user_challenge (user_id, challenge_date, challenge_type),
    INDEX idx_user_active (user_id, completed, expires_at)
);

-- Insert sample knowledge documents (will be populated by RAG indexer)
INSERT INTO knowledge_documents (doc_id, title, category, difficulty, file_path, content_preview) VALUES
('crypto_basics_001', 'What is Cryptocurrency?', 'crypto_basics', 'beginner', 'knowledge/lessons/crypto_basics_intro.md', 'Cryptocurrency is a digital or virtual currency that uses cryptography for security...'),
('risk_mgmt_001', 'Stop Loss Orders Explained', 'risk_management', 'beginner', 'knowledge/lessons/stop_loss_guide.md', 'A stop loss is your safety net. It automatically sells your position when price drops...'),
('psychology_001', 'Emotional Trading and FOMO', 'psychology', 'intermediate', 'knowledge/psychology/fomo_guide.md', 'Fear Of Missing Out (FOMO) is the biggest killer of trading accounts...')
ON DUPLICATE KEY UPDATE title=title;
