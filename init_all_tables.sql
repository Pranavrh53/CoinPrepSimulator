-- ============================================================
-- CoinPrep Simulator - Complete Database Init Script
-- Run this ONCE on your remote Aiven MySQL after creating it
-- ============================================================

-- Core Tables
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    crypto_bucks DECIMAL(15, 2) DEFAULT 10000.00,
    tether_balance DECIMAL(20, 8) DEFAULT 0,
    risk_tolerance VARCHAR(30) DEFAULT 'Medium',
    risk_score INT DEFAULT 0,
    verification_code VARCHAR(6),
    verified TINYINT(1) DEFAULT 0,
    achievements TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS wallets (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT,
    name VARCHAR(50) NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS transactions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT,
    wallet_id INT,
    coin_id VARCHAR(50),
    amount DECIMAL(15, 8),
    price DECIMAL(15, 2),
    type ENUM('buy', 'sell', 'limit', 'market', 'stop'),
    sold_price DECIMAL(15, 2),
    buy_transaction_id INT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (wallet_id) REFERENCES wallets(id),
    FOREIGN KEY (buy_transaction_id) REFERENCES transactions(id)
);

CREATE TABLE IF NOT EXISTS watchlist (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT,
    coin_id VARCHAR(50),
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS price_alerts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT,
    user_email VARCHAR(100) NOT NULL,
    coin_id VARCHAR(50),
    target_price DECIMAL(15, 2),
    alert_type ENUM('above', 'below'),
    order_type ENUM('limit', 'market', 'stop'),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notified TINYINT(1) DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS notifications (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT,
    coin_id VARCHAR(50),
    message TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_read TINYINT(1) DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Trading System Tables
CREATE TABLE IF NOT EXISTS trading_pairs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    base_currency VARCHAR(20) NOT NULL,
    quote_currency VARCHAR(20) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY unique_pair (base_currency, quote_currency)
);

CREATE TABLE IF NOT EXISTS orders (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    wallet_id INT NOT NULL,
    pair_id INT,
    base_currency VARCHAR(20) NOT NULL,
    quote_currency VARCHAR(20) NOT NULL,
    order_type ENUM('market', 'limit', 'stop_loss', 'take_profit') NOT NULL,
    side ENUM('buy', 'sell') NOT NULL,
    amount DECIMAL(20, 8) NOT NULL,
    price DECIMAL(20, 8),
    stop_price DECIMAL(20, 8),
    filled_amount DECIMAL(20, 8) DEFAULT 0,
    status ENUM('pending', 'filled', 'cancelled', 'partially_filled') DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    filled_at TIMESTAMP NULL,
    cancelled_at TIMESTAMP NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (wallet_id) REFERENCES wallets(id) ON DELETE CASCADE,
    FOREIGN KEY (pair_id) REFERENCES trading_pairs(id) ON DELETE SET NULL,
    INDEX idx_user_status (user_id, status),
    INDEX idx_pair_status (pair_id, status),
    INDEX idx_order_type (order_type, status)
);

CREATE TABLE IF NOT EXISTS order_fills (
    id INT AUTO_INCREMENT PRIMARY KEY,
    order_id INT NOT NULL,
    user_id INT NOT NULL,
    filled_amount DECIMAL(20, 8) NOT NULL,
    filled_price DECIMAL(20, 8) NOT NULL,
    filled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Risk Assessment Tables
CREATE TABLE IF NOT EXISTS risk_assessments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    financial_score DECIMAL(5,2) NOT NULL,
    knowledge_score DECIMAL(5,2) NOT NULL,
    psychological_score DECIMAL(5,2) NOT NULL,
    goals_score DECIMAL(5,2) NOT NULL,
    total_score DECIMAL(5,2) NOT NULL,
    risk_category VARCHAR(50) NOT NULL,
    responses JSON NOT NULL,
    ai_analysis JSON NOT NULL,
    completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_user_completed (user_id, completed_at DESC)
);

-- AI Learning System Tables
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
    weak_areas TEXT,
    completed_lessons TEXT,
    quiz_scores TEXT,
    total_learning_time INT DEFAULT 0,
    last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS knowledge_documents (
    id INT AUTO_INCREMENT PRIMARY KEY,
    doc_id VARCHAR(100) UNIQUE NOT NULL,
    title VARCHAR(255) NOT NULL,
    category ENUM('crypto_basics', 'trading_strategies', 'risk_management', 'psychology', 'case_studies', 'common_mistakes') NOT NULL,
    subcategory VARCHAR(100),
    file_path VARCHAR(500) NOT NULL,
    content_preview TEXT,
    difficulty ENUM('beginner', 'intermediate', 'advanced') DEFAULT 'beginner',
    word_count INT DEFAULT 0,
    indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_category (category),
    INDEX idx_difficulty (difficulty)
);

CREATE TABLE IF NOT EXISTS ai_conversations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    session_id VARCHAR(100) NOT NULL,
    user_question TEXT NOT NULL,
    user_skill_level ENUM('beginner', 'intermediate', 'advanced'),
    retrieved_docs TEXT,
    ai_response TEXT NOT NULL,
    response_time_ms INT,
    user_rating TINYINT,
    user_feedback TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_user_session (user_id, session_id),
    INDEX idx_created (created_at)
);

