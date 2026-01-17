# 🎨 UI/Template Updates Needed

This file shows exactly what needs to be added to your templates to display the new trading features.

---

## 1. Update Live Market Page (`templates/combined.html`)

### Add Order Type Selector to Trade Form

Find your existing trade form and update it to:

```html
<!-- Enhanced Trading Form -->
<form method="POST" action="/trade" class="trade-form">
    <!-- Existing fields -->
    <input type="hidden" name="coin_id" value="{{ coin.id }}">
    <input type="hidden" name="wallet_id" value="{{ wallets[0].id }}">
    <input type="hidden" name="current_price" value="{{ coin.current_price }}">
    <input type="hidden" name="source" value="live_market">
    
    <!-- Buy/Sell Toggle -->
    <div class="form-group">
        <label>Action:</label>
        <select name="action" id="trade-action" required onchange="updateFormFields()">
            <option value="buy">Buy</option>
            <option value="sell">Sell</option>
        </select>
    </div>
    
    <!-- NEW: Order Type Selector -->
    <div class="form-group">
        <label>Order Type:</label>
        <select name="order_type" id="order-type" required onchange="updateFormFields()">
            <option value="market">Market Order (Instant)</option>
            <option value="limit">Limit Order (Wait for Price)</option>
            <option value="stop_loss">Stop Loss (Protect)</option>
            <option value="take_profit">Take Profit (Lock Gains)</option>
        </select>
        <small class="help-text" id="order-type-help">
            Executes immediately at current market price
        </small>
    </div>
    
    <!-- Amount -->
    <div class="form-group">
        <label>Amount:</label>
        <input type="number" name="amount" step="0.00000001" required>
    </div>
    
    <!-- NEW: Quote Currency Selector (for buying) -->
    <div class="form-group" id="quote-currency-group" style="display:none;">
        <label>Pay With:</label>
        <select name="quote_currency" id="quote-currency">
            <option value="cryptobucks">CryptoBucks ({{ user_balances.crypto_bucks | round(2) }})</option>
            <option value="tether">USDT ({{ user_balances.tether | round(2) }})</option>
        </select>
    </div>
    
    <!-- NEW: Limit Price (shown for limit orders) -->
    <div class="form-group" id="limit-price-group" style="display:none;">
        <label>Limit Price ($):</label>
        <input type="number" name="limit_price" step="0.01" placeholder="Target price">
        <small class="help-text">Order executes when price reaches this level</small>
    </div>
    
    <!-- NEW: Stop Price (shown for stop_loss/take_profit) -->
    <div class="form-group" id="stop-price-group" style="display:none;">
        <label>Stop Price ($):</label>
        <input type="number" name="stop_price" step="0.01" placeholder="Trigger price">
        <small class="help-text" id="stop-price-help"></small>
    </div>
    
    <!-- Current Price Display -->
    <div class="price-info">
        <strong>Current Price:</strong> ${{ coin.current_price | round(2) }}
        <br>
        <strong>24h High:</strong> ${{ coin.high_24h | round(2) }}
        <br>
        <strong>24h Low:</strong> ${{ coin.low_24h | round(2) }}
        <br>
        <strong>24h Volume:</strong> ${{ coin.total_volume | round(0) }}
    </div>
    
    <button type="submit" class="btn btn-primary">Place Order</button>
</form>

<script>
function updateFormFields() {
    const orderType = document.getElementById('order-type').value;
    const action = document.getElementById('trade-action').value;
    const limitGroup = document.getElementById('limit-price-group');
    const stopGroup = document.getElementById('stop-price-group');
    const quoteGroup = document.getElementById('quote-currency-group');
    const helpText = document.getElementById('order-type-help');
    const stopHelp = document.getElementById('stop-price-help');
    
    // Hide all conditional fields
    limitGroup.style.display = 'none';
    stopGroup.style.display = 'none';
    
    // Show quote currency selector only for buy orders
    quoteGroup.style.display = (action === 'buy') ? 'block' : 'none';
    
    // Show relevant fields based on order type
    switch(orderType) {
        case 'market':
            helpText.textContent = 'Executes immediately at current market price';
            break;
        case 'limit':
            limitGroup.style.display = 'block';
            helpText.textContent = 'Waits until price reaches your target level';
            break;
        case 'stop_loss':
            stopGroup.style.display = 'block';
            stopHelp.textContent = 'Automatically sells if price drops to this level (protects against losses)';
            helpText.textContent = 'Protects your investment from large losses';
            break;
        case 'take_profit':
            stopGroup.style.display = 'block';
            stopHelp.textContent = 'Automatically sells if price rises to this level (locks in profits)';
            helpText.textContent = 'Locks in your profits when target is reached';
            break;
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', updateFormFields);
</script>
```

