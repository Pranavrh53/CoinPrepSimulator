# Trading Simulator Features - Implementation Guide

## Overview
Your crypto tracker is now a **comprehensive trading simulator** with professional features that teach users about trading before they use real money.

---

## 🔧 Setup Instructions

### 1. Run the Database Schema
Execute the new schema to create the necessary tables:

```bash
mysql -u root -p crypto_tracker < trading_schema.sql
```

This creates:
- `trading_pairs` - Defines available trading pairs (BTC/USDT, ETH/USDT, etc.)
- `orders` - Stores all orders (market, limit, stop_loss, take_profit)
- `order_fills` - Tracks order execution history
- Adds `tether_balance` column to users table

---

## 💰 Currency Flow (How It Works)

### Starting Point: CryptoBucks
- Users start with **CryptoBucks** (virtual currency)
- CryptoBucks balance: `users.crypto_bucks`

### Step 1: Buy USDT (Tether)
- Users convert CryptoBucks → USDT at market price
- USDT balance: `users.tether_balance`
- Trading pair: **USDT/CB** (CryptoBucks)

### Step 2: Trade Crypto with USDT
- Use USDT to buy/sell cryptocurrencies
- Trading pairs: **BTC/USDT**, **ETH/USDT**, **BNB/USDT**, etc.
- Transactions stored in `transactions` table

---

## 📊 Order Types Explained

### 1. **Market Order** ⚡
- **Executes immediately** at current market price
- Best for: Quick entry/exit
- Example: "Buy 0.5 BTC right now at $42,000"

**How it works in code:**
- When `order_type='market'` → Executes immediately in `/trade` route
- Debits quote currency (USDT or CryptoBucks)
- Credits base currency to portfolio

### 2. **Limit Order** 📍
- **Waits until price reaches your target**
- Stored as pending in `orders` table
- Background scheduler checks every 5 minutes

**Buy Limit Example:**
- "Buy 0.5 BTC when price drops to $40,000"
- Only executes if price ≤ $40,000

**Sell Limit Example:**
- "Sell 0.5 BTC when price rises to $45,000"
- Only executes if price ≥ $45,000

### 3. **Stop Loss** 🛑
- **Automatic sell when price drops**
- Protects against losses
- Example: "Sell if BTC drops to $39,000"

**How it works:**
- User owns BTC bought at $42,000
- Sets stop loss at $39,000
- If price drops to $39,000 → Auto-sells
- Limits loss to $3,000 per BTC

### 4. **Take Profit** 🎯
- **Automatic sell when target profit reached**
- Locks in gains
- Example: "Sell when BTC reaches $50,000"

**How it works:**
- User owns BTC bought at $42,000
- Sets take profit at $50,000
- If price rises to $50,000 → Auto-sells
- Captures $8,000 profit per BTC

---

## 🔄 Order Execution Flow

### Market Orders (Immediate)
```
User submits form → /trade route
  ↓
Validate balances
  ↓
Execute immediately
  ↓
Update balances & transactions
  ↓
Flash success message
```

### Limit/Stop Orders (Delayed)
```
User submits form → /trade route
  ↓
Create pending order in `orders` table
  ↓
Background scheduler (every 5 min)
  ↓
Check current prices
  ↓
If conditions met → execute_order()
  ↓
Update balances, transactions, order status
```

---

## 🌐 New API Endpoints

### `/orders` (GET)
- View all open orders
- View order history
- Template: `combined.html` section='orders'

### `/cancel_order/<order_id>` (POST)
- Cancel a pending order
- Only works for `status='pending'`

### `/trading_pairs` (GET)
- Returns JSON list of available pairs
- Used for dropdown menus

### `/api/orderbook/<pair>` (GET)
- Shows pending buy/sell orders
- Example: `/api/orderbook/bitcoin-tether`
- Returns:
  ```json
  {
    "pair": "bitcoin/tether",
    "bids": [{"price_level": 41000, "total_amount": 2.5}],
    "asks": [{"price_level": 42000, "total_amount": 1.8}],
    "timestamp": "2026-01-17T..."
  }
  ```

---

## 📈 Enhanced Market Data

### Live Market Page Now Shows:
- ✅ Current Price
- ✅ 24h High (`coin['high_24h']`)
- ✅ 24h Low (`coin['low_24h']`)
- ✅ 24h Volume (`coin['total_volume']`)
- ✅ Price Change % (existing)
- ✅ CryptoBucks balance
- ✅ USDT balance

All data comes from CoinGecko API.

---

## 🎓 Educational Features (Recommended Additions)

### Order Type Tooltips
Add to your trading form:
```html
<span class="tooltip">ℹ️
  <span class="tooltiptext">
    Market Order: Executes immediately at current price
  </span>
</span>
```

### Risk Warnings
When placing stop loss:
```html
<div class="warning">
  ⚠️ Tip: Place stop loss 5-10% below entry price for balanced risk
</div>
```

