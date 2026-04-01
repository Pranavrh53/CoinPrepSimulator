-- Trading Pairs Table
-- Defines available trading pairs (e.g., BTC/USDT, ETH/USDT)
CREATE TABLE IF NOT EXISTS trading_pairs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    base_currency VARCHAR(20) NOT NULL,      -- e.g., 'bitcoin', 'ethereum'
    quote_currency VARCHAR(20) NOT NULL,     -- e.g., 'tether', 'usd'
    symbol VARCHAR(20) NOT NULL,             -- e.g., 'BTC/USDT', 'ETH/USDT'
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY unique_pair (base_currency, quote_currency)
);

-- Orders Table
-- Stores all types of orders: market, limit, stop_loss, take_profit
CREATE TABLE IF NOT EXISTS orders (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    wallet_id INT NOT NULL,
    pair_id INT,                             -- Foreign key to trading_pairs
    base_currency VARCHAR(20) NOT NULL,      -- e.g., 'bitcoin'
    quote_currency VARCHAR(20) NOT NULL,     -- e.g., 'tether'
    order_type ENUM('market', 'limit', 'stop_loss', 'take_profit') NOT NULL,
    side ENUM('buy', 'sell') NOT NULL,       -- buy or sell
    amount DECIMAL(20, 8) NOT NULL,          -- amount of base currency
    price DECIMAL(20, 8),                    -- limit price (NULL for market orders)
    stop_price DECIMAL(20, 8),               -- stop price for stop_loss/take_profit
    filled_amount DECIMAL(20, 8) DEFAULT 0,  -- partially filled amount
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

-- Order Fills Table
-- Tracks execution history of orders
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

-- Insert default trading pairs
-- USDT can be bought with CryptoBucks (special case)
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

-- Add USDT balance column to users (will fail silently if already exists)
-- Check if column exists first
SET @col_exists = 0;
SELECT COUNT(*) INTO @col_exists 
FROM information_schema.columns 
WHERE table_schema = DATABASE() 
AND table_name = 'users' 
AND column_name = 'tether_balance';

SET @query = IF(@col_exists = 0, 
    'ALTER TABLE users ADD COLUMN tether_balance DECIMAL(20, 8) DEFAULT 0', 
    'SELECT "Column tether_balance already exists" AS Info');
PREPARE stmt FROM @query;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Add indexes for better performance (ignore errors if they already exist)
CREATE INDEX idx_orders_pending ON orders(status, order_type, base_currency);
CREATE INDEX idx_orders_user_pending ON orders(user_id, status);
