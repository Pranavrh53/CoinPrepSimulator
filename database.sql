CREATE DATABASE IF NOT EXISTS crypto_tracker;
USE crypto_tracker;

CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    crypto_bucks DECIMAL(15, 2) DEFAULT 10000.00,
    risk_tolerance VARCHAR(20) DEFAULT 'Medium',
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
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (wallet_id) REFERENCES wallets(id)
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
    coin_id VARCHAR(50),
    target_price DECIMAL(15, 2),
    alert_type ENUM('above', 'below'),
    order_type ENUM('limit', 'market', 'stop'),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Insert a default user
INSERT INTO users (username, email, password) VALUES 
('admin', 'admin@example.com', 'hashedpassword123');  -- Use bcrypt.hash('password123') in app for real use

-- Insert wallets for the default user (id = 1)
INSERT INTO wallets (user_id, name) VALUES (1, 'Default Wallet'), (1, 'Altcoin Wallet')
ON DUPLICATE KEY UPDATE name=name;