-- Create the database (if not already created)
CREATE DATABASE IF NOT EXISTS coinprep;
USE coinprep;

-- Table for users with fake currency balance
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(80) NOT NULL UNIQUE,
    password VARCHAR(120) NOT NULL,
    balance DECIMAL(15, 2) DEFAULT 10000.00 -- Fake currency balance starting at 10,000
);

-- Table for stocks with dynamic pricing
CREATE TABLE IF NOT EXISTS stocks (
    id INT AUTO_INCREMENT PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL UNIQUE,
    name VARCHAR(100) NOT NULL,
    current_price DECIMAL(15, 2) NOT NULL,
    last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Table for tracking transactions (buy/sell)
CREATE TABLE IF NOT EXISTS transactions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    stock_id INT NOT NULL,
    quantity INT NOT NULL,
    price_per_share DECIMAL(15, 2) NOT NULL,
    transaction_type ENUM('buy', 'sell') NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (stock_id) REFERENCES stocks(id)
);

-- Insert initial stock data for testing
INSERT INTO stocks (symbol, name, current_price) VALUES
('AAPL', 'Apple Inc.', 150.00),
('GOOGL', 'Google LLC', 2500.00),
('TSLA', 'Tesla Inc.', 700.00);

-- Optional: Insert a test user
INSERT INTO users (username, password) VALUES
('testuser', 'testpass'); -- Use proper hashing in production