---

## 2. Create New Orders Page

Add to `templates/combined.html` (in the sections area):

```html
{% if section == 'orders' %}
<div class="orders-container">
    <h2>📋 My Orders</h2>
    
    <!-- Balances Summary -->
    <div class="balances-summary">
        <div class="balance-card">
            <h4>CryptoBucks</h4>
            <p class="balance-amount">${{ user.crypto_bucks | round(2) }}</p>
        </div>
        <div class="balance-card">
            <h4>USDT Balance</h4>
            <p class="balance-amount">${{ user.tether_balance | round(2) }}</p>
        </div>
    </div>
    
    <!-- Open Orders -->
    <div class="section">
        <h3>🔄 Open Orders</h3>
        {% if open_orders %}
        <table class="orders-table">
            <thead>
                <tr>
                    <th>Pair</th>
                    <th>Type</th>
                    <th>Side</th>
                    <th>Amount</th>
                    <th>Price</th>
                    <th>Status</th>
                    <th>Created</th>
                    <th>Actions</th>
                </tr>
            </thead>
            <tbody>
                {% for order in open_orders %}
                <tr>
                    <td>
                        <strong>{{ order.base_currency.upper() }}/{{ order.quote_currency.upper() }}</strong>
                    </td>
                    <td>
                        <span class="badge badge-{{ order.order_type }}">
                            {{ order.order_type.replace('_', ' ').title() }}
                        </span>
                    </td>
                    <td>
                        <span class="badge badge-{{ order.side }}">
                            {{ order.side.upper() }}
                        </span>
                    </td>
                    <td>{{ order.amount }}</td>
                    <td>
                        {% if order.price %}
                            ${{ order.price | round(2) }}
                        {% elif order.stop_price %}
                            Stop: ${{ order.stop_price | round(2) }}
                        {% else %}
                            Market
                        {% endif %}
                    </td>
                    <td>
                        <span class="status status-{{ order.status }}">
                            {{ order.status.title() }}
                        </span>
                    </td>
                    <td>{{ order.created_at.strftime('%Y-%m-%d %H:%M') }}</td>
                    <td>
                        <form method="POST" action="/cancel_order/{{ order.id }}" style="display:inline;">
                            <button type="submit" class="btn btn-sm btn-danger" 
                                    onclick="return confirm('Cancel this order?')">
                                Cancel
                            </button>
                        </form>
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
        {% else %}
        <p class="no-data">No open orders. Place your first order from the Live Market page!</p>
        {% endif %}
    </div>
    
    <!-- Order History -->
    <div class="section">
        <h3>📜 Order History</h3>
        {% if order_history %}
        <table class="orders-table">
            <thead>
                <tr>
                    <th>Pair</th>
                    <th>Type</th>
                    <th>Side</th>
                    <th>Amount</th>
                    <th>Price</th>
                    <th>Status</th>
                    <th>Date</th>
                </tr>
            </thead>
            <tbody>
                {% for order in order_history %}
                <tr>
                    <td>{{ order.base_currency.upper() }}/{{ order.quote_currency.upper() }}</td>
                    <td>{{ order.order_type.replace('_', ' ').title() }}</td>
                    <td>
                        <span class="badge badge-{{ order.side }}">
                            {{ order.side.upper() }}
                        </span>
                    </td>
                    <td>{{ order.amount }}</td>
                    <td>
                        {% if order.price %}
                            ${{ order.price | round(2) }}
                        {% elif order.stop_price %}
                            ${{ order.stop_price | round(2) }}
                        {% endif %}
                    </td>
                    <td>
                        <span class="status status-{{ order.status }}">
                            {{ order.status.title() }}
                        </span>
                    </td>
                    <td>
                        {% if order.filled_at %}
                            {{ order.filled_at.strftime('%Y-%m-%d %H:%M') }}
                        {% elif order.cancelled_at %}
                            {{ order.cancelled_at.strftime('%Y-%m-%d %H:%M') }}
                        {% endif %}
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
        {% else %}
        <p class="no-data">No order history yet.</p>
        {% endif %}
    </div>
</div>
{% endif %}
```