CREATE TABLE IF NOT EXISTS learning_progress (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    content_type ENUM('lesson', 'quiz', 'challenge', 'trade_analysis') NOT NULL,
    content_id VARCHAR(100) NOT NULL,
    status ENUM('not_started', 'in_progress', 'completed') DEFAULT 'not_started',
    score INT,
    time_spent INT DEFAULT 0,
    attempts INT DEFAULT 0,
    completed_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE KEY unique_user_content (user_id, content_type, content_id),
    INDEX idx_user_progress (user_id, status)
);

CREATE TABLE IF NOT EXISTS trade_mistakes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    transaction_id INT,
    mistake_type ENUM('no_stop_loss', 'high_leverage', 'emotional_trading', 'poor_timing', 'no_research', 'overtrading', 'fomo', 'panic_sell') NOT NULL,
    severity ENUM('minor', 'moderate', 'severe') DEFAULT 'moderate',
    loss_amount DECIMAL(15, 2),
    ai_analysis TEXT,
    learned TINYINT(1) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (transaction_id) REFERENCES transactions(id) ON DELETE SET NULL,
    INDEX idx_user_mistakes (user_id, learned)
);

CREATE TABLE IF NOT EXISTS daily_challenges (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    challenge_date DATE NOT NULL,
    challenge_type VARCHAR(50) NOT NULL,
    description TEXT NOT NULL,
    target_metric VARCHAR(100),
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

-- Insert default trading pairs
INSERT IGNORE INTO trading_pairs (base_currency, quote_currency, symbol) VALUES
('tether', 'cryptobucks', 'USDT/CB'),
('bitcoin', 'tether', 'BTC/USDT'),
('ethereum', 'tether', 'ETH/USDT'),
('binancecoin', 'tether', 'BNB/USDT'),
('ripple', 'tether', 'XRP/USDT'),
('cardano', 'tether', 'ADA/USDT'),
('solana', 'tether', 'SOL/USDT'),
('polkadot', 'tether', 'DOT/USDT'),
('dogecoin', 'tether', 'DOGE/USDT'),
('avalanche-2', 'tether', 'AVAX/USDT');

-- Insert default knowledge documents
INSERT INTO knowledge_documents (doc_id, title, category, difficulty, file_path, content_preview) VALUES
('crypto_basics_001', 'What is Cryptocurrency?', 'crypto_basics', 'beginner', 'knowledge/lessons/crypto_basics_intro.md', 'Cryptocurrency is a digital or virtual currency...'),
('risk_mgmt_001', 'Stop Loss Orders Explained', 'risk_management', 'beginner', 'knowledge/lessons/stop_loss_guide.md', 'A stop loss is your safety net...'),
('psychology_001', 'Emotional Trading and FOMO', 'psychology', 'intermediate', 'knowledge/psychology/fomo_guide.md', 'Fear Of Missing Out (FOMO) is the biggest killer...')
ON DUPLICATE KEY UPDATE title=title;

-- ============================================================
-- Done! All tables created successfully.
-- ============================================================
