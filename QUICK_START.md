# 🚀 Quick Start Guide - Trading Simulator

## Step-by-Step Setup (5 Minutes)

### 1️⃣ Apply Database Changes
Open terminal and run:
```bash
cd d:\crypto_tracker
mysql -u root -pPranavrh123$ crypto_tracker < trading_schema.sql
```

**What this does:**
- Creates `trading_pairs` table with 10 default pairs
- Creates `orders` table for all order types
- Creates `order_fills` table for execution history
- Adds `tether_balance` column to users
- Adds necessary indexes

### 2️⃣ Verify Schema
```bash
mysql -u root -pPranavrh123$ crypto_tracker < init_trading.sql
```

Check output - you should see trading pairs and table structures.

### 3️⃣ Restart Flask App
```bash
python app.py
```

**New Background Jobs Running:**
- Price alerts checker (every 5 min) ✅ *Already had this*
- **Pending orders checker (every 5 min)** ✅ *NEW!*

---

## 🎮 Test the Features

### Test 1: Buy USDT with CryptoBucks
1. Login to your account
2. Go to Live Market
3. Find "Tether (USDT)"
4. Click Trade → Buy
5. Amount: 1000 USDT
6. Order Type: Market
7. Submit

**Expected Result:**
- CryptoBucks decreased by ~1000
- USDT balance = 1000

### Test 2: Buy BTC with USDT
1. Still on Live Market
2. Find "Bitcoin (BTC)"
3. Click Trade → Buy
4. Amount: 0.01 BTC
5. Quote Currency: USDT *(new dropdown)*
6. Order Type: Market
7. Submit

**Expected Result:**
- USDT balance decreased
- BTC added to portfolio

### Test 3: Place Limit Order
1. Find Ethereum (ETH)
2. Click Trade → Buy
3. Amount: 0.5 ETH
4. Order Type: Limit
5. Limit Price: *enter price 5% below current*
6. Submit

**Expected Result:**
- Order appears in `/orders` as "Pending"
- Will execute when ETH price drops to your limit

### Test 4: Set Stop Loss
1. Go to Portfolio
2. Find your BTC holding
3. Click Sell
4. Order Type: Stop Loss
5. Stop Price: *enter price 10% below current*
6. Amount: Your BTC amount
7. Submit

**Expected Result:**
- Protective sell order created
- Will trigger if BTC drops to stop price

### Test 5: Check Order Book
Visit in browser:
```
http://localhost:5000/api/orderbook/bitcoin-tether
```

**Expected Result:**
```json
{
  "pair": "bitcoin/tether",
  "bids": [...],
  "asks": [...],
  "timestamp": "..."
}
```

---

## 🔍 Verify Everything Works

### Check Database
```sql
-- See your USDT balance
SELECT username, crypto_bucks, tether_balance FROM users;

-- See pending orders
SELECT * FROM orders WHERE status = 'pending';

-- See trading pairs
SELECT * FROM trading_pairs;

-- See recent transactions
SELECT * FROM transactions ORDER BY timestamp DESC LIMIT 10;
```

### Check Logs
Watch terminal for:
```
Checking pending orders...
Checking price alerts...
[Every 5 minutes]
```

---

## 🎯 User Flow Diagram

```
┌─────────────────────────┐
│  New User Registers     │
│  Gets 10,000 CryptoBucks│
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  Buy USDT               │
│  (with CryptoBucks)     │
│  1 USDT = ~$1           │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  Trade Crypto           │
│  BTC/USDT, ETH/USDT     │
│  (with USDT)            │
└───────────┬─────────────┘
            │
            ├─ Market Order ──→ Instant execution
            │
            ├─ Limit Order ───→ Wait for price
            │
            ├─ Stop Loss ─────→ Auto-sell if drops
            │
            └─ Take Profit ───→ Auto-sell if rises
```

---

## 📱 Available Pages