---

## 3. Update Dashboard to Show Balances

Find your dashboard section and add:

```html
{% if section == 'dashboard' %}
<div class="dashboard">
    <h2>💼 Dashboard</h2>
    
    <!-- Enhanced Balance Display -->
    <div class="balances-grid">
        <div class="balance-card cryptobucks">
            <div class="balance-icon">💵</div>
            <h3>CryptoBucks</h3>
            <p class="balance-amount">${{ user.crypto_bucks | round(2) }}</p>
            <small>Virtual training currency</small>
        </div>
        
        <div class="balance-card usdt">
            <div class="balance-icon">💰</div>
            <h3>USDT (Tether)</h3>
            <p class="balance-amount">${{ user.tether_balance | default(0) | round(2) }}</p>
            <small>Stablecoin for trading</small>
            <a href="/live_market" class="btn btn-sm">Buy USDT</a>
        </div>
        
        <div class="balance-card portfolio">
            <div class="balance-icon">📊</div>
            <h3>Portfolio Value</h3>
            <p class="balance-amount">Calculate...</p>
            <small>Total holdings value</small>
            <a href="/portfolio" class="btn btn-sm">View Portfolio</a>
        </div>
    </div>
    
    <!-- Quick Actions -->
    <div class="quick-actions">
        <h3>Quick Actions</h3>
        <a href="/live_market" class="action-btn">
            <span>🛒</span>
            <span>Trade Now</span>
        </a>
        <a href="/orders" class="action-btn">
            <span>📋</span>
            <span>My Orders</span>
        </a>
        <a href="/portfolio" class="action-btn">
            <span>💼</span>
            <span>Portfolio</span>
        </a>
        <a href="/alerts" class="action-btn">
            <span>🔔</span>
            <span>Price Alerts</span>
        </a>
    </div>
    
    <!-- Rest of your existing dashboard content... -->
</div>
{% endif %}
```

---

## 4. Add Navigation Link for Orders

In your navigation menu, add:

```html
<nav>
    <a href="/dashboard">Dashboard</a>
    <a href="/live_market">Live Market</a>
    <a href="/portfolio">Portfolio</a>
    <a href="/orders">📋 Orders</a>  <!-- NEW! -->
    <a href="/watchlist">Watchlist</a>
    <a href="/alerts">Alerts</a>
    <a href="/logout">Logout</a>
</nav>
```

---

## 5. Add CSS Styles

Add to `static/css/style.css`:

