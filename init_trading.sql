-- Quick Start: Initialize Trading Simulator
-- Run this after trading_schema.sql to set up the system

-- Verify trading pairs are created
SELECT * FROM trading_pairs;

-- Add USDT balance column if not exists (backup command)
ALTER TABLE users ADD COLUMN IF NOT EXISTS tether_balance DECIMAL(20, 8) DEFAULT 0;

-- Optional: Give existing users some starting USDT (for testing)
-- Uncomment if you want to give all users 1000 USDT to start
-- UPDATE users SET tether_balance = 1000 WHERE tether_balance = 0;

-- Verify tables exist
SHOW TABLES LIKE '%orders%';
SHOW TABLES LIKE '%trading_pairs%';

-- Check structure
DESCRIBE orders;
DESCRIBE trading_pairs;
DESCRIBE order_fills;

-- Sample queries to test the system

-- 1. View all available trading pairs
SELECT id, symbol, base_currency, quote_currency, is_active 
FROM trading_pairs 
WHERE is_active = TRUE;

-- 2. Check user balances
SELECT id, username, crypto_bucks, tether_balance 
FROM users 
LIMIT 10;

-- 3. View pending orders
SELECT o.id, u.username, o.base_currency, o.quote_currency, 
       o.order_type, o.side, o.amount, o.price, o.stop_price
FROM orders o
JOIN users u ON o.user_id = u.id
WHERE o.status = 'pending'
ORDER BY o.created_at DESC;

-- 4. Order book for BTC/USDT
SELECT 
    side,
    price as price_level,
    SUM(amount - filled_amount) as total_amount,
    COUNT(*) as num_orders
FROM orders
WHERE base_currency = 'bitcoin' 
  AND quote_currency = 'tether'
  AND status = 'pending'
  AND order_type = 'limit'
GROUP BY side, price
ORDER BY 
    CASE WHEN side = 'buy' THEN price END DESC,
    CASE WHEN side = 'sell' THEN price END ASC;

-- 5. User trade history with order types
SELECT 
    u.username,
    t.coin_id,
    t.type,
    t.amount,
    t.price,
    t.sold_price,
    (COALESCE(t.sold_price, 0) - t.price) * t.amount as profit_loss,
    t.timestamp
FROM transactions t
JOIN users u ON t.user_id = u.id
WHERE u.id = 1  -- Change to your user ID
ORDER BY t.timestamp DESC
LIMIT 20;

-- 6. Order execution statistics
SELECT 
    order_type,
    side,
    COUNT(*) as total_orders,
    SUM(CASE WHEN status = 'filled' THEN 1 ELSE 0 END) as filled,
    SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
    SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END) as cancelled
FROM orders
GROUP BY order_type, side;

-- 7. Most active trading pairs
SELECT 
    tp.symbol,
    COUNT(*) as order_count,
    SUM(o.amount) as total_volume
FROM orders o
JOIN trading_pairs tp ON o.pair_id = tp.id
WHERE o.status IN ('filled', 'pending')
GROUP BY tp.symbol
ORDER BY order_count DESC;

-- Cleanup commands (use with caution!)

-- Remove all test orders (if starting fresh)
-- DELETE FROM orders WHERE user_id IN (SELECT id FROM users WHERE username LIKE 'test%');

-- Reset all pending orders to cancelled (emergency)
-- UPDATE orders SET status = 'cancelled', cancelled_at = NOW() WHERE status = 'pending';

-- Clear order fills
-- DELETE FROM order_fills WHERE order_id IN (SELECT id FROM orders WHERE status = 'cancelled');