### Tutorial Mode
Create first-time walkthrough:
1. "Welcome! You have 10,000 CryptoBucks to start"
2. "First, buy some USDT (stablecoin) to trade with"
3. "Now use USDT to buy Bitcoin"
4. "Set a stop loss to protect your investment"

---

## 📋 Example User Journey

### Complete Trading Cycle:

**Day 1: Setup**
1. User registers → Gets 10,000 CryptoBucks
2. Buys 1,000 USDT @ $1 = 1,000 CryptoBucks spent
3. Balance: 9,000 CryptoBucks + 1,000 USDT

**Day 2: Buy BTC**
4. Market Order: Buy 0.5 BTC @ $40,000 = 800 USDT
5. Balance: 9,000 CB + 200 USDT + 0.5 BTC

**Day 3: Risk Management**
6. Stop Loss: Sell 0.5 BTC if price drops to $38,000
7. Take Profit: Sell 0.5 BTC if price rises to $45,000

**Day 4: Price Rises → Take Profit Triggered**
8. BTC reaches $45,000 → Auto-sells
9. Balance: 9,000 CB + 1,025 USDT + 0 BTC
10. **Profit: 225 USDT ($225)**

---

## 🔍 Database Queries for Debugging

### Check Pending Orders
```sql
SELECT * FROM orders WHERE status = 'pending';
```

### View User Balances
```sql
SELECT username, crypto_bucks, tether_balance FROM users;
```

### See Order Book for BTC/USDT
```sql
SELECT side, price, SUM(amount) as total
FROM orders
WHERE base_currency = 'bitcoin' 
  AND quote_currency = 'tether'
  AND status = 'pending'
  AND order_type = 'limit'
GROUP BY side, price
ORDER BY price;
```

### User Trade History
```sql
SELECT t.*, o.order_type, o.side
FROM transactions t
LEFT JOIN orders o ON t.user_id = o.user_id
WHERE t.user_id = 1
ORDER BY t.timestamp DESC;
```

---

## 🎯 Next Steps for Your UI

### 1. Update Trading Form
Add order type selector:
```html
<select name="order_type">
  <option value="market">Market (Instant)</option>
  <option value="limit">Limit (Wait for Price)</option>
  <option value="stop_loss">Stop Loss (Protect)</option>
  <option value="take_profit">Take Profit (Lock Gains)</option>
</select>

<input type="number" name="limit_price" placeholder="Target Price" />
<input type="number" name="stop_price" placeholder="Stop Price" />
```

### 2. Display Order Book
Create chart or table showing:
```
SELL ORDERS (Asks)
$42,500 | ████████ 1.2 BTC
$42,200 | ████ 0.8 BTC
$42,000 | ██ 0.5 BTC
------------------------
CURRENT PRICE: $41,800
------------------------
BUY ORDERS (Bids)
$41,500 | ████ 0.9 BTC
$41,200 | ████████ 1.5 BTC
$41,000 | ██████ 1.1 BTC
```

### 3. Show User Balances
On dashboard:
```html
<div class="balances">
  <div>CryptoBucks: ${{ user.crypto_bucks }}</div>
  <div>USDT: ${{ user.tether_balance }}</div>
  <div>Total Portfolio: ${{ total_value }}</div>
</div>
```

### 4. Open Orders Widget
```html
<h3>Your Open Orders</h3>
{% for order in open_orders %}
<div class="order">
  {{ order.side }} {{ order.amount }} {{ order.base_currency }}
  @ ${{ order.price }} ({{ order.order_type }})
  <button onclick="cancelOrder({{ order.id }})">Cancel</button>
</div>
{% endfor %}
```

---

## 🚀 Testing Checklist

- [ ] Buy USDT with CryptoBucks
- [ ] Market order: Buy BTC with USDT
- [ ] Limit order: Place and wait for execution
- [ ] Stop loss: Set below current price
- [ ] Take profit: Set above current price
- [ ] Cancel pending order
- [ ] View order book
- [ ] Check balances update correctly
- [ ] Verify order history displays

---

## 📞 Key Functions Reference

| Function | Purpose |
|----------|---------|
| `check_pending_orders()` | Background job - executes limit/stop orders |
| `execute_order()` | Processes order and updates balances |
| `/trade` route | Handles all order submissions |
| `/orders` route | Displays user's orders |
| `/api/orderbook/<pair>` | Returns order book data |

---

## 🎓 Educational Value

This simulator teaches users:
1. ✅ **Order types** - When to use each
2. ✅ **Risk management** - Stop losses prevent big losses
3. ✅ **Profit taking** - Lock in gains systematically
4. ✅ **Market mechanics** - How order books work
5. ✅ **Trading pairs** - Understanding base/quote currencies
6. ✅ **Position sizing** - Managing portfolio allocation

All **without risking real money!**

---

## 🔐 Security Notes

- All balances are virtual (CryptoBucks and USDT)
- No real money or real crypto involved
- Users practice risk-free
- Background job runs every 5 minutes (adjustable via `CHECK_INTERVAL`)

---

**Your crypto tracker is now a professional trading simulator!** 🎉