```css
/* Order Type Badges */
.badge {
    padding: 4px 8px;
    border-radius: 4px;
    font-size: 0.85em;
    font-weight: bold;
}

.badge-market {
    background: #4CAF50;
    color: white;
}

.badge-limit {
    background: #2196F3;
    color: white;
}

.badge-stop_loss {
    background: #f44336;
    color: white;
}

.badge-take_profit {
    background: #FF9800;
    color: white;
}

.badge-buy {
    background: #28a745;
    color: white;
}

.badge-sell {
    background: #dc3545;
    color: white;
}

/* Order Status */
.status {
    padding: 4px 10px;
    border-radius: 12px;
    font-size: 0.85em;
}

.status-pending {
    background: #fff3cd;
    color: #856404;
}

.status-filled {
    background: #d4edda;
    color: #155724;
}

.status-cancelled {
    background: #f8d7da;
    color: #721c24;
}

/* Balances Grid */
.balances-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
    gap: 20px;
    margin-bottom: 30px;
}

.balance-card {
    background: white;
    padding: 20px;
    border-radius: 10px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
    text-align: center;
}

.balance-card .balance-icon {
    font-size: 3em;
    margin-bottom: 10px;
}

.balance-card h3 {
    margin: 10px 0;
    font-size: 1.2em;
}

.balance-amount {
    font-size: 2em;
    font-weight: bold;
    color: #2c3e50;
    margin: 10px 0;
}

.balance-card small {
    color: #7f8c8d;
}

.balance-card .btn-sm {
    margin-top: 10px;
    padding: 5px 15px;
    font-size: 0.9em;
}

/* Orders Table */
.orders-table {
    width: 100%;
    border-collapse: collapse;
    margin: 20px 0;
    background: white;
    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
}

.orders-table thead {
    background: #2c3e50;
    color: white;
}

.orders-table th,
.orders-table td {
    padding: 12px;
    text-align: left;
    border-bottom: 1px solid #ddd;
}

.orders-table tbody tr:hover {
    background: #f5f5f5;
}

/* Help Text */
.help-text {
    display: block;
    margin-top: 5px;
    color: #666;
    font-size: 0.9em;
}

/* Form Groups */
.form-group {
    margin-bottom: 15px;
}

.form-group label {
    display: block;
    margin-bottom: 5px;
    font-weight: bold;
}

.form-group input,
.form-group select {
    width: 100%;
    padding: 8px;
    border: 1px solid #ddd;
    border-radius: 4px;
}

/* Quick Actions */
.quick-actions {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: 15px;
    margin: 20px 0;
}

.action-btn {
    background: white;
    padding: 20px;
    border-radius: 8px;
    text-align: center;
    text-decoration: none;
    color: #2c3e50;
    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    transition: transform 0.2s;
}

.action-btn:hover {
    transform: translateY(-3px);
    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
}

.action-btn span:first-child {
    display: block;
    font-size: 2em;
    margin-bottom: 8px;
}

/* Price Info */
.price-info {
    background: #f8f9fa;
    padding: 15px;
    border-radius: 8px;
    margin: 15px 0;
}

.price-info strong {
    color: #2c3e50;
}
```

---

## 6. Order Book Visualization (Optional)

If you want to show the order book, add this section:

```html
<div class="order-book" id="orderbook-{{ coin.id }}">
    <h4>📊 Order Book</h4>
    <div class="orderbook-content">
        <div class="asks">
            <h5>Sell Orders (Asks)</h5>
            <div class="orders-list" id="asks-{{ coin.id }}"></div>
        </div>
        <div class="current-price">
            <strong>Current: ${{ coin.current_price }}</strong>
        </div>
        <div class="bids">
            <h5>Buy Orders (Bids)</h5>
            <div class="orders-list" id="bids-{{ coin.id }}"></div>
        </div>
    </div>
</div>

<script>
function loadOrderBook(coinId, quoteCurrency = 'tether') {
    fetch(`/api/orderbook/${coinId}-${quoteCurrency}`)
        .then(res => res.json())
        .then(data => {
            const asksDiv = document.getElementById(`asks-${coinId}`);
            const bidsDiv = document.getElementById(`bids-${coinId}`);
            
            // Display asks (sell orders)
            asksDiv.innerHTML = data.asks.slice(0, 5).map(ask => `
                <div class="order-row ask-row">
                    <span class="price">$${ask.price_level.toFixed(2)}</span>
                    <span class="amount">${ask.total_amount.toFixed(4)}</span>
                </div>
            `).join('');
            
            // Display bids (buy orders)
            bidsDiv.innerHTML = data.bids.slice(0, 5).map(bid => `
                <div class="order-row bid-row">
                    <span class="price">$${bid.price_level.toFixed(2)}</span>
                    <span class="amount">${bid.total_amount.toFixed(4)}</span>
                </div>
            `).join('');
        })
        .catch(err => console.error('Order book load failed:', err));
}

// Auto-refresh every 30 seconds
setInterval(() => loadOrderBook('bitcoin'), 30000);
</script>
```

---

## Summary

**Files to Update:**
1. ✅ `templates/combined.html` - Add order form fields, orders page, enhanced dashboard
2. ✅ `static/css/style.css` - Add styling for new components
3. ✅ Navigation menu - Add "Orders" link

**Key Features to Implement in UI:**
- Order type selector (Market/Limit/Stop Loss/Take Profit)
- Conditional form fields based on order type
- Display CryptoBucks AND USDT balances
- Orders management page
- Order book visualization (optional but recommended)

**The backend is ready - just add these UI elements and you're done!** 🎉