| URL | What You'll See |
|-----|----------------|
| `/dashboard` | Balances (CryptoBucks + USDT) |
| `/live_market` | Trade with enhanced data (high/low/volume) |
| `/portfolio` | Your holdings |
| `/orders` | Open orders + history *(NEW!)* |
| `/watchlist` | Tracked coins |
| `/alerts` | Price alerts |
| `/api/orderbook/bitcoin-tether` | Order book JSON *(NEW!)* |
| `/trading_pairs` | Available pairs JSON *(NEW!)* |

---

## 🛠️ Troubleshooting

### "Table 'orders' doesn't exist"
**Fix:** Run the schema again:
```bash
mysql -u root -pPranavrh123$ crypto_tracker < trading_schema.sql
```

### "Column 'tether_balance' not found"
**Fix:** Run this manually:
```sql
ALTER TABLE users ADD COLUMN tether_balance DECIMAL(20, 8) DEFAULT 0;
```

### Orders not executing
**Check:**
1. Is Flask running? (background job needs Flask active)
2. Check logs for "Checking pending orders..."
3. Is current price meeting your limit/stop price?
4. Query: `SELECT * FROM orders WHERE status = 'pending';`

### Can't buy crypto with USDT
**Check:**
1. Do you have USDT balance? `SELECT tether_balance FROM users WHERE id = YOUR_ID;`
2. Did you buy USDT first?
3. Is quote_currency set to 'tether' in form?

---

## 📋 Quick Reference

### Order Types at a Glance

| Order | When to Use | Example |
|-------|-------------|---------|
| **Market** | Buy/sell NOW | "Buy 0.1 BTC right now" |
| **Limit** | Wait for better price | "Buy when BTC drops to $40k" |
| **Stop Loss** | Limit losses | "Sell if BTC drops to $38k" |
| **Take Profit** | Lock gains | "Sell when BTC hits $50k" |

### Form Fields

**Market Order:**
- coin_id ✓
- amount ✓
- current_price ✓
- order_type = "market" ✓
- action (buy/sell) ✓
- quote_currency *(new!)* ✓

**Limit Order:**
- Same as market PLUS:
- limit_price ✓
- order_type = "limit" ✓

**Stop Loss:**
- Same as market PLUS:
- stop_price ✓
- order_type = "stop_loss" ✓
- action = "sell" ✓

**Take Profit:**
- Same as stop loss
- order_type = "take_profit" ✓

---

## 🎓 Teaching Users

### Add These Tooltips to Your UI

**Market Order:**
> 💡 Executes immediately at current market price. Best for entering/exiting quickly.

**Limit Order:**
> 💡 Only executes when price reaches your target. Use to buy low or sell high automatically.

**Stop Loss:**
> ⚠️ Protects you from large losses. Place 5-10% below your buy price.
> Example: Bought at $100? Set stop at $90-$95.

**Take Profit:**
> 🎯 Locks in profits automatically. Set your target profit level.
> Example: Bought at $100? Set take profit at $120 for 20% gain.

---

## ✅ Success Indicators

You know it's working when:

- ✅ Dashboard shows both CryptoBucks AND USDT balance
- ✅ Can buy USDT from Live Market
- ✅ Can place different order types
- ✅ `/orders` page shows your pending orders
- ✅ Background job logs appear every 5 min
- ✅ Order book API returns JSON data
- ✅ Limit orders execute when price is reached

---

## 🎉 You're Ready!

**Your trading simulator is live!**

Users can now:
1. ✅ Learn trading with virtual money
2. ✅ Practice order types
3. ✅ Understand risk management
4. ✅ Use real market prices
5. ✅ Explore before risking real capital

**No real money involved = Safe learning! 🎓**

---

## 📞 Need Help?

Check these files for details:
- `TRADING_FEATURES.md` - Complete feature documentation
- `IMPLEMENTATION_SUMMARY.md` - Technical overview
- `init_trading.sql` - Database testing queries

Happy trading (simulation)! 🚀
