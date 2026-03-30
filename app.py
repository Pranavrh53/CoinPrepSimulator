from flask import Flask, request, jsonify, render_template, session, redirect, url_for, flash, json, send_file, send_from_directory
from flask_bcrypt import Bcrypt
from flask_cors import CORS
import mysql.connector
import requests
import json
from datetime import datetime, timedelta
import os
import random
import string
import time
import numpy as np
import pandas as pd
from queue import Queue
from threading import Lock
from apscheduler.schedulers.background import BackgroundScheduler
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import io
import contextlib
import traceback
from risk_assessment_data import (
    FINANCIAL_CAPACITY_TEST,
    INVESTMENT_KNOWLEDGE_TEST,
    PSYCHOLOGICAL_TOLERANCE_TEST,
    GOALS_TIMELINE_TEST,
    RISK_CATEGORIES,
    get_ai_analysis_prompt
)

# Import AI Learning System
from ai_assistant import get_ai_assistant
from user_profiler import get_user_profiler
from learning_routes import learning_bp, init_learning_system


def _load_local_env_file():
    """Load key/value pairs from .env into process environment."""
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    if not os.path.exists(env_path):
        return

    try:
        with open(env_path, 'r', encoding='utf-8') as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue

                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except Exception as e:
        print(f"Warning: failed to load .env file: {e}")


_load_local_env_file()

app = Flask(__name__)
app.secret_key = os.urandom(24)
bcrypt = Bcrypt(app)

# Allow the Lovable/Vite frontend (different port) to call Flask API endpoints.
# credentials=True is required so the browser sends the Flask session cookie.
CORS(
    app,
    resources={r"/api/*": {"origins": [
        "http://localhost:5173",   # Vite dev server (default)
        "http://localhost:8080",   # Alternative Vite port
        "http://localhost:3000",   # CRA / other dev server
        "http://127.0.0.1:5173",
        "http://127.0.0.1:8080",
    ]}},
    supports_credentials=True,
)

# Email Configuration
EMAIL_CONFIG = {
    'MAIL_SERVER': 'smtp.gmail.com',  # Using Gmail SMTP server
    'MAIL_PORT': 587,
    'MAIL_USE_TLS': True,
    'MAIL_USERNAME': 'frozenflames677@gmail.com',  # Replace with your email
    'MAIL_PASSWORD': 'auhe hrhm cfix hjii',     # Use App Password if 2FA is enabled
    'MAIL_DEFAULT_SENDER': 'frozenflames677@gmail.com'  # Replace with your email
}

# MySQL Configuration
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': 'Pranavrh123$',
    'database': 'crypto_tracker'
}

# CoinGecko API
COINGECKO_API = "https://api.coingecko.com/api/v3"
COINS_PER_PAGE = 20
CACHE_DURATION = 600  # Cache API responses for 10 minutes
api_cache = {}  # In-memory cache: {url: (response_data, timestamp)}
CHECK_INTERVAL = 300  # Check prices every 5 minutes

# Request throttling
REQUEST_LIMIT = 5  # Requests per minute
REQUEST_WINDOW = 60  # Window in seconds (1 minute)
request_timestamps = Queue()
request_lock = Lock()

def get_db_connection():
    try:
        return mysql.connector.connect(**db_config)
    except mysql.connector.Error as err:
        print(f"Database connection failed: {err}")
        return None


def ensure_watchlist_scenarios_table(conn):
    """Ensure scenario replay history table exists for watchlist simulator."""
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS watchlist_scenarios (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            coin_id VARCHAR(64) NOT NULL,
            replay_date DATE NOT NULL,
            entry_price DECIMAL(18, 8) NOT NULL,
            conservative_return DECIMAL(8, 2) NOT NULL,
            rule_based_return DECIMAL(8, 2) NOT NULL,
            emotional_return DECIMAL(8, 2) NOT NULL,
            best_strategy VARCHAR(64) NOT NULL,
            prep_score INT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_user_coin_created (user_id, coin_id, created_at)
        )
        """
    )
    conn.commit()
    cursor.close()


def ensure_price_alerts_schema(conn):
    """Ensure extended alert fields and history table exist."""
    cursor = conn.cursor()

    cursor.execute("SHOW COLUMNS FROM price_alerts LIKE 'note'")
    if not cursor.fetchone():
        cursor.execute("ALTER TABLE price_alerts ADD COLUMN note VARCHAR(500) NULL")

    cursor.execute("SHOW COLUMNS FROM price_alerts LIKE 'snoozed_until'")
    if not cursor.fetchone():
        cursor.execute("ALTER TABLE price_alerts ADD COLUMN snoozed_until DATETIME NULL")

    cursor.execute("SHOW COLUMNS FROM price_alerts LIKE 'triggered_at'")
    if not cursor.fetchone():
        cursor.execute("ALTER TABLE price_alerts ADD COLUMN triggered_at DATETIME NULL")

    cursor.execute("SHOW COLUMNS FROM price_alerts LIKE 'trigger_price'")
    if not cursor.fetchone():
        cursor.execute("ALTER TABLE price_alerts ADD COLUMN trigger_price DECIMAL(15, 2) NULL")

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS price_alert_history (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            alert_id INT NULL,
            coin_id VARCHAR(50) NOT NULL,
            target_price DECIMAL(15, 2) NOT NULL,
            trigger_price DECIMAL(15, 2) NOT NULL,
            alert_type ENUM('above', 'below') NOT NULL,
            note VARCHAR(500) NULL,
            triggered_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_user_triggered (user_id, triggered_at),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
    )

    conn.commit()
    cursor.close()

def generate_verification_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

def throttle_request():
    with request_lock:
        current_time = time.time()
        while not request_timestamps.empty():
            if current_time - request_timestamps.queue[0] > REQUEST_WINDOW:
                request_timestamps.get()
            else:
                break
        if request_timestamps.qsize() >= REQUEST_LIMIT:
            oldest_request = request_timestamps.queue[0]
            sleep_time = REQUEST_WINDOW - (current_time - oldest_request) + 1
            print(f"Rate limit reached. Sleeping for {sleep_time:.2f} seconds.")
            time.sleep(sleep_time)
        request_timestamps.put(current_time)

def fetch_with_retry(url, retries=3, base_delay=10):
    if url in api_cache:
        cached_data, timestamp = api_cache[url]
        if time.time() - timestamp < CACHE_DURATION:
            print(f"Cache hit for {url}")
            if isinstance(cached_data, (list, dict)) and cached_data:  # Validate cached data
                return type(
                    'Response',
                    (),
                    {
                        'text': json.dumps(cached_data),
                        'json': lambda *args, **kwargs: cached_data,
                        'raise_for_status': lambda *args, **kwargs: None,
                    },
                )()
            else:
                print(f"Invalid cached data for {url}, fetching fresh data")
        else:
            print(f"Cache expired for {url}")

    throttle_request()
    for attempt in range(retries):
        try:
            print(f"Making API request to {url} (attempt {attempt + 1})")
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            api_cache[url] = (data, time.time())
            print(f"API request successful for {url}")
            return response
        except requests.RequestException as e:
            if attempt < retries - 1:
                delay = base_delay * (2 ** attempt)
                print(f"Request failed: {e}. Retrying in {delay} seconds...")
                time.sleep(delay)
                continue
            print(f"API request failed after {retries} attempts: {e}")
            if url in api_cache:
                cached_data, timestamp = api_cache[url]
                if isinstance(cached_data, (list, dict)) and cached_data:
                    print(f"Returning expired cached response for {url}")
                    return type(
                        'Response',
                        (),
                        {
                            'text': json.dumps(cached_data),
                            'json': lambda *args, **kwargs: cached_data,
                            'raise_for_status': lambda *args, **kwargs: None,
                        },
                    )()
            return None
    return None

def send_email_notification(recipient, subject, body):
    """Send an email notification to the specified recipient."""
    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_CONFIG['MAIL_DEFAULT_SENDER']
        msg['To'] = recipient
        msg['Subject'] = subject
        
        msg.attach(MIMEText(body, 'plain'))
        
        with smtplib.SMTP(EMAIL_CONFIG['MAIL_SERVER'], EMAIL_CONFIG['MAIL_PORT']) as server:
            server.starttls()
            server.login(EMAIL_CONFIG['MAIL_USERNAME'], EMAIL_CONFIG['MAIL_PASSWORD'])
            server.send_message(msg)
            
        print(f"Email notification sent to {recipient}")
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False

# Comprehensive Risk Assessment Helper Functions
def calculate_test_score(test_data, responses):
    """Calculate percentage score for a single test"""
    total_possible = sum(max(opt['points'] for opt in q['options']) for q in test_data['questions'])
    total_earned = sum(responses.get(q['id'], 0) for q in test_data['questions'])
    return round((total_earned / total_possible) * 100, 2)

def get_risk_category(weighted_score):
    """Get risk category based on weighted average score"""
    for category in RISK_CATEGORIES:
        if category['range'][0] <= weighted_score < category['range'][1]:
            return category
    return RISK_CATEGORIES[-1]  # Return most aggressive if > max

def generate_ai_analysis(scores, user_data):
    """Generate AI-powered analysis of user's risk profile"""
    analysis = {
        'summary': '',
        'strengths': [],
        'concerns': [],
        'recommendations': [],
        'asset_allocation': {},
        'crypto_advice': '',
        'action_steps': [],
        'risk_management': []
    }
    
    category = get_risk_category(scores['total'])
    analysis['summary'] = f"Your comprehensive risk assessment indicates a **{category['level']}** risk profile with an overall score of {scores['total']}%. {category['description']}"
    
    # Analyze each dimension
    if scores['financial'] >= 70:
        analysis['strengths'].append("Strong financial capacity with good income stability and emergency reserves")
    elif scores['financial'] >= 50:
        analysis['strengths'].append("Adequate financial capacity to support moderate risk-taking")
    else:
        analysis['concerns'].append("Limited financial capacity - focus on building emergency fund before aggressive investing")
    
    if scores['knowledge'] >= 70:
        analysis['strengths'].append("Solid investment knowledge and experience base")
    elif scores['knowledge'] >= 50:
        analysis['strengths'].append("Good foundational investment knowledge")
    else:
        analysis['concerns'].append("Limited investment knowledge - consider educational resources before complex strategies")
    
    if scores['psychological'] >= 70:
        analysis['strengths'].append("Strong emotional resilience to market volatility")
    elif scores['psychological'] >= 50:
        analysis['strengths'].append("Moderate psychological comfort with market fluctuations")
    else:
        analysis['concerns'].append("Low psychological tolerance for volatility - stick to stable investments")
    
    if scores['goals'] >= 70:
        analysis['strengths'].append("Long time horizon allowing for growth-oriented strategies")
    elif scores['goals'] >= 50:
        analysis['strengths'].append("Moderate timeline suitable for balanced approach")
    else:
        analysis['concerns'].append("Short time horizon - prioritize capital preservation")
    
    # Check for mismatches
    capacity_vs_tolerance = abs(scores['financial'] - scores['psychological'])
    if capacity_vs_tolerance > 30:
        if scores['financial'] > scores['psychological']:
            analysis['concerns'].append("⚠️ MISMATCH: Financial capacity exists but low psychological tolerance - start conservatively")
        else:
            analysis['concerns'].append("⚠️ MISMATCH: High risk appetite but limited financial capacity - be cautious")
    
    knowledge_vs_tolerance = abs(scores['knowledge'] - scores['psychological'])
    if knowledge_vs_tolerance > 30:
        if scores['knowledge'] < scores['psychological']:
            analysis['concerns'].append("⚠️ CAUTION: Risk appetite exceeds investment knowledge - educate yourself first")
    
    # Recommendations based on profile
    if scores['total'] < 30:
        analysis['recommendations'] = [
            "Focus on capital preservation with high-quality bonds and savings accounts",
            "Build emergency fund covering 6-12 months of expenses",
            "Consider low-cost index funds for equity exposure (10-20% max)",
            "Avoid speculative assets and complex derivatives",
            "Review portfolio quarterly but avoid frequent trading"
        ]
    elif scores['total'] < 45:
        analysis['recommendations'] = [
            "Maintain 50-60% in bonds and stable income assets",
            "Allocate 30-40% to diversified equity funds",
            "Consider dividend-paying stocks for income",
            "Keep 10% in cash for opportunities and emergencies",
            "Rebalance annually to maintain target allocation"
        ]
    elif scores['total'] < 55:
        analysis['recommendations'] = [
            "Balanced 50-50 or 60-40 stock-bond allocation",
            "Diversify across sectors, market caps, and geographies",
            "Include 5-10% alternative investments for diversification",
            "Consider tax-loss harvesting strategies",
            "Rebalance semi-annually or when allocations drift 5%+"
        ]
    elif scores['total'] < 65:
        analysis['recommendations'] = [
            "Growth-focused 60-70% equity allocation",
            "Include growth stocks, small-caps, and emerging markets",
            "Limit bonds to 20-30% for stability",
            "Consider sector-specific ETFs for targeted exposure",
            "Maintain discipline during market corrections"
        ]
    else:
        analysis['recommendations'] = [
            "Aggressive 75-85% equity allocation for maximum growth",
            "Include high-growth stocks, small-caps, and alternatives",
            "Consider sector rotation strategies",
            "Include international and emerging markets (20-30%)",
            "Prepare for 30-50% portfolio swings during market cycles"
        ]
    
    analysis['asset_allocation'] = category['allocation']
    
    # Crypto-specific advice
    crypto_pct = category['crypto_allocation']
    if scores['total'] < 30:
        analysis['crypto_advice'] = f"Cryptocurrency allocation: {crypto_pct}. Limit to well-established coins (BTC, ETH) only. Treat as speculative <2% of portfolio."
    elif scores['total'] < 45:
        analysis['crypto_advice'] = f"Cryptocurrency allocation: {crypto_pct}. Focus on top 10 cryptocurrencies by market cap. Consider dollar-cost averaging."
    elif scores['total'] < 55:
        analysis['crypto_advice'] = f"Cryptocurrency allocation: {crypto_pct}. Diversify across 5-10 established cryptocurrencies. Include both large-cap and mid-cap coins."
    elif scores['total'] < 65:
        analysis['crypto_advice'] = f"Cryptocurrency allocation: {crypto_pct}. Can explore beyond top 20 coins. Consider DeFi and blockchain projects with strong fundamentals."
    else:
        analysis['crypto_advice'] = f"Cryptocurrency allocation: {crypto_pct}. Can include small-cap and emerging projects. Consider staking and DeFi strategies."
    
    analysis['action_steps'] = [
        f"Review current portfolio allocation against recommended {category['level']} profile",
        f"Ensure emergency fund is adequate ({user_data.get('emergency_months', '3-6')} months expenses)",
        "Set up automatic rebalancing alerts when allocations drift >5%",
        "Review and adjust risk tolerance annually or after major life changes",
        "Track performance against appropriate benchmarks for your allocation"
    ]
    
    if scores['total'] < 40:
        analysis['risk_management'] = [
            "Use stop-loss orders at 5-10% below purchase price",
            "Avoid margin and leverage entirely",
            "Diversify across at least 15-20 holdings",
            "Keep 20-30% in cash and cash equivalents",
            "Review portfolio monthly but trade infrequently"
        ]
    elif scores['total'] < 60:
        analysis['risk_management'] = [
            "Use stop-loss orders at 10-15% below purchase price",
            "Limit single position size to 5-7% of portfolio",
            "Diversify across 10-15 holdings",
            "Maintain 5-10% cash position",
            "Review quarterly and rebalance as needed"
        ]
    else:
        analysis['risk_management'] = [
            "Use trailing stops on individual positions",
            "Can concentrate in 6-10 high-conviction positions",
            "Accept wider position sizing (up to 10% each)",
            "Minimal cash drag (0-5%) for maximum market exposure",
            "Active monitoring with quarterly deep reviews"
        ]
    
    return analysis

def check_price_alerts():
    print("Checking price alerts...")
    conn = get_db_connection()
    if not conn:
        print("Database connection failed in price alert check")
        return
    try:
        ensure_price_alerts_schema(conn)
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT pa.*, u.email as user_email
            FROM price_alerts pa
            JOIN users u ON pa.user_id = u.id
            WHERE pa.notified = 0
              AND (pa.snoozed_until IS NULL OR pa.snoozed_until <= NOW())
            """
        )
        alerts = cursor.fetchall()
        if not alerts:
            return
        coin_ids = list(set(alert['coin_id'] for alert in alerts))
        coin_ids_str = ','.join(coin_ids)
        response = fetch_with_retry(f"{COINGECKO_API}/coins/markets?vs_currency=usd&ids={coin_ids_str}")
        if not response:
            print("Failed to fetch prices for alerts")
            return
        prices = {coin['id']: float(coin['current_price']) for coin in json.loads(response.text) if 'current_price' in coin}
        for alert in alerts:
            coin_id = alert['coin_id']
            current_price = prices.get(coin_id)
            if current_price is None:
                continue
            target_price = float(alert['target_price'])
            alert_type = alert['alert_type']
            triggered = (alert_type == 'above' and current_price >= target_price) or (alert_type == 'below' and current_price <= target_price)
            if triggered:
                message = f"Alert: {coin_id.capitalize()} has {alert_type} ${target_price:.2f}. Current price: ${current_price:.2f}."
                cursor.execute(
                    "INSERT INTO notifications (user_id, coin_id, message) VALUES (%s, %s, %s)",
                    (alert['user_id'], coin_id, message)
                )

                cursor.execute(
                    """
                    INSERT INTO price_alert_history
                    (user_id, alert_id, coin_id, target_price, trigger_price, alert_type, note, triggered_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                    """,
                    (
                        alert['user_id'], alert['id'], coin_id,
                        target_price, current_price, alert_type, alert.get('note')
                    )
                )

                cursor.execute(
                    """
                    UPDATE price_alerts
                    SET notified = 1,
                        triggered_at = NOW(),
                        trigger_price = %s
                    WHERE id = %s
                    """,
                    (current_price, alert['id'])
                )
                conn.commit()
                print(f"Notification triggered for user {alert['user_id']}: {message}")
                # Send email notification to the user's email
                user_email = alert['user_email']
                send_email_notification(
                    recipient=user_email,
                    subject=f"Crypto Price Alert: {coin_id.upper()} {alert_type} {target_price}",
                    body=f"""
                    Hi,
                    
                    Your price alert has been triggered:
                    
                    {message}
                    
                    You can view your portfolio and set up new alerts by logging in to your account.
                    
                    Best regards,
                    Crypto Tracker Team(Pranav RH)
                    """
                )
    except mysql.connector.Error as err:
        print(f"Database error in price alert check: {err}")
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()

def check_pending_orders():
    """Check and execute pending limit, stop_loss, and take_profit orders"""
    print("Checking pending orders...")
    conn = get_db_connection()
    if not conn:
        print("Database connection failed in pending orders check")
        return
    try:
        cursor = conn.cursor(dictionary=True)
        # Get all pending orders
        cursor.execute("""
            SELECT o.* FROM orders o 
            WHERE o.status = 'pending' AND o.order_type IN ('limit', 'stop_loss', 'take_profit')
        """)
        orders = cursor.fetchall()
        
        if not orders:
            return
        
        # Get unique coin IDs to fetch prices
        coin_ids = list(set(order['base_currency'] for order in orders))
        coin_ids_str = ','.join(coin_ids)
        
        response = fetch_with_retry(f"{COINGECKO_API}/coins/markets?vs_currency=usd&ids={coin_ids_str}")
        if not response:
            print("Failed to fetch prices for pending orders")
            return
        
        prices = {coin['id']: float(coin['current_price']) for coin in json.loads(response.text) if 'current_price' in coin}
        
        for order in orders:
            base_currency = order['base_currency']
            current_price = prices.get(base_currency)
            
            if current_price is None:
                continue
            
            should_execute = False
            order_type = order['order_type']
            side = order['side']
            
            # Check if order should be executed
            if order_type == 'limit':
                if side == 'buy' and current_price <= float(order['price']):
                    should_execute = True
                elif side == 'sell' and current_price >= float(order['price']):
                    should_execute = True
            
            elif order_type == 'stop_loss':
                # Stop loss: sell when price drops below stop_price
                if side == 'sell' and current_price <= float(order['stop_price']):
                    should_execute = True
            
            elif order_type == 'take_profit':
                # Take profit: sell when price rises above stop_price
                if side == 'sell' and current_price >= float(order['stop_price']):
                    should_execute = True
            
            if should_execute:
                try:
                    # Execute the order
                    print(f"Attempting to execute {order_type} {side} order #{order['id']}: {order['amount']} {base_currency} @ ${current_price} (target: {order.get('price') or order.get('stop_price')})")
                    execute_order(cursor, conn, order, current_price)
                    conn.commit()  # Commit after each successful execution
                    print(f"✅ Successfully executed {order_type} order #{order['id']} for {order['amount']} {base_currency} at ${current_price}")
                except Exception as e:
                    print(f"❌ Error executing order #{order['id']}: {e}")
                    import traceback
                    traceback.print_exc()
                    conn.rollback()
    except mysql.connector.Error as err:
        print(f"Database error in pending orders check: {err}")
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()

def execute_order(cursor, conn, order, execution_price):
    """Execute a pending order at the given price"""
    user_id = order['user_id']
    wallet_id = order['wallet_id']
    base_currency = order['base_currency']
    quote_currency = order['quote_currency']
    side = order['side']
    amount = float(order['amount'])
    
    print(f"Executing {side} order: {amount} {base_currency} with {quote_currency} @ ${execution_price}")
    
    if side == 'buy':
        # Buy: Deduct quote currency, add base currency to portfolio
        if quote_currency == 'tether':
            cursor.execute("SELECT tether_balance FROM users WHERE id = %s", (user_id,))
            user = cursor.fetchone()
            if not user:
                raise Exception("User not found")
            
            tether_balance = float(user['tether_balance'])
            total_cost = amount * execution_price
            trading_fee = total_cost * 0.001  # 0.1% fee
            total_with_fee = total_cost + trading_fee
            
            print(f"USDT balance: ${tether_balance}, Cost: ${total_cost}, Fee: ${trading_fee:.2f}, Total: ${total_with_fee:.2f}")
            
            if total_with_fee > tether_balance:
                # Cancel order if insufficient balance
                print(f"Insufficient USDT balance. Cancelling order #{order['id']}")
                cursor.execute("UPDATE orders SET status = 'cancelled', cancelled_at = NOW() WHERE id = %s", (order['id'],))
                conn.commit()
                return
            
            # Deduct USDT and record transaction
            cursor.execute("UPDATE users SET tether_balance = tether_balance - %s WHERE id = %s", (total_with_fee, user_id))
            cursor.execute("""
                INSERT INTO transactions (user_id, wallet_id, coin_id, amount, price, type) 
                VALUES (%s, %s, %s, %s, %s, 'buy')
            """, (user_id, wallet_id, base_currency, amount, execution_price))
            print(f"Buy transaction recorded. Deducted ${total_cost} USDT")
            
        elif quote_currency == 'cryptobucks':
            cursor.execute("SELECT crypto_bucks FROM users WHERE id = %s", (user_id,))
            user = cursor.fetchone()
            if not user:
                raise Exception("User not found")
            
            crypto_bucks = float(user['crypto_bucks'])
            total_cost = amount * execution_price
            trading_fee = total_cost * 0.001  # 0.1% fee
            total_with_fee = total_cost + trading_fee
            
            print(f"CryptoBucks balance: ${crypto_bucks}, Cost: ${total_cost}, Fee: ${trading_fee:.2f}, Total: ${total_with_fee:.2f}")
            
            if total_with_fee > crypto_bucks:
                # Cancel order if insufficient balance
                print(f"Insufficient CryptoBucks. Cancelling order #{order['id']}")
                cursor.execute("UPDATE orders SET status = 'cancelled', cancelled_at = NOW() WHERE id = %s", (order['id'],))
                conn.commit()
                return
            
            # Deduct CryptoBucks and record transaction
            cursor.execute("UPDATE users SET crypto_bucks = crypto_bucks - %s WHERE id = %s", (total_with_fee, user_id))
            cursor.execute("""
                INSERT INTO transactions (user_id, wallet_id, coin_id, amount, price, type) 
                VALUES (%s, %s, %s, %s, %s, 'buy')
            """, (user_id, wallet_id, base_currency, amount, execution_price))
            print(f"Buy transaction recorded. Deducted ${total_cost} CryptoBucks")
    
    elif side == 'sell':
        # Sell: Check if user has the coins, add quote currency
        cursor.execute("""
            SELECT id, amount, price FROM transactions 
            WHERE user_id = %s AND wallet_id = %s AND coin_id = %s AND type = 'buy' 
            ORDER BY id ASC
        """, (user_id, wallet_id, base_currency))
        
        buy_transactions = cursor.fetchall()
        
        # Calculate available amount
        cursor.execute("""
            SELECT buy_transaction_id, SUM(amount) as total_sold 
            FROM transactions 
            WHERE user_id = %s AND type = 'sell' 
            GROUP BY buy_transaction_id
        """, (user_id,))
        
        sold_amounts = {row['buy_transaction_id']: float(row['total_sold']) for row in cursor.fetchall()}
        
        available_amount = 0
        buy_transaction_id = None
        purchase_price = None
        
        for buy in buy_transactions:
            buy_id = buy['id']
            total_bought = float(buy['amount'])
            total_sold = sold_amounts.get(buy_id, 0.0)
            remaining = total_bought - total_sold
            
            if remaining >= amount:
                buy_transaction_id = buy_id
                purchase_price = float(buy['price'])
                available_amount = remaining
                break
        
        if buy_transaction_id is None or available_amount < amount:
            # Cancel order if insufficient coins
            print(f"Insufficient {base_currency} to sell. Available: {available_amount}, Needed: {amount}")
            cursor.execute("UPDATE orders SET status = 'cancelled', cancelled_at = NOW() WHERE id = %s", (order['id'],))
            conn.commit()
            return
        
        # Execute sell
        revenue = amount * execution_price
        trading_fee = revenue * 0.001  # 0.1% fee
        net_revenue = revenue - trading_fee
        
        print(f"Selling {amount} {base_currency} for ${revenue:.2f}, Fee: ${trading_fee:.2f}, Net: ${net_revenue:.2f}")
        
        if quote_currency == 'tether':
            cursor.execute("UPDATE users SET tether_balance = tether_balance + %s WHERE id = %s", (net_revenue, user_id))
        elif quote_currency == 'cryptobucks':
            cursor.execute("UPDATE users SET crypto_bucks = crypto_bucks + %s WHERE id = %s", (net_revenue, user_id))
        
        cursor.execute("""
            INSERT INTO transactions (user_id, wallet_id, coin_id, amount, price, type, sold_price, buy_transaction_id) 
            VALUES (%s, %s, %s, %s, %s, 'sell', %s, %s)
        """, (user_id, wallet_id, base_currency, amount, purchase_price, execution_price, buy_transaction_id))
        print(f"Sell transaction recorded. Added ${revenue} to balance")
    
    # Mark order as filled
    cursor.execute("""
        UPDATE orders SET status = 'filled', filled_amount = %s, filled_at = NOW() 
        WHERE id = %s
    """, (amount, order['id']))
    
    # Record order fill
    cursor.execute("""
        INSERT INTO order_fills (order_id, user_id, filled_amount, filled_price) 
        VALUES (%s, %s, %s, %s)
    """, (order['id'], user_id, amount, execution_price))
    
    print(f"Order #{order['id']} marked as filled")

# Start background scheduler
scheduler = BackgroundScheduler()
scheduler.add_job(check_price_alerts, 'interval', seconds=CHECK_INTERVAL)
scheduler.add_job(check_pending_orders, 'interval', seconds=CHECK_INTERVAL)
scheduler.start()

def calculate_risk_metrics(coin_ids, amounts, days=30):
    risk_free_rate = 0.02 / 365
    metrics = {}
    for coin_id, amount in zip(coin_ids, amounts):
        url = f"{COINGECKO_API}/coins/{coin_id}/market_chart?vs_currency=usd&days={days}"
        response = fetch_with_retry(url)
        if not response:
            print(f"Failed to fetch historical data for {coin_id}. Skipping risk metrics.")
            metrics[coin_id] = {'sharpe_ratio': 'N/A', 'volatility': 'N/A', 'max_drawdown': 'N/A'}
            continue
        data = json.loads(response.text)
        prices = [item[1] for item in data.get('prices', [])]
        if len(prices) < 2:
            print(f"Insufficient historical data for {coin_id}. Skipping risk metrics.")
            metrics[coin_id] = {'sharpe_ratio': 'N/A', 'volatility': 'N/A', 'max_drawdown': 'N/A'}
            continue
        returns = np.diff(prices) / prices[:-1]
        mean_return = np.mean(returns)
        std_return = np.std(returns) if len(returns) > 1 else 0
        sharpe_ratio = np.sqrt(365) * (mean_return - risk_free_rate) / std_return if std_return > 0 else 'N/A'
        volatility = std_return * np.sqrt(365) if std_return > 0 else 'N/A'
        cumulative = np.cumprod(1 + returns)
        peak = np.maximum.accumulate(cumulative)
        drawdown = (peak - cumulative) / peak
        max_drawdown = np.max(drawdown) if len(drawdown) > 0 else 'N/A'
        metrics[coin_id] = {
            'sharpe_ratio': round(sharpe_ratio, 2) if isinstance(sharpe_ratio, (int, float)) else 'N/A',
            'volatility': round(volatility, 4) if isinstance(volatility, (int, float)) else 'N/A',
            'max_drawdown': round(max_drawdown, 4) if isinstance(max_drawdown, (int, float)) else 'N/A'
        }
    return metrics

def calculate_correlation_matrix(coin_ids, days=30):
    if not coin_ids:
        return {'labels': [], 'matrix': []}
    prices_dict = {}
    for coin_id in coin_ids:
        url = f"{COINGECKO_API}/coins/{coin_id}/market_chart?vs_currency=usd&days={days}"
        response = fetch_with_retry(url)
        if response:
            data = json.loads(response.text)
            prices_dict[coin_id] = [item[1] for item in data.get('prices', [])]
        else:
            print(f"Failed to fetch historical data for {coin_id}. Excluding from correlation matrix.")
            prices_dict[coin_id] = []
    valid_coins = [coin_id for coin_id, prices in prices_dict.items() if len(prices) >= 2]
    if not valid_coins:
        return {'labels': coin_ids, 'matrix': []}
    min_length = min(len(prices) for coin_id, prices in prices_dict.items() if coin_id in valid_coins)
    if min_length < 2:
        return {'labels': valid_coins, 'matrix': []}
    df = pd.DataFrame({coin_id: prices[:min_length] for coin_id, prices in prices_dict.items() if coin_id in valid_coins})
    returns = df.pct_change().dropna()
    if returns.empty:
        return {'labels': valid_coins, 'matrix': []}
    corr_matrix = returns.corr().values.tolist()
    return {'labels': valid_coins, 'matrix': corr_matrix}

@app.route('/')
def index():
    if 'user_id' in session and session.get('expires_at', 0) > datetime.now().timestamp():
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if not username or not password:
            flash("Username and password are required", "error")
            return render_template('combined.html', section='login', user=None)
        conn = get_db_connection()
        if conn is None:
            flash("Database connection failed", "error")
            return render_template('combined.html', section='login', user=None)
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM users WHERE username = %s AND verified = 1", (username,))
            user = cursor.fetchone()
            if user and bcrypt.check_password_hash(user['password'], password):
                session['user_id'] = user['id']
                session['expires_at'] = (datetime.now() + timedelta(minutes=30)).timestamp()
                return redirect(url_for('dashboard'))
            flash("Invalid credentials or unverified account", "error")
        except mysql.connector.Error as err:
            flash(f"Database error: {err}", "error")
        finally:
            if conn.is_connected():
                cursor.close()
                conn.close()
        return render_template('combined.html', section='login', user=None)
    return render_template('combined.html', section='login', user=None)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        if not username or not email or not password:
            flash("All fields are required", "error")
            return render_template('combined.html', section='register', user=None)
        password = bcrypt.generate_password_hash(password).decode('utf-8')
        conn = get_db_connection()
        if conn is None:
            flash("Database connection failed", "error")
            return render_template('combined.html', section='register', user=None)
        try:
            cursor = conn.cursor()
            verification_code = generate_verification_code()
            cursor.execute("INSERT INTO users (username, email, password, verification_code, verified) VALUES (%s, %s, %s, %s, 0)", 
                          (username, email, password, verification_code))
            cursor.execute("UPDATE users SET achievements = '' WHERE email = %s", (email,))
            conn.commit()
            flash(f"Verification code sent to {email}. Please verify.", "info")
            return redirect(url_for('verify', email=email))
        except mysql.connector.Error as err:
            flash(f"Registration error: {err}", "error")
        finally:
            if conn.is_connected():
                cursor.close()
                conn.close()
        return render_template('combined.html', section='register', user=None)
    return render_template('combined.html', section='register', user=None)

@app.route('/verify/<email>', methods=['GET', 'POST'])
def verify(email):
    if request.method == 'POST':
        code = request.form.get('code')
        if not code:
            flash("Verification code is required", "error")
            return render_template('combined.html', section='verify', email=email, user=None)
        conn = get_db_connection()
        if conn is None:
            flash("Database connection failed", "error")
            return render_template('combined.html', section='verify', email=email, user=None)
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE email = %s AND verification_code = %s", (email, code))
            user = cursor.fetchone()
            if user:
                cursor.execute("UPDATE users SET verified = 1, verification_code = NULL WHERE email = %s", (email,))
                conn.commit()
                flash("Account verified! Please log in.", "success")
                return redirect(url_for('login'))
            flash("Invalid verification code.", "error")
        except mysql.connector.Error as err:
            flash(f"Database error: {err}", "error")
        finally:
            if conn.is_connected():
                cursor.close()
                conn.close()
        return render_template('combined.html', section='verify', email=email, user=None)
    return render_template('combined.html', section='verify', email=email, user=None)

@app.route('/risk_quiz', methods=['GET', 'POST'])
def risk_quiz():
    if 'user_id' not in session or session.get('expires_at', 0) < datetime.now().timestamp():
        return redirect(url_for('login'))

    blueprint = {
        'financial': {
            'label': 'Financial Capacity',
            'test': FINANCIAL_CAPACITY_TEST,
            'questions': FINANCIAL_CAPACITY_TEST['questions'][:5],
        },
        'knowledge': {
            'label': 'Investment Knowledge',
            'test': INVESTMENT_KNOWLEDGE_TEST,
            'questions': INVESTMENT_KNOWLEDGE_TEST['questions'][:5],
        },
        'psychological': {
            'label': 'Psychological Tolerance',
            'test': PSYCHOLOGICAL_TOLERANCE_TEST,
            'questions': PSYCHOLOGICAL_TOLERANCE_TEST['questions'][:5],
        },
        'goals': {
            'label': 'Goals & Timeline',
            'test': GOALS_TIMELINE_TEST,
            'questions': GOALS_TIMELINE_TEST['questions'][:5],
        },
    }

    questions = []
    for dim_key, cfg in blueprint.items():
        for q in cfg['questions']:
            normalized_options = []
            for opt in q['options']:
                normalized_options.append({
                    'value': int(opt['points']),
                    'text': opt['text'],
                    'explanation': f"Risk impact score: {int(opt['points'])}/10"
                })

            questions.append({
                'id': q['id'],
                'text': q['text'],
                'dimension': cfg['label'],
                'explanation': f"{cfg['label']} - {q.get('category', 'Assessment')}",
                'options': normalized_options
            })

    def _category_from_score(total_score):
        for category in RISK_CATEGORIES:
            low, high = category['range']
            if low <= total_score < high:
                return category
        return RISK_CATEGORIES[-1]

    def _dimension_score_for(dim_questions, response_map):
        max_points = sum(max(int(o['points']) for o in q['options']) for q in dim_questions)
        earned_points = sum(int(response_map.get(q['id'], 0)) for q in dim_questions)
        if max_points <= 0:
            return 0.0
        return round((earned_points / max_points) * 100, 2)
    
    if request.method == 'POST':
        try:
            responses = {}
            for question in questions:
                raw_value = request.form.get(question['id'])
                if raw_value is None:
                    raise ValueError("Missing response")
                responses[question['id']] = int(raw_value)

            financial_score = _dimension_score_for(blueprint['financial']['questions'], responses)
            knowledge_score = _dimension_score_for(blueprint['knowledge']['questions'], responses)
            psychological_score = _dimension_score_for(blueprint['psychological']['questions'], responses)
            goals_score = _dimension_score_for(blueprint['goals']['questions'], responses)

            total_score = round(
                financial_score * blueprint['financial']['test']['weight'] +
                knowledge_score * blueprint['knowledge']['test']['weight'] +
                psychological_score * blueprint['psychological']['test']['weight'] +
                goals_score * blueprint['goals']['test']['weight'],
                2
            )

            category = _category_from_score(total_score)
            risk_percent = int(round(total_score))

            allocation_lines = ''.join(
                f"<li><strong>{asset}:</strong> {allocation}</li>"
                for asset, allocation in category['allocation'].items()
            )
            recommendation = f"""
            <h4>Recommended Strategy:</h4>
            <p>{category['recommendation']}</p>
            <h5>Target Allocation</h5>
            <ul>
                {allocation_lines}
                <li><strong>Crypto:</strong> {category['crypto_allocation']}</li>
            </ul>
            """

            dimension_scores = {
                'financial': financial_score,
                'knowledge': knowledge_score,
                'psychological': psychological_score,
                'goals': goals_score,
            }

            strengths = [
                name for name, score in [
                    ('Financial Capacity', financial_score),
                    ('Investment Knowledge', knowledge_score),
                    ('Psychological Tolerance', psychological_score),
                    ('Goals & Timeline', goals_score),
                ] if score >= 70
            ]
            weak_areas = [
                name for name, score in [
                    ('Financial Capacity', financial_score),
                    ('Investment Knowledge', knowledge_score),
                    ('Psychological Tolerance', psychological_score),
                    ('Goals & Timeline', goals_score),
                ] if score < 50
            ]

            ai_analysis = {
                'summary': (
                    f"Comprehensive risk assessment completed. Overall profile: {category['level']} "
                    f"({total_score}%)."
                ),
                'strengths': strengths,
                'concerns': weak_areas,
                'recommendations': [
                    category['recommendation'],
                    f"Keep crypto exposure within {category['crypto_allocation']} of your total portfolio.",
                    "Re-run this assessment monthly to track risk understanding improvements.",
                ],
                'asset_allocation': category['allocation'],
                'crypto_advice': (
                    f"Maintain disciplined crypto sizing around {category['crypto_allocation']} "
                    "with strict stop-loss and position-size rules."
                ),
                'action_steps': [
                    "Document entry, stop, and target before every trade.",
                    "Review your last 10 trades and classify mistakes weekly.",
                    "Use smaller size until your weakest risk dimension improves above 60%.",
                ],
                'risk_management': [
                    "Set max risk per trade to 1-2% of account value.",
                    "Avoid increasing risk after losses.",
                    "Track win rate and average R-multiple every week.",
                ],
                'dimension_scores': dimension_scores,
            }

            conn = get_db_connection()
            if conn:
                try:
                    cursor = conn.cursor()

                    # Ensure comprehensive risk table exists.
                    cursor.execute("""
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
                            INDEX idx_user_completed (user_id, completed_at)
                        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                    """)

                    cursor.execute("""
                        INSERT INTO risk_assessments (
                            user_id, financial_score, knowledge_score,
                            psychological_score, goals_score, total_score,
                            risk_category, responses, ai_analysis, completed_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        session['user_id'],
                        financial_score,
                        knowledge_score,
                        psychological_score,
                        goals_score,
                        total_score,
                        category['level'],
                        json.dumps(responses),
                        json.dumps(ai_analysis),
                        datetime.now(),
                    ))

                    cursor.execute("""
                        UPDATE users 
                        SET risk_tolerance = %s, risk_score = %s 
                        WHERE id = %s
                    """, (category['level'], int(round(total_score)), session['user_id']))
                    conn.commit()

                    cursor.execute("""
                        SELECT total_score, completed_at
                        FROM risk_assessments
                        WHERE user_id = %s
                        ORDER BY completed_at DESC
                        LIMIT 8
                    """, (session['user_id'],))
                    history_rows = cursor.fetchall() or []

                    trend_labels = []
                    trend_scores = []
                    for row in reversed(history_rows):
                        score_idx = 0
                        date_idx = 1
                        trend_scores.append(float(row[score_idx] or 0))
                        dt_val = row[date_idx]
                        trend_labels.append(dt_val.strftime('%b %d') if hasattr(dt_val, 'strftime') else 'Snapshot')

                    return render_template(
                        'combined.html',
                        section='risk_quiz_result',
                        risk_level=category['level'],
                        risk_percent=risk_percent,
                        score=total_score,
                        max_score=100,
                        recommendation=recommendation,
                        dimension_scores=dimension_scores,
                        trend_labels=trend_labels,
                        trend_scores=trend_scores,
                        risk_category=category,
                    )
                    
                except mysql.connector.Error as err:
                    flash(f"Database error: {err}", "error")
                    return redirect(url_for('risk_quiz'))
                finally:
                    if conn.is_connected():
                        cursor.close()
                        conn.close()
            return redirect(url_for('dashboard'))
            
        except ValueError as e:
            flash("Invalid input. Please answer all assessment questions.", "error")
            return redirect(url_for('risk_quiz'))
    
    # GET request - show the quiz
    return render_template(
        'combined.html',
        section='risk_quiz',
        questions=questions,
        risk_question_count=len(questions),
        risk_dimension_count=len(blueprint),
        estimated_minutes=8,
    )

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session or session.get('expires_at', 0) < datetime.now().timestamp():
        return redirect(url_for('login'))
    coins = []
    response = fetch_with_retry(f"{COINGECKO_API}/coins/markets?vs_currency=usd&ids=bitcoin,ethereum,binancecoin,tether")
    if response:
        coins = json.loads(response.text)
    else:
        flash("Failed to fetch market data. Please try again later.", "error")
    conn = get_db_connection()
    user = None
    triggered_alerts = []
    sold_transactions = []
    risk_analytics = {
        'available': False,
        'latest_score': 0,
        'risk_category': '',
        'financial_score': 0,
        'knowledge_score': 0,
        'psychological_score': 0,
        'goals_score': 0,
        'trend_labels': [],
        'trend_scores': [],
        'last_updated': None,
    }
    dashboard_metrics = {
        'total': 0,
        'wins': 0,
        'avg_pl': 0.0,
        'best': 0.0,
    }
    dashboard_analytics = {
        'portfolio_total': 0.0,
        'portfolio_change_pct_7d': 0.0,
        'portfolio_trend_labels': [],
        'portfolio_trend_values': [],
        'allocation': {
            'btc': 0.0,
            'eth': 0.0,
            'usdt': 0.0,
            'other': 0.0,
        },
        'trade_volume_total': 0.0,
        'trade_volume_window_label': '24h',
        'trade_volume_bars': [0, 0, 0, 0, 0, 0],
    }

    def safe_float(value, default=0.0):
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT crypto_bucks, tether_balance, risk_tolerance, risk_score, achievements FROM users WHERE id = %s", (session['user_id'],))
            user = cursor.fetchone()
            if user:
                user['crypto_bucks'] = safe_float(user.get('crypto_bucks', 0))
                user['tether_balance'] = safe_float(user.get('tether_balance', 0))
                dashboard_analytics['portfolio_total'] = round(user['crypto_bucks'] + user['tether_balance'], 2)
            cursor.execute("""
                SELECT n.id, n.coin_id, n.message, n.created_at, pa.alert_type, pa.target_price 
                FROM notifications n
                JOIN price_alerts pa ON n.coin_id = pa.coin_id AND n.user_id = pa.user_id
                WHERE n.user_id = %s AND n.is_read = 0 
                ORDER BY n.created_at DESC
            """, (session['user_id'],))
            notifications = cursor.fetchall()
            if notifications:
                coin_ids = ','.join(set(n['coin_id'] for n in notifications))
                response = fetch_with_retry(f"{COINGECKO_API}/coins/markets?vs_currency=usd&ids={coin_ids}")
                if response:
                    prices = {coin['id']: coin['current_price'] for coin in json.loads(response.text)}
                    for notification in notifications:
                        notification['current_price'] = prices.get(notification['coin_id'], 0)
                        notification['triggered_at'] = notification['created_at'].strftime('%Y-%m-%d %H:%M:%S')
                        if 'alert_type' not in notification:
                            notification['alert_type'] = 'above' if 'above' in notification['message'].lower() else 'below'
                        if 'target_price' not in notification:
                            import re
                            match = re.search(r'\$([\d.]+)', notification['message'])
                            if match:
                                notification['target_price'] = float(match.group(1))
                        triggered_alerts.append(notification)

            # Archived trades shown on dashboard right panel
            cursor.execute(
                """
                SELECT wallet_id, coin_id, amount, price, sold_price, timestamp
                FROM transactions
                WHERE user_id = %s AND type = 'sell'
                ORDER BY timestamp DESC
                LIMIT 12
                """,
                (session['user_id'],)
            )
            sold_transactions = cursor.fetchall()
            for tx in sold_transactions:
                tx['price'] = safe_float(tx.get('price'))
                tx['sold_price'] = safe_float(tx.get('sold_price'))
                tx['amount'] = safe_float(tx.get('amount'))
                tx['profit'] = round((tx['sold_price'] - tx['price']) * tx['amount'], 2)

            # Account metrics and portfolio trend (based on realized P/L over the latest 7 days).
            cursor.execute(
                """
                SELECT coin_id, amount, price, sold_price, timestamp
                FROM transactions
                WHERE user_id = %s AND type = 'sell'
                ORDER BY timestamp ASC
                """,
                (session['user_id'],)
            )
            all_sold_transactions = cursor.fetchall() or []

            if all_sold_transactions:
                total_pl = 0.0
                best_pl = None
                wins = 0
                for tx in all_sold_transactions:
                    amount = safe_float(tx.get('amount'))
                    buy_price = safe_float(tx.get('price'))
                    sell_price = safe_float(tx.get('sold_price'))
                    pl = (sell_price - buy_price) * amount
                    total_pl += pl
                    if pl > 0:
                        wins += 1
                    if best_pl is None or pl > best_pl:
                        best_pl = pl

                total_trades = len(all_sold_transactions)
                dashboard_metrics['total'] = total_trades
                dashboard_metrics['wins'] = wins
                dashboard_metrics['avg_pl'] = round(total_pl / total_trades, 2) if total_trades else 0.0
                dashboard_metrics['best'] = round(best_pl if best_pl is not None else 0.0, 2)

            today = datetime.now().date()
            trend_dates = [today - timedelta(days=i) for i in range(6, -1, -1)]
            daily_realized = {d: 0.0 for d in trend_dates}
            for tx in all_sold_transactions:
                timestamp_value = tx.get('timestamp')
                if not timestamp_value:
                    continue
                day_key = timestamp_value.date()
                if day_key in daily_realized:
                    amount = safe_float(tx.get('amount'))
                    buy_price = safe_float(tx.get('price'))
                    sell_price = safe_float(tx.get('sold_price'))
                    daily_realized[day_key] += (sell_price - buy_price) * amount

            pnl_7d = sum(daily_realized.values())
            current_total = dashboard_analytics['portfolio_total']
            baseline_total = current_total - pnl_7d
            running_total = baseline_total
            trend_values = []
            for d in trend_dates:
                running_total += daily_realized[d]
                trend_values.append(round(running_total, 2))

            dashboard_analytics['portfolio_trend_labels'] = [d.strftime('%b %d') for d in trend_dates]
            dashboard_analytics['portfolio_trend_values'] = trend_values
            if baseline_total > 0:
                dashboard_analytics['portfolio_change_pct_7d'] = round((pnl_7d / baseline_total) * 100, 2)

            # Asset allocation from active holdings + balances.
            cursor.execute(
                """
                SELECT id, coin_id, amount, price
                FROM transactions
                WHERE user_id = %s AND type = 'buy'
                ORDER BY id ASC
                """,
                (session['user_id'],)
            )
            buy_transactions = cursor.fetchall() or []

            cursor.execute(
                """
                SELECT buy_transaction_id, SUM(amount) as total_sold
                FROM transactions
                WHERE user_id = %s AND type = 'sell' AND buy_transaction_id IS NOT NULL
                GROUP BY buy_transaction_id
                """,
                (session['user_id'],)
            )
            sold_amount_rows = cursor.fetchall() or []
            sold_amounts = {row['buy_transaction_id']: safe_float(row.get('total_sold')) for row in sold_amount_rows}

            holdings_amounts = {}
            for buy in buy_transactions:
                buy_id = buy.get('id')
                coin_id = (buy.get('coin_id') or '').lower()
                if not coin_id:
                    continue
                remaining = safe_float(buy.get('amount')) - sold_amounts.get(buy_id, 0.0)
                if remaining > 0:
                    holdings_amounts[coin_id] = holdings_amounts.get(coin_id, 0.0) + remaining

            holdings_values = {}
            if holdings_amounts:
                coin_ids = ','.join(sorted(holdings_amounts.keys()))
                holdings_response = fetch_with_retry(
                    f"{COINGECKO_API}/coins/markets?vs_currency=usd&ids={coin_ids}"
                )
                if holdings_response:
                    holdings_data = json.loads(holdings_response.text)
                    market_prices = {
                        item.get('id'): safe_float(item.get('current_price'))
                        for item in holdings_data
                    }
                    for coin_id, amount in holdings_amounts.items():
                        holdings_values[coin_id] = amount * market_prices.get(coin_id, 0.0)

            btc_value = holdings_values.get('bitcoin', 0.0)
            eth_value = holdings_values.get('ethereum', 0.0)
            usdt_value = user['tether_balance'] if user else 0.0
            other_coin_value = sum(
                value for coin_id, value in holdings_values.items()
                if coin_id not in ('bitcoin', 'ethereum', 'tether')
            )
            if 'tether' in holdings_values:
                usdt_value += holdings_values.get('tether', 0.0)
            other_value = (user['crypto_bucks'] if user else 0.0) + other_coin_value

            allocation_total = btc_value + eth_value + usdt_value + other_value
            if allocation_total > 0:
                dashboard_analytics['allocation']['btc'] = round((btc_value / allocation_total) * 100, 1)
                dashboard_analytics['allocation']['eth'] = round((eth_value / allocation_total) * 100, 1)
                dashboard_analytics['allocation']['usdt'] = round((usdt_value / allocation_total) * 100, 1)
                dashboard_analytics['allocation']['other'] = round((other_value / allocation_total) * 100, 1)

            # Trade volume bars (prefer last 24h; fallback to last 30d if 24h is empty).
            cursor.execute(
                """
                SELECT amount, price, sold_price, type, timestamp
                FROM transactions
                WHERE user_id = %s AND timestamp >= (NOW() - INTERVAL 24 HOUR)
                ORDER BY timestamp ASC
                """,
                (session['user_id'],)
            )
            recent_transactions = cursor.fetchall() or []

            def compute_volume_bars(rows, window_start, bucket_seconds):
                bar_values = [0.0] * 6
                for tx in rows:
                    ts = tx.get('timestamp')
                    if not ts:
                        continue
                    elapsed_seconds = max(0, (ts - window_start).total_seconds())
                    bucket_index = min(5, int(elapsed_seconds // bucket_seconds))

                    amount = safe_float(tx.get('amount'))
                    if (tx.get('type') or '').lower() == 'sell' and tx.get('sold_price') is not None:
                        unit_price = safe_float(tx.get('sold_price'))
                    else:
                        unit_price = safe_float(tx.get('price'))

                    bar_values[bucket_index] += max(0.0, amount * unit_price)

                total_value = sum(bar_values)
                max_bar = max(bar_values) if bar_values else 0.0
                normalized = [0.0] * 6
                if max_bar > 0:
                    normalized = [round((value / max_bar) * 100, 1) for value in bar_values]
                return normalized, round(total_value, 2)

            if recent_transactions:
                bars, total_value = compute_volume_bars(
                    recent_transactions,
                    datetime.now() - timedelta(hours=24),
                    4 * 60 * 60,
                )
                dashboard_analytics['trade_volume_bars'] = bars
                dashboard_analytics['trade_volume_total'] = total_value

            if not recent_transactions or dashboard_analytics['trade_volume_total'] <= 0:
                cursor.execute(
                    """
                    SELECT amount, price, sold_price, type, timestamp
                    FROM transactions
                    WHERE user_id = %s AND timestamp >= (NOW() - INTERVAL 30 DAY)
                    ORDER BY timestamp ASC
                    """,
                    (session['user_id'],)
                )
                month_transactions = cursor.fetchall() or []
                if month_transactions:
                    bars, total_value = compute_volume_bars(
                        month_transactions,
                        datetime.now() - timedelta(days=30),
                        5 * 24 * 60 * 60,
                    )
                    dashboard_analytics['trade_volume_bars'] = bars
                    dashboard_analytics['trade_volume_total'] = total_value
                    dashboard_analytics['trade_volume_window_label'] = '30d'

            try:
                cursor.execute("""
                    SELECT financial_score, knowledge_score, psychological_score, goals_score,
                           total_score, risk_category, completed_at
                    FROM risk_assessments
                    WHERE user_id = %s
                    ORDER BY completed_at DESC
                    LIMIT 10
                """, (session['user_id'],))
                assessments = cursor.fetchall() or []

                if assessments:
                    latest = assessments[0]
                    risk_analytics['available'] = True
                    risk_analytics['latest_score'] = float(latest.get('total_score') or 0)
                    risk_analytics['risk_category'] = latest.get('risk_category') or ''
                    risk_analytics['financial_score'] = float(latest.get('financial_score') or 0)
                    risk_analytics['knowledge_score'] = float(latest.get('knowledge_score') or 0)
                    risk_analytics['psychological_score'] = float(latest.get('psychological_score') or 0)
                    risk_analytics['goals_score'] = float(latest.get('goals_score') or 0)
                    risk_analytics['last_updated'] = latest.get('completed_at')

                    trend_labels = []
                    trend_scores = []
                    for row in reversed(assessments):
                        completed_at = row.get('completed_at')
                        trend_labels.append(completed_at.strftime('%b %d') if completed_at else 'N/A')
                        trend_scores.append(float(row.get('total_score') or 0))

                    risk_analytics['trend_labels'] = trend_labels
                    risk_analytics['trend_scores'] = trend_scores
            except mysql.connector.Error:
                # Risk table may not exist in some environments yet.
                pass
        except mysql.connector.Error as err:
            flash(f"Database error: {err}", "error")
        finally:
            if conn.is_connected():
                cursor.close()
                conn.close()
    return render_template(
        'combined.html',
        section='dashboard',
        coins=coins,
        user=user,
        triggered_alerts=triggered_alerts,
        sold_transactions=sold_transactions,
        risk_analytics=risk_analytics,
        dashboard_metrics=dashboard_metrics,
        dashboard_analytics=dashboard_analytics,
        next_check_seconds=CHECK_INTERVAL
    )

@app.route('/dismiss_alert/<int:notification_id>', methods=['POST'])
def dismiss_alert(notification_id):
    if 'user_id' not in session or session.get('expires_at', 0) < datetime.now().timestamp():
        return redirect(url_for('login'))
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("UPDATE notifications SET is_read = 1 WHERE id = %s AND user_id = %s", (notification_id, session['user_id']))
            conn.commit()
            flash("Alert dismissed.", "success")
        except mysql.connector.Error as err:
            flash(f"Database error: {err}", "error")
        finally:
            if conn.is_connected():
                cursor.close()
                conn.close()
    return redirect(url_for('dashboard'))

@app.route('/trade_from_alert', methods=['POST'])
def trade_from_alert():
    if 'user_id' not in session or session.get('expires_at', 0) < datetime.now().timestamp():
        return redirect(url_for('login'))
    coin_id = request.form.get('coin_id')
    current_price = float(request.form.get('current_price', 0))
    return redirect(url_for('live_market', coin_id=coin_id, current_price=current_price))

@app.route('/refresh_alerts', methods=['POST'])
def refresh_alerts():
    if 'user_id' not in session or session.get('expires_at', 0) < datetime.now().timestamp():
        return redirect(url_for('login'))
    check_price_alerts()
    flash("Alerts refreshed.", "success")
    return redirect(url_for('dashboard'))

@app.route('/live_market')
def live_market():
    if 'user_id' not in session or session.get('expires_at', 0) < datetime.now().timestamp():
        return redirect(url_for('login'))

    def safe_float(value, default=0.0):
        """Coerce possibly-null/non-numeric API values into floats for template safety."""
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def safe_int(value, default=0):
        """Coerce possibly-null/non-numeric API values into ints for template safety."""
        try:
            return int(value)
        except (TypeError, ValueError):
            return default
    page = int(request.args.get('page', 1))
    coins = []
    response = fetch_with_retry(f"{COINGECKO_API}/coins/markets?vs_currency=usd&order=market_cap_desc&per_page={COINS_PER_PAGE}&page={page}&sparkline=false")
    if response:
        coins = json.loads(response.text)
        # Enhance each coin with 24h high/low data
        for coin in coins:
            coin['current_price'] = safe_float(coin.get('current_price'))
            coin['price_change_percentage_24h'] = safe_float(coin.get('price_change_percentage_24h'))
            coin['market_cap'] = safe_int(coin.get('market_cap'))
            coin['high_24h'] = safe_float(coin.get('high_24h'))
            coin['low_24h'] = safe_float(coin.get('low_24h'))
            coin['total_volume'] = safe_float(coin.get('total_volume'))
    else:
        flash("Failed to fetch live market data. Using cached data if available.", "warning")
    total_coins = 1000
    total_pages = (total_coins + COINS_PER_PAGE - 1) // COINS_PER_PAGE
    conn = get_db_connection()
    user_wallets = []
    user_balances = {'crypto_bucks': 0, 'tether': 0}
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT id, name FROM wallets WHERE user_id = %s", (session['user_id'],))
            user_wallets = cursor.fetchall()
            if not user_wallets:
                cursor.execute("INSERT INTO wallets (user_id, name) VALUES (%s, %s)", 
                              (session['user_id'], 'Default Wallet'))
                conn.commit()
                cursor.execute("SELECT id, name FROM wallets WHERE user_id = %s", (session['user_id'],))
                user_wallets = cursor.fetchall()
            
            # Get user balances
            cursor.execute("SELECT crypto_bucks, tether_balance FROM users WHERE id = %s", (session['user_id'],))
            user = cursor.fetchone()
            if user:
                user_balances['crypto_bucks'] = float(user['crypto_bucks'])
                user_balances['tether'] = float(user.get('tether_balance', 0))
        except mysql.connector.Error as err:
            flash(f"Database error: {err}", "error")
        finally:
            if conn.is_connected():
                cursor.close()
                conn.close()
    return render_template('combined.html', section='live_market', coins=coins, wallets=user_wallets, 
                         page=page, total_pages=total_pages, user_balances=user_balances)

@app.route('/trade', methods=['POST'])
def trade():
    if 'user_id' not in session or session.get('expires_at', 0) < datetime.now().timestamp():
        return redirect(url_for('login'))
    
    coin_id = request.form.get('coin_id', '').lower()
    amount = request.form.get('amount')
    current_price = request.form.get('current_price')
    wallet_id = request.form.get('wallet_id')
    action = request.form.get('action')  # 'buy' or 'sell'
    order_type = request.form.get('order_type', 'market')  # 'market', 'limit', 'stop_loss', 'take_profit'
    limit_price = request.form.get('limit_price')  # For limit orders
    stop_price = request.form.get('stop_price')  # For stop_loss/take_profit
    quote_currency = request.form.get('quote_currency', 'cryptobucks')  # Default to CryptoBucks
    source = request.form.get('source', 'live_market')
    
    if not all([coin_id, amount, wallet_id, action]) or action not in ['buy', 'sell']:
        flash("All fields are required", "error")
        return redirect(url_for(source))
    
    try:
        amount = float(amount)
        wallet_id = int(wallet_id)
        if current_price:
            current_price = float(current_price)
        # Convert empty strings to None for database NULL
        if limit_price and limit_price.strip():
            limit_price = float(limit_price)
        else:
            limit_price = None
        if stop_price and stop_price.strip():
            stop_price = float(stop_price)
        else:
            stop_price = None
    except ValueError:
        flash("Invalid amount, price, or wallet", "error")
        return redirect(url_for(source))
    
    if amount <= 0:
        flash("Amount must be positive", "error")
        return redirect(url_for(source))
    
    conn = get_db_connection()
    if conn is None:
        flash("Database connection failed", "error")
        return redirect(url_for(source))
    
    try:
        cursor = conn.cursor(dictionary=True)
        
        # Handle MARKET orders - execute immediately
        if order_type == 'market':
            if not current_price or current_price <= 0:
                flash("Current price is required for market orders", "error")
                return redirect(url_for(source))
            
            if action == 'buy':
                # Determine which currency to use for payment
                if coin_id == 'tether':
                    # Buying USDT with CryptoBucks
                    cursor.execute("SELECT crypto_bucks FROM users WHERE id = %s", (session['user_id'],))
                    balance = float(cursor.fetchone()['crypto_bucks'])
                    total_cost = amount * current_price
                    trading_fee = total_cost * 0.001  # 0.1% fee
                    total_with_fee = total_cost + trading_fee
                    
                    if total_with_fee > balance:
                        flash(f"Insufficient CryptoBucks. Need ${total_with_fee:.2f} (includes ${trading_fee:.2f} fee)", "error")
                        return redirect(url_for(source))
                    
                    cursor.execute("UPDATE users SET crypto_bucks = crypto_bucks - %s, tether_balance = tether_balance + %s WHERE id = %s", 
                                 (total_with_fee, amount, session['user_id']))
                    flash(f"Successfully bought {amount} USDT (Fee: ${trading_fee:.2f})", "success")
                
                elif quote_currency == 'tether':
                    # Buying crypto with USDT
                    cursor.execute("SELECT tether_balance FROM users WHERE id = %s", (session['user_id'],))
                    tether_balance = float(cursor.fetchone()['tether_balance'])
                    total_cost = amount * current_price
                    trading_fee = total_cost * 0.001  # 0.1% fee
                    total_with_fee = total_cost + trading_fee
                    
                    if total_with_fee > tether_balance:
                        flash(f"Insufficient USDT. Need ${total_with_fee:.2f} (includes ${trading_fee:.2f} fee)", "error")
                        return redirect(url_for(source))
                    
                    cursor.execute("UPDATE users SET tether_balance = tether_balance - %s WHERE id = %s", 
                                 (total_with_fee, session['user_id']))
                    cursor.execute("INSERT INTO transactions (user_id, wallet_id, coin_id, amount, price, type) VALUES (%s, %s, %s, %s, %s, %s)",
                                 (session['user_id'], wallet_id, coin_id, amount, current_price, 'buy'))
                    flash(f"Successfully bought {amount} {coin_id} (Fee: ${trading_fee:.2f})", "success")
                
                else:
                    # Buying crypto with CryptoBucks (legacy)
                    cursor.execute("SELECT crypto_bucks FROM users WHERE id = %s", (session['user_id'],))
                    crypto_bucks = float(cursor.fetchone()['crypto_bucks'])
                    total_cost = amount * current_price
                    trading_fee = total_cost * 0.001  # 0.1% fee
                    total_with_fee = total_cost + trading_fee
                    
                    if total_with_fee > crypto_bucks:
                        flash(f"Insufficient CryptoBucks. Need ${total_with_fee:.2f} (includes ${trading_fee:.2f} fee)", "error")
                        return redirect(url_for(source))
                    
                    cursor.execute("UPDATE users SET crypto_bucks = crypto_bucks - %s WHERE id = %s", 
                                 (total_with_fee, session['user_id']))
                    cursor.execute("INSERT INTO transactions (user_id, wallet_id, coin_id, amount, price, type) VALUES (%s, %s, %s, %s, %s, %s)",
                                 (session['user_id'], wallet_id, coin_id, amount, current_price, 'buy'))
                    flash(f"Successfully bought {amount} {coin_id} (Fee: ${trading_fee:.2f})", "success")
            
            elif action == 'sell':
                buy_transaction_id = request.form.get('buy_transaction_id')
                if not buy_transaction_id:
                    flash("Missing buy transaction ID", "error")
                    return redirect(url_for(source))
                
                try:
                    buy_transaction_id = int(buy_transaction_id)
                except ValueError:
                    flash("Invalid buy transaction ID", "error")
                    return redirect(url_for(source))
                
                cursor.execute(
                    "SELECT amount, price FROM transactions WHERE id = %s AND user_id = %s AND wallet_id = %s AND coin_id = %s AND type = 'buy'",
                    (buy_transaction_id, session['user_id'], wallet_id, coin_id)
                )
                buy = cursor.fetchone()
                if not buy:
                    flash("Invalid buy transaction", "error")
                    return redirect(url_for(source))
                
                cursor.execute(
                    "SELECT SUM(amount) as total_sold FROM transactions WHERE user_id = %s AND type = 'sell' AND buy_transaction_id = %s",
                    (session['user_id'], buy_transaction_id)
                )
                already_sold = float(cursor.fetchone()['total_sold'] or 0)
                available = float(buy['amount']) - already_sold
                
                if amount > available:
                    flash("Insufficient coin amount to sell", "error")
                    return redirect(url_for(source))
                
                purchase_price = float(buy['price'])
                revenue = amount * current_price
                trading_fee = revenue * 0.001  # 0.1% fee
                net_revenue = revenue - trading_fee
                
                # Credit USDT or CryptoBucks based on quote_currency
                if quote_currency == 'tether':
                    cursor.execute("UPDATE users SET tether_balance = tether_balance + %s WHERE id = %s", 
                                 (net_revenue, session['user_id']))
                else:
                    cursor.execute("UPDATE users SET crypto_bucks = crypto_bucks + %s WHERE id = %s", 
                                 (net_revenue, session['user_id']))
                
                cursor.execute(
                    "INSERT INTO transactions (user_id, wallet_id, coin_id, amount, price, type, sold_price, buy_transaction_id) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                    (session['user_id'], wallet_id, coin_id, amount, purchase_price, 'sell', current_price, buy_transaction_id)
                )
                profit = (current_price - purchase_price) * amount
                net_profit = profit - trading_fee
                flash(f"Successfully sold {amount} {coin_id} (Profit: ${profit:.2f}, Fee: ${trading_fee:.2f}, Net: ${net_profit:.2f})", "success")
        
        # Handle LIMIT, STOP_LOSS, TAKE_PROFIT orders - save for later execution
        else:
            if order_type == 'limit' and (limit_price is None or limit_price <= 0):
                flash("Limit price is required for limit orders", "error")
                return redirect(url_for(source))
            
            if order_type in ['stop_loss', 'take_profit'] and (stop_price is None or stop_price <= 0):
                flash("Stop price is required for stop loss/take profit orders", "error")
                return redirect(url_for(source))

            # Prevent accidental instant fills: validate trigger direction against current market price.
            if order_type == 'limit' and current_price and current_price > 0:
                if action == 'buy' and limit_price >= current_price:
                    flash(
                        f"Limit buy must be below current market price (${current_price:.4f}). "
                        "Set a lower limit price or use a market buy.",
                        "error"
                    )
                    return redirect(url_for(source))
                if action == 'sell' and limit_price <= current_price:
                    flash(
                        f"Limit sell must be above current market price (${current_price:.4f}). "
                        "Set a higher limit price or use a market sell.",
                        "error"
                    )
                    return redirect(url_for(source))

            # Current execution engine supports stop/take-profit on sell side only.
            if order_type in ['stop_loss', 'take_profit'] and action != 'sell':
                flash(
                    f"{order_type.replace('_', ' ').title()} is currently supported for sell orders only.",
                    "error"
                )
                return redirect(url_for(source))
            
            # Get trading pair ID
            cursor.execute(
                "SELECT id FROM trading_pairs WHERE base_currency = %s AND quote_currency = %s",
                (coin_id, quote_currency)
            )
            pair = cursor.fetchone()
            pair_id = pair['id'] if pair else None
            
            # Create pending order
            cursor.execute("""
                INSERT INTO orders (user_id, wallet_id, pair_id, base_currency, quote_currency, 
                                  order_type, side, amount, price, stop_price, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending')
            """, (session['user_id'], wallet_id, pair_id, coin_id, quote_currency, 
                  order_type, action, amount, limit_price, stop_price))
            
            flash(f"{order_type.replace('_', ' ').title()} order placed successfully", "success")
        
        conn.commit()
    except mysql.connector.Error as err:
        flash(f"Database error: {err}", "error")
        conn.rollback()
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()
    
    return redirect(url_for(source))

@app.route('/portfolio', methods=['GET', 'POST'])
def portfolio():
    if 'user_id' not in session or session.get('expires_at', 0) < datetime.now().timestamp():
        return redirect(url_for('login'))
    if request.method == 'POST':
        coin_id = request.form.get('coin_id', '').lower()
        amount = request.form.get('amount')
        purchase_price = request.form.get('purchase_price')
        wallet_id = request.form.get('wallet_id')
        if not all([coin_id, amount, purchase_price, wallet_id]):
            flash("All fields are required", "error")
            return redirect(url_for('portfolio'))
        try:
            amount = float(amount)
            purchase_price = float(purchase_price)
            wallet_id = int(wallet_id)
        except ValueError:
            flash("Invalid amount, purchase price, or wallet", "error")
            return redirect(url_for('portfolio'))
        conn = get_db_connection()
        if conn:
            try:
                cursor = conn.cursor(dictionary=True)
                cursor.execute("SELECT id FROM wallets WHERE user_id = %s AND id = %s", (session['user_id'], wallet_id))
                if not cursor.fetchone():
                    flash("Invalid wallet", "error")
                    return redirect(url_for('portfolio'))
                cursor.execute("SELECT crypto_bucks FROM users WHERE id = %s", (session['user_id'],))
                crypto_bucks = float(cursor.fetchone()['crypto_bucks'])
                total_cost = amount * purchase_price
                if total_cost <= crypto_bucks and amount > 0 and purchase_price > 0:
                    cursor.execute("UPDATE users SET crypto_bucks = crypto_bucks - %s WHERE id = %s", (total_cost, session['user_id']))
                    cursor.execute("INSERT INTO transactions (user_id, wallet_id, coin_id, amount, price, type) VALUES (%s, %s, %s, %s, %s, 'buy')",
                                 (session['user_id'], wallet_id, coin_id, amount, purchase_price))
                    conn.commit()
                    flash("Transaction added successfully", "success")
                else:
                    flash("Insufficient CryptoBucks or invalid input", "error")
            except mysql.connector.Error as err:
                flash(f"Database error: {err}", "error")
            finally:
                if conn.is_connected():
                    cursor.close()
                    conn.close()
    conn = get_db_connection()
    sold_transactions = []
    all_transactions = []
    total_profit = 0.0
    total_unrealized_profit = 0.0
    current_prices = {}
    risk_metrics = {}
    transactions = []
    grouped_holdings = {}
    user_wallets = []
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT id, name FROM wallets WHERE user_id = %s", (session['user_id'],))
            user_wallets = cursor.fetchall()
            
            # Get all transactions for trade history
            cursor.execute("SELECT * FROM transactions WHERE user_id = %s ORDER BY id DESC", (session['user_id'],))
            all_transactions = cursor.fetchall()
            
            # Process all transactions to ensure proper data types
            for transaction in all_transactions:
                transaction['price'] = float(transaction['price'] or 0)
                transaction['sold_price'] = float(transaction.get('sold_price') or 0)
                transaction['amount'] = float(transaction['amount'] or 0)
                transaction['formatted_date'] = f"Transaction #{transaction['id']}"  # Fallback since no created_at column
                
                # Calculate fee for each transaction
                if transaction['type'] == 'buy':
                    transaction['fee'] = transaction['amount'] * transaction['price'] * 0.001
                else:
                    transaction['fee'] = transaction['amount'] * transaction['sold_price'] * 0.001
            
            cursor.execute("SELECT * FROM transactions WHERE user_id = %s AND type = 'sell'", (session['user_id'],))
            sold_transactions = cursor.fetchall()
            for transaction in sold_transactions:
                transaction['price'] = float(transaction['price'] or 0)
                transaction['sold_price'] = float(transaction['sold_price'] or 0)
                transaction['amount'] = float(transaction['amount'] or 0)
                profit = (transaction['sold_price'] - transaction['price']) * transaction['amount']
                transaction['profit'] = round(profit, 2)
                total_profit += profit
            cursor.execute("SELECT id, wallet_id, coin_id, amount, price FROM transactions WHERE user_id = %s AND type = 'buy' ORDER BY id ASC",
                          (session['user_id'],))
            buy_transactions = cursor.fetchall()
            sold_amounts = {}
            cursor.execute("SELECT buy_transaction_id, SUM(amount) as total_sold FROM transactions WHERE user_id = %s AND type = 'sell' GROUP BY buy_transaction_id",
                          (session['user_id'],))
            for row in cursor.fetchall():
                sold_amounts[row['buy_transaction_id']] = float(row['total_sold'])
            
            # Build individual transactions and group by coin for average price
            for buy in buy_transactions:
                buy_id = buy['id']
                total_bought = float(buy['amount'] or 0)
                total_sold = sold_amounts.get(buy_id, 0.0)
                remaining_amount = total_bought - total_sold
                if remaining_amount > 0:
                    coin_id = buy['coin_id']
                    price = float(buy['price'] or 0)
                    
                    transactions.append({
                        'wallet_id': buy['wallet_id'],
                        'coin_id': coin_id,
                        'amount': remaining_amount,
                        'price': price,
                        'buy_transaction_id': buy_id
                    })
                    
                    # Group by coin for average buy price calculation
                    if coin_id not in grouped_holdings:
                        grouped_holdings[coin_id] = {
                            'coin_id': coin_id,
                            'total_amount': 0,
                            'total_cost': 0
                        }
                    grouped_holdings[coin_id]['total_amount'] += remaining_amount
                    grouped_holdings[coin_id]['total_cost'] += remaining_amount * price
        except mysql.connector.Error as err:
            flash(f"Database error: {err}", "error")
        finally:
            if conn.is_connected():
                cursor.close()
                conn.close()
    coin_ids = list(set(t['coin_id'] for t in transactions + sold_transactions))
    amounts = [t['amount'] for t in transactions if t['coin_id'] in coin_ids]
    if coin_ids:
        risk_metrics = calculate_risk_metrics(coin_ids, amounts)
    correlation_data = calculate_correlation_matrix(coin_ids)
    coin_ids_str = ','.join(coin_ids) or 'bitcoin'
    response = fetch_with_retry(f"{COINGECKO_API}/coins/markets?vs_currency=usd&ids={coin_ids_str}")
    if response:
        data = json.loads(response.text)
        current_prices = {coin['id']: float(coin['current_price']) for coin in data if 'current_price' in coin}
    else:
        flash("Failed to fetch current prices. Using cached data if available.", "warning")
        cached_url = f"{COINGECKO_API}/coins/markets?vs_currency=usd&ids={coin_ids_str}"
        if cached_url in api_cache:
            cached_data, _ = api_cache[cached_url]
            current_prices = {coin['id']: float(coin['current_price']) for coin in cached_data if 'current_price' in coin}
        else:
            current_prices = {coin_id: 0.0 for coin_id in coin_ids}
    
    # Calculate average buy price and unrealized P/L for grouped holdings
    total_fees_paid = sum(t['fee'] for t in all_transactions)
    
    for coin_id, holding in grouped_holdings.items():
        if holding['total_amount'] > 0:
            holding['avg_buy_price'] = holding['total_cost'] / holding['total_amount']
        else:
            holding['avg_buy_price'] = 0
        
        current_price = current_prices.get(coin_id, 0)
        holding['current_price'] = current_price
        current_value = holding['total_amount'] * current_price
        unrealized_profit = current_value - holding['total_cost']
        holding['unrealized_profit'] = unrealized_profit
        total_unrealized_profit += unrealized_profit
    
    return render_template('combined.html', 
                         section='portfolio', 
                         transactions=transactions,
                         grouped_holdings=grouped_holdings,
                         all_transactions=all_transactions,
                         sold_transactions=sold_transactions, 
                         total_profit=round(total_profit, 2),
                         total_unrealized_profit=round(total_unrealized_profit, 2),
                         total_fees_paid=round(total_fees_paid, 2),
                         current_prices=current_prices, 
                         wallets=user_wallets, 
                         risk_metrics=risk_metrics, 
                         correlation_data=correlation_data)

@app.route('/watchlist', methods=['GET', 'POST'])
def watchlist():
    if 'user_id' not in session or session.get('expires_at', 0) < datetime.now().timestamp():
        return redirect(url_for('login'))

    def safe_float(value, default=0.0):
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def build_prep_signal(coin):
        change = safe_float(coin.get('price_change_percentage_24h'))
        market_cap = safe_float(coin.get('market_cap'))

        if change >= 4:
            return "Momentum Drill", "signal-momentum"
        if change <= -4:
            return "Dip-Defense Drill", "signal-defense"
        if market_cap >= 100000000000:
            return "Stability Anchor", "signal-stability"
        return "Range Practice", "signal-range"
    conn = get_db_connection()
    if conn is None:
        flash("Database connection failed", "error")
        return redirect(url_for('dashboard'))
    available_coins = []
    response = fetch_with_retry(f"{COINGECKO_API}/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=100&page=1&sparkline=false")
    if response:
        available_coins = json.loads(response.text)
    else:
        flash("Failed to fetch coin list for dropdown. Using cached data if available.", "warning")
    if request.method == 'POST':
        action = request.form.get('action')
        coin_id = request.form.get('coin_id', '').lower().strip()
        if not coin_id:
            flash("Coin ID is required", "error")
            return redirect(url_for('watchlist'))
        try:
            cursor = conn.cursor(dictionary=True)
            if action == 'add':
                coin_exists = any(coin['id'] == coin_id for coin in available_coins)
                if not coin_exists:
                    flash(f"Coin '{coin_id}' not found. Please select a valid coin.", "error")
                    return redirect(url_for('watchlist'))
                cursor.execute("SELECT * FROM watchlist WHERE user_id = %s AND coin_id = %s", (session['user_id'], coin_id))
                if cursor.fetchone():
                    flash(f"'{coin_id}' is already in your watchlist.", "warning")
                else:
                    cursor.execute("INSERT INTO watchlist (user_id, coin_id) VALUES (%s, %s)", (session['user_id'], coin_id))
                    conn.commit()
                    flash(f"'{coin_id}' added to your watchlist!", "success")
            elif action == 'remove':
                cursor.execute("DELETE FROM watchlist WHERE user_id = %s AND coin_id = %s", (session['user_id'], coin_id))
                if cursor.rowcount > 0:
                    conn.commit()
                    flash(f"'{coin_id}' removed from your watchlist!", "success")
                else:
                    flash(f"'{coin_id}' not found in your watchlist.", "warning")
        except mysql.connector.Error as err:
            flash(f"Database error: {err}", "error")
        finally:
            if conn.is_connected():
                cursor.close()
                conn.close()
        return redirect(url_for('watchlist'))
    watchlist = []
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT coin_id FROM watchlist WHERE user_id = %s", (session['user_id'],))
        watchlist = cursor.fetchall()
    except mysql.connector.Error as err:
        flash(f"Database error: {err}", "error")
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()
    coins = []
    watchlist_insights = {
        'total': 0,
        'up_count': 0,
        'down_count': 0,
        'avg_change': 0.0,
        'market_focus': 'Balanced',
        'readiness_score': 50,
        'coach_tip': 'Build your watchlist to receive simulation coaching.'
    }
    if watchlist:
        coin_ids = ','.join([w['coin_id'] for w in watchlist])
        response = fetch_with_retry(f"{COINGECKO_API}/coins/markets?vs_currency=usd&ids={coin_ids}&order=market_cap_desc&sparkline=false")
        if response:
            coins = json.loads(response.text)
            watchlist_ids = set(w['coin_id'] for w in watchlist)
            fetched_ids = set(coin['id'] for coin in coins)
            missing_coins = watchlist_ids - fetched_ids
            for coin_id in missing_coins:
                coins.append({
                    'id': coin_id,
                    'name': coin_id.capitalize(),
                    'symbol': coin_id[:3].upper(),
                    'current_price': 0.0,
                    'price_change_percentage_24h': 0.0,
                    'market_cap': 0.0
                })
        else:
            flash("Failed to fetch watchlist data. Using cached data if available.", "warning")
            coins = [{'id': w['coin_id'], 'name': w['coin_id'].capitalize(), 'symbol': w['coin_id'][:3].upper(), 
                      'current_price': 0.0, 'price_change_percentage_24h': 0.0, 'market_cap': 0.0} 
                     for w in watchlist]

        for coin in coins:
            coin['current_price'] = safe_float(coin.get('current_price'))
            coin['price_change_percentage_24h'] = safe_float(coin.get('price_change_percentage_24h'))
            coin['market_cap'] = safe_float(coin.get('market_cap'))
            signal, signal_class = build_prep_signal(coin)
            coin['prep_signal'] = signal
            coin['prep_signal_class'] = signal_class

        if coins:
            up_count = sum(1 for coin in coins if coin['price_change_percentage_24h'] > 0)
            down_count = sum(1 for coin in coins if coin['price_change_percentage_24h'] < 0)
            avg_change = sum(coin['price_change_percentage_24h'] for coin in coins) / len(coins)
            total_market_cap = sum(max(coin['market_cap'], 0) for coin in coins)
            top_market_cap = max((coin['market_cap'] for coin in coins), default=0)
            concentration = (top_market_cap / total_market_cap * 100) if total_market_cap > 0 else 0

            if concentration > 70:
                market_focus = 'High Concentration'
                coach_tip = 'Your watchlist is heavily concentrated. Simulate position sizing to reduce single-coin risk.'
            elif abs(avg_change) >= 3:
                market_focus = 'High Volatility'
                coach_tip = 'Large daily swings detected. Practice stop-loss and take-profit placement before live trading.'
            elif up_count >= down_count:
                market_focus = 'Trend-Friendly'
                coach_tip = 'Trend setup detected. Test entry timing with staggered buys in simulator mode.'
            else:
                market_focus = 'Pullback Phase'
                coach_tip = 'Market is cooling. Run defensive scenarios and compare max drawdown outcomes.'

            readiness_score = 55
            readiness_score += min(len(coins) * 4, 20)
            readiness_score += min(max(avg_change, 0), 5) * 2
            readiness_score -= max(concentration - 55, 0) * 0.35
            readiness_score = int(max(1, min(99, round(readiness_score))))

            watchlist_insights = {
                'total': len(coins),
                'up_count': up_count,
                'down_count': down_count,
                'avg_change': round(avg_change, 2),
                'market_focus': market_focus,
                'readiness_score': readiness_score,
                'coach_tip': coach_tip
            }
    else:
        flash("Your watchlist is empty. Add some coins to track!", "info")
    return render_template('combined.html', section='watchlist', coins=coins, available_coins=available_coins,
                         watchlist_insights=watchlist_insights)

@app.route('/alerts', methods=['GET', 'POST'])
def alerts():
    if 'user_id' not in session or session.get('expires_at', 0) < datetime.now().timestamp():
        return redirect(url_for('login'))
    # Fetch available coins for the dropdown
    available_coins = []
    response = fetch_with_retry(f"{COINGECKO_API}/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=100&page=1&sparkline=false")
    if response:
        available_coins = json.loads(response.text)
    else:
        flash("Failed to fetch coin list for dropdown. Using cached data if available.", "warning")
    if request.method == 'POST':
        coin_id = request.form.get('coin_id', '').lower()
        target_price = request.form.get('target_price')
        alert_type = request.form.get('alert_type')
        order_type = request.form.get('order_type')
        alert_note = request.form.get('alert_note', '').strip()
        if not all([coin_id, target_price, alert_type, order_type]):
            flash("All fields are required", "error")
            return redirect(url_for('alerts'))
        # Validate coin_id
        coin_exists = any(coin['id'] == coin_id for coin in available_coins)
        if not coin_exists:
            coin_check_response = fetch_with_retry(f"{COINGECKO_API}/coins/{coin_id}")
            coin_exists = coin_check_response is not None
        if not coin_exists:
            flash(f"Coin '{coin_id}' not found. Please select a valid coin.", "error")
            return redirect(url_for('alerts'))
        try:
            target_price = float(target_price)
        except ValueError:
            flash("Invalid target price", "error")
            return redirect(url_for('alerts'))
        if target_price <= 0:
            flash("Target price must be positive", "error")
            return redirect(url_for('alerts'))
        conn = get_db_connection()
        if conn:
            try:
                ensure_price_alerts_schema(conn)
                cursor = conn.cursor(dictionary=True)
                # Get user's email
                cursor.execute("SELECT email FROM users WHERE id = %s", (session['user_id'],))
                user = cursor.fetchone()
                if not user or 'email' not in user:
                    flash("Error: Could not retrieve your email address. Please update your profile.", "error")
                    return redirect(url_for('alerts'))
                
                # Insert the alert with user's email
                cursor.execute("""
                    INSERT INTO price_alerts 
                    (user_id, user_email, coin_id, target_price, alert_type, order_type, notified, note) 
                    VALUES (%s, %s, %s, %s, %s, %s, 0, %s)
                """, (session['user_id'], user['email'], coin_id, target_price, alert_type, order_type, alert_note[:500]))
                conn.commit()
                flash("Alert set successfully. You will receive email notifications when the price is reached.", "success")
            except mysql.connector.Error as err:
                flash(f"Database error: {err}", "error")
            finally:
                if conn.is_connected():
                    cursor.close()
                    conn.close()
    conn = get_db_connection()
    alerts = []
    alert_history = []
    next_check_seconds = CHECK_INTERVAL
    if conn:
        try:
            ensure_price_alerts_schema(conn)
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM price_alerts WHERE user_id = %s ORDER BY created_at DESC", (session['user_id'],))
            alerts = cursor.fetchall()

            active_alerts = [a for a in alerts if not a.get('notified')]
            if active_alerts:
                coin_ids = sorted(set(a['coin_id'] for a in active_alerts if a.get('coin_id')))
                coin_ids_str = ','.join(coin_ids)
                response = fetch_with_retry(f"{COINGECKO_API}/coins/markets?vs_currency=usd&ids={coin_ids_str}")
                price_map = {}
                if response:
                    price_map = {
                        coin['id']: float(coin['current_price'])
                        for coin in json.loads(response.text)
                        if 'id' in coin and coin.get('current_price') is not None
                    }

                for alert in alerts:
                    current_price = price_map.get(alert['coin_id'])
                    alert['current_price'] = current_price
                    alert['status'] = 'Triggered' if alert['notified'] else 'Watching'

                    if alert.get('notified'):
                        alert['progress_pct'] = 100
                    elif current_price is not None:
                        target_price = float(alert['target_price'])
                        if alert['alert_type'] == 'above':
                            pct = (current_price / target_price) * 100 if target_price > 0 else 0
                        else:
                            pct = (target_price / max(current_price, 0.0001)) * 100 if target_price > 0 else 0
                        alert['progress_pct'] = int(max(0, min(100, round(pct))))
                    else:
                        alert['progress_pct'] = 0
            else:
                for alert in alerts:
                    alert['current_price'] = None
                    alert['status'] = 'Triggered' if alert['notified'] else 'Watching'
                    alert['progress_pct'] = 100 if alert.get('notified') else 0

            cursor.execute(
                """
                SELECT coin_id, target_price, trigger_price, alert_type, note, triggered_at
                FROM price_alert_history
                WHERE user_id = %s
                ORDER BY triggered_at DESC
                LIMIT 30
                """,
                (session['user_id'],)
            )
            alert_history = cursor.fetchall()

            for alert in alerts:
                snoozed_until = alert.get('snoozed_until')
                if snoozed_until and isinstance(snoozed_until, datetime) and snoozed_until > datetime.now():
                    alert['status'] = 'Snoozed'

        except mysql.connector.Error as err:
            flash(f"Database error: {err}", "error")
        finally:
            if conn.is_connected():
                cursor.close()
                conn.close()
    return render_template(
        'combined.html',
        section='alerts',
        alerts=alerts,
        alert_history=alert_history,
        available_coins=available_coins,
        next_check_seconds=next_check_seconds
    )

@app.route('/remove_alert/<int:alert_id>', methods=['POST'])
def remove_alert(alert_id):
    if 'user_id' not in session or session.get('expires_at', 0) < datetime.now().timestamp():
        return redirect(url_for('login'))
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM price_alerts WHERE id = %s AND user_id = %s", (alert_id, session['user_id']))
            if cursor.rowcount > 0:
                conn.commit()
                flash("Alert removed successfully", "success")
            else:
                flash("Alert not found", "error")
        except mysql.connector.Error as err:
            flash(f"Database error: {err}", "error")
        finally:
            if conn.is_connected():
                cursor.close()
                conn.close()
    return redirect(url_for('alerts'))


@app.route('/snooze_alert/<int:alert_id>', methods=['POST'])
def snooze_alert(alert_id):
    if 'user_id' not in session or session.get('expires_at', 0) < datetime.now().timestamp():
        return redirect(url_for('login'))

    conn = get_db_connection()
    if conn:
        try:
            ensure_price_alerts_schema(conn)
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE price_alerts
                SET snoozed_until = DATE_ADD(NOW(), INTERVAL 24 HOUR)
                WHERE id = %s AND user_id = %s AND notified = 0
                """,
                (alert_id, session['user_id'])
            )
            if cursor.rowcount > 0:
                conn.commit()
                flash("Alert snoozed for 24 hours.", "success")
            else:
                flash("Alert not found or already triggered.", "warning")
        except mysql.connector.Error as err:
            flash(f"Database error: {err}", "error")
        finally:
            if conn.is_connected():
                cursor.close()
                conn.close()

    return redirect(url_for('alerts'))

@app.route('/orders')
def orders():
    """View all open orders and order history"""
    if 'user_id' not in session or session.get('expires_at', 0) < datetime.now().timestamp():
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    open_orders = []
    order_history = []
    
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            
            # Get open (pending) orders
            cursor.execute("""
                SELECT o.*, tp.symbol as pair_symbol 
                FROM orders o
                LEFT JOIN trading_pairs tp ON o.pair_id = tp.id
                WHERE o.user_id = %s AND o.status = 'pending'
                ORDER BY o.created_at DESC
            """, (session['user_id'],))
            open_orders = cursor.fetchall()
            
            # Get order history (filled or cancelled)
            cursor.execute("""
                SELECT o.*, tp.symbol as pair_symbol 
                FROM orders o
                LEFT JOIN trading_pairs tp ON o.pair_id = tp.id
                WHERE o.user_id = %s AND o.status IN ('filled', 'cancelled')
                ORDER BY o.created_at DESC
                LIMIT 50
            """, (session['user_id'],))
            order_history = cursor.fetchall()
            
        except mysql.connector.Error as err:
            flash(f"Database error: {err}", "error")
        finally:
            if conn.is_connected():
                cursor.close()
                conn.close()
    
    return render_template('combined.html', section='orders', 
                         open_orders=open_orders, order_history=order_history)

@app.route('/cancel_order/<int:order_id>', methods=['POST'])
def cancel_order(order_id):
    """Cancel a pending order"""
    if 'user_id' not in session or session.get('expires_at', 0) < datetime.now().timestamp():
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE orders SET status = 'cancelled', cancelled_at = NOW() 
                WHERE id = %s AND user_id = %s AND status = 'pending'
            """, (order_id, session['user_id']))
            
            if cursor.rowcount > 0:
                conn.commit()
                flash("Order cancelled successfully", "success")
            else:
                flash("Order not found or already executed", "error")
        except mysql.connector.Error as err:
            flash(f"Database error: {err}", "error")
        finally:
            if conn.is_connected():
                cursor.close()
                conn.close()
    
    return redirect(url_for('orders'))

@app.route('/check_orders_now')
def check_orders_now():
    """Manually trigger order execution check"""
    if 'user_id' not in session or session.get('expires_at', 0) < datetime.now().timestamp():
        return redirect(url_for('login'))
    
    print("🔄 Manual order check triggered by user")
    check_pending_orders()
    flash("✅ Order check completed! Check your orders below.", "success")
    return redirect(url_for('orders'))

@app.route('/trading_pairs')
def trading_pairs():
    """Get all available trading pairs"""
    if 'user_id' not in session or session.get('expires_at', 0) < datetime.now().timestamp():
        return jsonify({'error': 'Unauthorized'}), 401
    
    conn = get_db_connection()
    pairs = []
    
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM trading_pairs WHERE is_active = TRUE")
            pairs = cursor.fetchall()
        except mysql.connector.Error as err:
            return jsonify({'error': str(err)}), 500
        finally:
            if conn.is_connected():
                cursor.close()
                conn.close()
    
    return jsonify(pairs)

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('expires_at', None)
    return redirect(url_for('login'))

@app.route('/historical/<coin_id>')
def historical(coin_id):
    response = fetch_with_retry(f"{COINGECKO_API}/coins/{coin_id}/market_chart?vs_currency=usd&days=30")
    if response:
        data = json.loads(response.text)
        dates = [datetime.fromtimestamp(item[0]/1000).strftime('%Y-%m-%d') for item in data['prices']]
        prices = [item[1] for item in data['prices']]
        volumes = [item[1] for item in data['total_volumes']]
        market_caps = [item[1] for item in data['market_caps']]
        return jsonify({
            'dates': dates,
            'prices': prices,
            'volumes': volumes,
            'market_caps': market_caps
        })
    return jsonify({'error': 'Failed to fetch historical data'}), 500


@app.route('/api/scenario_replay/<coin_id>')
def scenario_replay(coin_id):
    if 'user_id' not in session or session.get('expires_at', 0) < datetime.now().timestamp():
        return jsonify({'error': 'Unauthorized'}), 401

    replay_date_raw = request.args.get('date', '').strip()
    if not replay_date_raw:
        return jsonify({'error': 'Date is required'}), 400

    try:
        replay_date = datetime.strptime(replay_date_raw, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400

    response = fetch_with_retry(f"{COINGECKO_API}/coins/{coin_id}/market_chart?vs_currency=usd&days=30")
    if not response:
        return jsonify({'error': 'Failed to fetch historical data'}), 500

    data = json.loads(response.text)
    price_points = data.get('prices', [])
    if len(price_points) < 6:
        return jsonify({'error': 'Not enough historical data for replay'}), 400

    series = []
    for ts, price in price_points:
        dt = datetime.fromtimestamp(ts / 1000).date()
        try:
            p = float(price)
        except (TypeError, ValueError):
            continue
        series.append({'date': dt, 'price': p})

    if len(series) < 6:
        return jsonify({'error': 'Not enough valid historical points'}), 400

    entry_idx = min(range(len(series)), key=lambda i: abs((series[i]['date'] - replay_date).days))
    # Keep enough lookahead for scenario outcomes.
    entry_idx = max(0, min(entry_idx, len(series) - 4))

    entry_point = series[entry_idx]
    next_point = series[min(entry_idx + 1, len(series) - 1)]
    lookahead = series[entry_idx + 1:min(entry_idx + 4, len(series))]
    if not lookahead:
        lookahead = [next_point]

    entry_price = entry_point['price']
    next_price = next_point['price']
    max_price = max(p['price'] for p in lookahead)
    min_price = min(p['price'] for p in lookahead)
    end_price = lookahead[-1]['price']

    conservative_return = ((next_price - entry_price) / entry_price) * 100 * 0.75
    rule_based_return = ((end_price - entry_price) / entry_price) * 100

    # Emotional outcome amplifies losses and often cuts winners early.
    if end_price >= entry_price:
        emotional_anchor = ((max_price - entry_price) / entry_price) * 100 * 0.35
        emotional_return = emotional_anchor - 0.8
    else:
        emotional_return = ((min_price - entry_price) / entry_price) * 100 * 1.15

    conservative_return = round(max(-8.5, min(12.5, conservative_return)), 2)
    rule_based_return = round(max(-10.0, min(18.0, rule_based_return)), 2)
    emotional_return = round(max(-15.0, min(10.0, emotional_return)), 2)

    outcomes = [
        {'label': 'Conservative Exit', 'value': conservative_return},
        {'label': 'Rule-Based Exit', 'value': rule_based_return},
        {'label': 'Emotional Exit', 'value': emotional_return}
    ]
    outcomes.sort(key=lambda x: x['value'], reverse=True)
    best_strategy = outcomes[0]['label']

    edge_vs_emotional = rule_based_return - emotional_return
    price_range_pct = ((max_price - min_price) / entry_price) * 100 if entry_price > 0 else 0
    prep_score = 52 + edge_vs_emotional * 5.4 - max(price_range_pct - 6, 0) * 1.1
    prep_score = int(max(1, min(99, round(prep_score))))

    if edge_vs_emotional >= 2:
        lesson = (
            f"Rule-based planning beat emotional behavior by {edge_vs_emotional:.2f}%. "
            "Use this replay to lock in stop-loss and take-profit rules before executing a trade."
        )
    else:
        lesson = (
            f"The edge is narrow ({edge_vs_emotional:.2f}% vs emotional). "
            "On choppy sessions, improve entry timing and reduce position size in simulation first."
        )

    return jsonify({
        'coin_id': coin_id,
        'requested_date': replay_date_raw,
        'used_date': entry_point['date'].isoformat(),
        'entry_price': round(entry_price, 6),
        'conservative_return': conservative_return,
        'rule_based_return': rule_based_return,
        'emotional_return': emotional_return,
        'best_strategy': best_strategy,
        'prep_score': prep_score,
        'lesson': lesson
    })


@app.route('/api/scenario_replay/save', methods=['POST'])
def save_scenario_replay():
    if 'user_id' not in session or session.get('expires_at', 0) < datetime.now().timestamp():
        return jsonify({'error': 'Unauthorized'}), 401

    payload = request.get_json(silent=True) or {}
    coin_id = str(payload.get('coin_id', '')).strip().lower()
    used_date = str(payload.get('used_date', '')).strip()

    if not coin_id or not used_date:
        return jsonify({'error': 'coin_id and used_date are required'}), 400

    try:
        replay_date = datetime.strptime(used_date, '%Y-%m-%d').date()
        entry_price = float(payload.get('entry_price', 0))
        conservative_return = float(payload.get('conservative_return', 0))
        rule_based_return = float(payload.get('rule_based_return', 0))
        emotional_return = float(payload.get('emotional_return', 0))
        best_strategy = str(payload.get('best_strategy', 'Rule-Based Exit')).strip()[:64]
        prep_score = int(payload.get('prep_score', 50))
    except (TypeError, ValueError):
        return jsonify({'error': 'Invalid payload values'}), 400

    prep_score = max(1, min(99, prep_score))

    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500

    try:
        ensure_watchlist_scenarios_table(conn)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO watchlist_scenarios (
                user_id, coin_id, replay_date, entry_price,
                conservative_return, rule_based_return, emotional_return,
                best_strategy, prep_score
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                session['user_id'], coin_id, replay_date, entry_price,
                conservative_return, rule_based_return, emotional_return,
                best_strategy, prep_score
            )
        )
        conn.commit()
        cursor.close()
        return jsonify({'ok': True})
    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        if conn.is_connected():
            conn.close()


@app.route('/api/scenario_replay/history')
def scenario_replay_history():
    if 'user_id' not in session or session.get('expires_at', 0) < datetime.now().timestamp():
        return jsonify({'error': 'Unauthorized'}), 401

    coin_id = request.args.get('coin_id', '').strip().lower()
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500

    try:
        ensure_watchlist_scenarios_table(conn)
        cursor = conn.cursor(dictionary=True)

        if coin_id:
            cursor.execute(
                """
                SELECT replay_date, prep_score, best_strategy,
                       conservative_return, rule_based_return, emotional_return, created_at
                FROM watchlist_scenarios
                WHERE user_id = %s AND coin_id = %s
                ORDER BY created_at DESC
                LIMIT 12
                """,
                (session['user_id'], coin_id)
            )
        else:
            cursor.execute(
                """
                SELECT coin_id, replay_date, prep_score, best_strategy,
                       conservative_return, rule_based_return, emotional_return, created_at
                FROM watchlist_scenarios
                WHERE user_id = %s
                ORDER BY created_at DESC
                LIMIT 12
                """,
                (session['user_id'],)
            )

        rows = cursor.fetchall()
        cursor.close()

        for row in rows:
            if isinstance(row.get('replay_date'), datetime):
                row['replay_date'] = row['replay_date'].date().isoformat()
            elif hasattr(row.get('replay_date'), 'isoformat'):
                row['replay_date'] = row['replay_date'].isoformat()

            if isinstance(row.get('created_at'), datetime):
                row['created_at'] = row['created_at'].isoformat()

        return jsonify({'history': rows})
    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        if conn.is_connected():
            conn.close()

@app.route('/correlation_matrix')
def correlation_matrix():
    if 'user_id' not in session or session.get('expires_at', 0) < datetime.now().timestamp():
        return jsonify({'error': 'Unauthorized', 'labels': [], 'matrix': []}), 401

    conn = get_db_connection()
    coin_ids = []
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT DISTINCT coin_id FROM transactions WHERE user_id = %s", (session['user_id'],))
            coin_ids = [row['coin_id'] for row in cursor.fetchall()]
        except mysql.connector.Error as err:
            return jsonify({'error': f'Database error: {err}', 'labels': [], 'matrix': []}), 500
        finally:
            if conn.is_connected():
                cursor.close()
                conn.close()
    correlation_data = calculate_correlation_matrix(coin_ids)
    return jsonify(correlation_data)

@app.route('/api/orderbook/<pair>')
def orderbook(pair):
    """Get order book for a specific trading pair (e.g., BTC/USDT)"""
    if 'user_id' not in session or session.get('expires_at', 0) < datetime.now().timestamp():
        return jsonify({'error': 'Unauthorized'}), 401
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cursor = conn.cursor(dictionary=True)
        
        # Parse pair (e.g., "bitcoin-tether" or "BTC/USDT")
        if '/' in pair:
            parts = pair.split('/')
            base = parts[0].lower()
            quote = parts[1].lower()
            # Convert symbols to coin IDs
            if base == 'btc':
                base = 'bitcoin'
            elif base == 'eth':
                base = 'ethereum'
            elif base == 'usdt':
                base = 'tether'
            if quote == 'usdt':
                quote = 'tether'
        elif '-' in pair:
            base, quote = pair.lower().split('-')
        else:
            return jsonify({'error': 'Invalid pair format'}), 400
        
        # Get buy orders (bids) - sorted by price descending
        cursor.execute("""
            SELECT price as price_level, SUM(amount - filled_amount) as total_amount, COUNT(*) as order_count
            FROM orders
            WHERE base_currency = %s AND quote_currency = %s 
            AND side = 'buy' AND status = 'pending' AND order_type = 'limit'
            GROUP BY price
            ORDER BY price DESC
            LIMIT 20
        """, (base, quote))
        bids = cursor.fetchall()
        
        # Get sell orders (asks) - sorted by price ascending
        cursor.execute("""
            SELECT price as price_level, SUM(amount - filled_amount) as total_amount, COUNT(*) as order_count
            FROM orders
            WHERE base_currency = %s AND quote_currency = %s 
            AND side = 'sell' AND status = 'pending' AND order_type = 'limit'
            GROUP BY price
            ORDER BY price ASC
            LIMIT 20
        """, (base, quote))
        asks = cursor.fetchall()
        
        # Convert Decimal to float for JSON serialization
        for bid in bids:
            bid['price_level'] = float(bid['price_level'])
            bid['total_amount'] = float(bid['total_amount'])
        
        for ask in asks:
            ask['price_level'] = float(ask['price_level'])
            ask['total_amount'] = float(ask['total_amount'])
        
        return jsonify({
            'pair': f"{base}/{quote}",
            'bids': bids,
            'asks': asks,
            'timestamp': datetime.now().isoformat()
        })
        
    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()

@app.route('/backtester')
def backtester():
    """Render backtester inside the existing Flask app shell."""
    try:
        if 'user_id' not in session or session.get('expires_at', 0) < datetime.now().timestamp():
            return redirect(url_for('login'))
        return render_template('combined.html', section='backtester')
    except Exception as e:
        error_msg = f"Error in backtester route: {str(e)}\n\n{traceback.format_exc()}"
        print(error_msg)
        return render_template('combined.html', section='backtester', error=str(e))


@app.route('/backtester_app/')
@app.route('/backtester_app/<path:asset_path>')
def backtester_app_assets(asset_path='index.html'):
    """Serve built Lovable backtester bundle isolated from main app routes."""
    if 'user_id' not in session or session.get('expires_at', 0) < datetime.now().timestamp():
        return redirect(url_for('login'))

    dist_dir = os.path.join(app.static_folder, 'lovable_backtester')
    requested_file = os.path.join(dist_dir, asset_path)

    if os.path.isfile(requested_file):
        return send_from_directory(dist_dir, asset_path)

    return send_from_directory(dist_dir, 'index.html')

@app.route('/api/backtest', methods=['POST'])
def api_backtest():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    data = request.json
    
    try:
        # Get historical data from CoinGecko
        coin_id = data.get('coin_id')
        days = int(data.get('days', 30))
        initial_capital = float(data.get('initial_capital', 1000))
        strategy_code = data.get('strategy_code', '')
        
        # Fetch historical data
        end_date = int(time.time())
        start_date = end_date - (days * 24 * 60 * 60)
        
        response = fetch_with_retry(
            f"{COINGECKO_API}/coins/{coin_id}/market_chart/range"
            f"?vs_currency=usd&from={start_date}&to={end_date}"
        )
        
        # Process the data
        historical_data = response.json()
        prices = historical_data['prices']
        
        # Create a DataFrame with OHLCV data (simplified - using close prices)
        df = pd.DataFrame(prices, columns=['timestamp', 'close'])
        df['date'] = pd.to_datetime(df['timestamp'], unit='ms')
        df['open'] = df['close'].shift(1)
        df['high'] = df[['open', 'close']].max(axis=1)
        df['low'] = df[['open', 'close']].min(axis=1)
        df['volume'] = 0  # Not available in this API response
        
        # Prepare the strategy function
        strategy_globals = {}
        strategy_locals = {'data': df, 'portfolio': {'cash': initial_capital, 'position': 0, 'equity': [initial_capital]}}
        
        # Execute the strategy code in a controlled environment
        try:
            # Create a custom namespace with only the allowed modules
            allowed_globals = {
                'pd': pd,
                'np': np,
                '__builtins__': {
                    'range': range,
                    'len': len,
                    'float': float,
                    'int': int,
                    'str': str,
                    'list': list,
                    'dict': dict,
                    'min': min,
                    'max': max,
                    'sum': sum,
                    'abs': abs,
                    'round': round,
                    'zip': zip,
                    'enumerate': enumerate,
                    'sorted': sorted,
                    'reversed': reversed,
                    'filter': filter,
                    'map': map,
                }
            }
            
            # Execute the strategy code
            exec(strategy_code, strategy_globals, strategy_locals)
            
            # Get the strategy results
            if 'strategy' in strategy_locals:
                result = strategy_locals['strategy'](df, {'cash': initial_capital, 'position': 0})
            else:
                # Try to find the strategy function
                for name, obj in strategy_locals.items():
                    if callable(obj) and name != '<module>':
                        result = obj(df, {'cash': initial_capital, 'position': 0})
                        break
                else:
                    return jsonify({'error': 'No strategy function found in the code'}), 400
            
            # Process the results
            if not isinstance(result, dict) or 'signals' not in result or 'metrics' not in result:
                return jsonify({'error': 'Strategy must return a dictionary with "signals" and "metrics"'}), 400
            
            # Calculate trades and equity curve
            trades = []
            equity_curve = [{'timestamp': int(df['timestamp'].iloc[0]), 'equity': initial_capital}]
            
            for i in range(1, len(df)):
                # Simplified trade simulation
                if i < len(result['signals']) and 'position' in result['signals'][i]:
                    prev_position = result['signals'][i-1]['position'] if i > 0 else 0
                    current_position = result['signals'][i]['position']
                    
                    if current_position != prev_position:
                        price = df['close'].iloc[i]
                        trade_type = 'buy' if current_position > prev_position else 'sell'
                        trade_size = abs(current_position - prev_position)
                        
                        trades.append({
                            'timestamp': int(df['timestamp'].iloc[i]),
                            'type': trade_type,
                            'price': price,
                            'position': current_position,
                            'pnl': 0  # Simplified for this example
                        })
                
                # Update equity curve (simplified)
                if 'strategy_return' in result and i < len(result['strategy_return']):
                    daily_return = result['strategy_return'].iloc[i] if not np.isnan(result['strategy_return'].iloc[i]) else 0
                    equity = equity_curve[-1]['equity'] * (1 + daily_return)
                    equity_curve.append({
                        'timestamp': int(df['timestamp'].iloc[i]),
                        'equity': equity
                    })
            
            # Calculate win rate (simplified)
            win_rate = 0.5  # Default
            if trades:
                winning_trades = sum(1 for t in trades if t.get('pnl', 0) > 0)
                win_rate = winning_trades / len(trades)
            
            result['metrics']['win_rate'] = win_rate
            
            return jsonify({
                'success': True,
                'trades': trades,
                'equity_curve': equity_curve,
                'metrics': result['metrics']
            })
            
        except Exception as e:
            error_msg = f"Error executing strategy: {str(e)}\n\nTraceback:\n{traceback.format_exc()}"
            return jsonify({'error': error_msg}), 400
            
    except Exception as e:
        return jsonify({'error': f'Backtest failed: {str(e)}'}), 500

@app.route('/achievements')
def achievements():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)

            # Current user profile snapshot
            cursor.execute(
                "SELECT id, username, risk_score, achievements FROM users WHERE id = %s",
                (session['user_id'],)
            )
            user = cursor.fetchone() or {}
            raw_achievements = [
                a.strip() for a in (user.get('achievements') or '').split(',') if a.strip()
            ]

            # Current user trading metrics
            cursor.execute("""
                SELECT
                    COALESCE(SUM(CASE WHEN type='sell' AND sold_price IS NOT NULL THEN (sold_price - price) * amount ELSE 0 END), 0) AS total_profit,
                    COALESCE(SUM(CASE WHEN type='sell' AND sold_price IS NOT NULL THEN 1 ELSE 0 END), 0) AS closed_trades,
                    COALESCE(SUM(CASE WHEN type='sell' AND sold_price IS NOT NULL AND sold_price > price THEN 1 ELSE 0 END), 0) AS winning_trades,
                    COALESCE(COUNT(DISTINCT CASE WHEN type IN ('buy', 'sell') THEN coin_id END), 0) AS unique_coins
                FROM transactions
                WHERE user_id = %s
            """, (session['user_id'],))
            user_metrics = cursor.fetchone() or {}

            total_profit = float(user_metrics.get('total_profit') or 0)
            closed_trades = int(user_metrics.get('closed_trades') or 0)
            winning_trades = int(user_metrics.get('winning_trades') or 0)
            unique_coins = int(user_metrics.get('unique_coins') or 0)
            win_rate = round((winning_trades / closed_trades) * 100, 1) if closed_trades > 0 else 0.0
            risk_score = int(user.get('risk_score') or 0)

            # Rich achievement definitions with progress
            achievement_cards = [
                {
                    'key': 'first_trade',
                    'title': 'First Trade',
                    'description': 'Complete your first closed trade',
                    'icon': 'fa-medal',
                    'progress': min(closed_trades, 1),
                    'target': 1,
                    'unlocked': (closed_trades >= 1) or ('First Trade' in raw_achievements),
                },
                {
                    'key': 'diamond_hands',
                    'title': 'Diamond Hands',
                    'description': 'Reach 15 closed trades',
                    'icon': 'fa-gem',
                    'progress': min(closed_trades, 15),
                    'target': 15,
                    'unlocked': (closed_trades >= 15) or ('Diamond Hands' in raw_achievements),
                },
                {
                    'key': 'profit_master',
                    'title': 'Profit Master',
                    'description': 'Achieve +$1,000 net realized profit',
                    'icon': 'fa-coins',
                    'progress': min(max(total_profit, 0), 1000),
                    'target': 1000,
                    'unlocked': (total_profit >= 1000) or ('Profit Master' in raw_achievements),
                },
                {
                    'key': 'risk_manager',
                    'title': 'Risk Manager',
                    'description': 'Score 70+ in risk assessment',
                    'icon': 'fa-shield-alt',
                    'progress': min(max(risk_score, 0), 70),
                    'target': 70,
                    'unlocked': (risk_score >= 70) or ('Risk Manager' in raw_achievements),
                },
                {
                    'key': 'diversifier',
                    'title': 'Diversifier',
                    'description': 'Trade 5 different coins',
                    'icon': 'fa-bullseye',
                    'progress': min(unique_coins, 5),
                    'target': 5,
                    'unlocked': (unique_coins >= 5) or ('Diversifier' in raw_achievements),
                },
                {
                    'key': 'consistent_winner',
                    'title': 'Consistent Winner',
                    'description': 'Maintain 60%+ win rate over 10+ trades',
                    'icon': 'fa-chart-line',
                    'progress': min(win_rate, 60) if closed_trades >= 10 else 0,
                    'target': 60,
                    'unlocked': (closed_trades >= 10 and win_rate >= 60) or ('Consistent Winner' in raw_achievements),
                },
            ]

            unlocked_count = sum(1 for c in achievement_cards if c['unlocked'])

            # Global leaderboard with multiple factors
            cursor.execute("""
                SELECT
                    u.id,
                    u.username,
                    COALESCE(u.risk_score, 0) AS risk_score,
                    COALESCE(u.achievements, '') AS achievements,
                    COALESCE(SUM(CASE WHEN t.type='sell' AND t.sold_price IS NOT NULL THEN (t.sold_price - t.price) * t.amount ELSE 0 END), 0) AS total_profit,
                    COALESCE(SUM(CASE WHEN t.type='sell' AND t.sold_price IS NOT NULL THEN 1 ELSE 0 END), 0) AS closed_trades,
                    COALESCE(SUM(CASE WHEN t.type='sell' AND t.sold_price IS NOT NULL AND t.sold_price > t.price THEN 1 ELSE 0 END), 0) AS winning_trades,
                    COALESCE(COUNT(DISTINCT CASE WHEN t.type IN ('buy', 'sell') THEN t.coin_id END), 0) AS diversity
                FROM users u
                LEFT JOIN transactions t ON t.user_id = u.id
                GROUP BY u.id, u.username, u.risk_score, u.achievements
            """)
            leaderboard_rows = cursor.fetchall() or []

            leaderboard = []
            for row in leaderboard_rows:
                row_profit = float(row.get('total_profit') or 0)
                row_trades = int(row.get('closed_trades') or 0)
                row_wins = int(row.get('winning_trades') or 0)
                row_risk = int(row.get('risk_score') or 0)
                row_diversity = int(row.get('diversity') or 0)
                row_ach_count = len([a for a in str(row.get('achievements') or '').split(',') if a.strip()])
                row_win_rate = (row_wins / row_trades * 100.0) if row_trades > 0 else 0.0

                profit_factor = max(min((max(row_profit, 0) / 2000.0) * 30.0, 30.0), 0.0)
                win_rate_factor = max(min((row_win_rate / 100.0) * 20.0, 20.0), 0.0)
                trade_factor = max(min((row_trades / 30.0) * 20.0, 20.0), 0.0)
                risk_factor = max(min((row_risk / 100.0) * 15.0, 15.0), 0.0)
                diversity_factor = max(min((row_diversity / 10.0) * 10.0, 10.0), 0.0)
                achievement_factor = max(min((row_ach_count / 10.0) * 5.0, 5.0), 0.0)

                composite_score = round(
                    profit_factor + win_rate_factor + trade_factor + risk_factor + diversity_factor + achievement_factor,
                    2,
                )

                leaderboard.append({
                    'user_id': row.get('id'),
                    'username': row.get('username') or 'Trader',
                    'total_profit': row_profit,
                    'closed_trades': row_trades,
                    'win_rate': round(row_win_rate, 1),
                    'risk_score': row_risk,
                    'diversity': row_diversity,
                    'achievement_count': row_ach_count,
                    'score': composite_score,
                })

            leaderboard.sort(key=lambda x: (x['score'], x['total_profit']), reverse=True)
            for idx, row in enumerate(leaderboard, start=1):
                row['rank'] = idx

            top_leaderboard = leaderboard[:25]
            my_rank_row = next((r for r in leaderboard if r['user_id'] == session['user_id']), None)

            return render_template(
                'combined.html',
                section='achievements',
                achievements=raw_achievements,
                achievement_cards=achievement_cards,
                unlocked_count=unlocked_count,
                total_achievements=len(achievement_cards),
                user_metrics={
                    'total_profit': total_profit,
                    'closed_trades': closed_trades,
                    'win_rate': win_rate,
                    'risk_score': risk_score,
                    'diversity': unique_coins,
                },
                leaderboard=top_leaderboard,
                leaderboard_count=len(leaderboard),
                my_rank=my_rank_row,
                score_factors=[
                    'Net realized profit (30%)',
                    'Win rate (20%)',
                    'Closed trades volume (20%)',
                    'Risk assessment score (15%)',
                    'Coin diversity (10%)',
                    'Achievement count (5%)',
                ],
            )
        except mysql.connector.Error as err:
            flash(f"Database error: {err}", "error")
        finally:
            if conn.is_connected():
                cursor.close()
                conn.close()
    return redirect(url_for('dashboard'))

@app.route('/update_achievements', methods=['POST']) 
def update_achievements():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    achievement = request.form.get('achievement')
    if not achievement:
        flash("Achievement is required", "error")
        return redirect(url_for('achievements'))
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT achievements FROM users WHERE id = %s", (session['user_id'],))
            user = cursor.fetchone()
            current_achievements = user['achievements'].split(',') if user['achievements'] else []
            if achievement not in current_achievements:
                current_achievements.append(achievement)
                cursor.execute("UPDATE users SET achievements = %s WHERE id = %s", (','.join(current_achievements), session['user_id']))
                conn.commit()
                flash("Achievement added successfully", "success")
            else:
                flash("Achievement already exists", "error")
        except mysql.connector.Error as err:
            flash(f"Database error: {err}", "error")
        finally:
            if conn.is_connected():
                cursor.close()
                conn.close()
    return redirect(url_for('achievements'))

@app.route('/test-email')
def test_email():
    try:
        # Replace with your test email
        test_email = 'frozenflames677@gmail.com'
        success = send_email_notification(
            recipient=test_email,
            subject='Test Email from Crypto Tracker',
            body='This is a test email to verify the email functionality is working.'
        )
        if success:
            return 'Test email sent successfully! Check your inbox.'
        else:
            return 'Failed to send test email.', 500
    except Exception as e:
        return f'Error: {str(e)}', 500

# ==================== AI TRADE ADVISOR (Phase 1: Before Trade) ====================

# Module-level fallback so the variable always exists
ai_assistant = None
ai_assistant_fallback = None

@app.route('/api/trade-advisor', methods=['POST'])
def trade_advisor():
    """Phase 1: Before Trade → Decision Help API"""
    if 'user_id' not in session or session.get('expires_at', 0) < datetime.now().timestamp():
        return jsonify({'error': 'Not authenticated'}), 401
    
    # Check if AI assistant is available
    global ai_assistant, ai_assistant_fallback
    if ai_assistant is None:
        return jsonify({'error': 'AI system not initialized. Set GEMINI_API_KEY or ANTHROPIC_API_KEY environment variable and restart the app.'}), 503
    
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    coin_id = data.get('coin_id', '').lower()
    current_price = data.get('current_price', 0)
    price_change_24h = data.get('price_change_24h', 0)
    
    if not coin_id or not current_price:
        return jsonify({'error': 'coin_id and current_price are required'}), 400
    
    try:
        current_price = float(current_price)
        price_change_24h = float(price_change_24h)
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid price values'}), 400
    
    try:
        result = ai_assistant.get_trade_advice(
            user_id=session['user_id'],
            coin_id=coin_id,
            current_price=current_price,
            price_change_24h=price_change_24h
        )

        # If primary provider is unavailable, try secondary provider when configured.
        if (not result.get('ai_available', True)) and ai_assistant_fallback is not None:
            try:
                fallback_result = ai_assistant_fallback.get_trade_advice(
                    user_id=session['user_id'],
                    coin_id=coin_id,
                    current_price=current_price,
                    price_change_24h=price_change_24h
                )

                if fallback_result.get('ai_available', True):
                    fallback_result['provider_failover'] = True
                    fallback_result['primary_provider_error'] = result.get('ai_error', '')
                    return jsonify(fallback_result)
            except Exception as fallback_err:
                print(f"Trade advisor fallback error: {fallback_err}")

        return jsonify(result)
    except Exception as e:
        print(f"Trade advisor primary error: {e}")

        if ai_assistant_fallback is not None:
            try:
                fallback_result = ai_assistant_fallback.get_trade_advice(
                    user_id=session['user_id'],
                    coin_id=coin_id,
                    current_price=current_price,
                    price_change_24h=price_change_24h
                )
                fallback_result['provider_failover'] = True
                fallback_result['primary_provider_error'] = str(e)
                return jsonify(fallback_result)
            except Exception as fallback_err:
                print(f"Trade advisor fallback error: {fallback_err}")
                return jsonify({'error': f'Trade advisor unavailable. Primary: {str(e)} | Fallback: {str(fallback_err)}'}), 503

        return jsonify({'error': f'Trade advisor unavailable: {str(e)}'}), 503

# ==================== AI LEARNING SYSTEM INITIALIZATION ====================

# Initialize AI Assistant and User Profiler
try:
    # Provider keys and preference
    # Gemini: https://makersuite.google.com/app/apikey
    # Claude: https://console.anthropic.com/
    gemini_key = os.getenv('GEMINI_API_KEY')
    anthropic_key = os.getenv('ANTHROPIC_API_KEY')
    provider_pref = (os.getenv('AI_PROVIDER') or 'auto').strip().lower()

    primary_key = None
    primary_provider = None
    fallback_key = None
    fallback_provider = None

    if provider_pref in ('anthropic', 'claude'):
        if anthropic_key:
            primary_key = anthropic_key
            primary_provider = 'claude'
        elif gemini_key:
            primary_key = gemini_key
            primary_provider = 'gemini'
    elif provider_pref == 'gemini':
        if gemini_key:
            primary_key = gemini_key
            primary_provider = 'gemini'
        elif anthropic_key:
            primary_key = anthropic_key
            primary_provider = 'claude'
    else:
        if gemini_key:
            primary_key = gemini_key
            primary_provider = 'gemini'
        elif anthropic_key:
            primary_key = anthropic_key
            primary_provider = 'claude'

    if gemini_key and anthropic_key:
        if primary_provider == 'gemini':
            fallback_key = anthropic_key
            fallback_provider = 'claude'
        elif primary_provider == 'claude':
            fallback_key = gemini_key
            fallback_provider = 'gemini'

    if primary_key:
        ai_assistant = get_ai_assistant(get_db_connection, primary_key, provider=primary_provider)

        if fallback_key and fallback_provider:
            try:
                ai_assistant_fallback = get_ai_assistant(get_db_connection, fallback_key, provider=fallback_provider)
            except Exception as fallback_init_error:
                ai_assistant_fallback = None
                print(f"⚠️  Could not initialize fallback AI provider: {fallback_init_error}")

        user_profiler = get_user_profiler(get_db_connection)
        
        # Initialize learning routes with AI components
        init_learning_system(ai_assistant, user_profiler)
        
        # Register learning blueprint
        app.register_blueprint(learning_bp)
        
        print("✅ AI Learning System initialized successfully!")
        print(f"   - AI Provider: {primary_provider.capitalize()}")
        if ai_assistant_fallback is not None:
            print(f"   - Failover Provider: {fallback_provider.capitalize()}")
        print("   - RAG system ready")
        print("   - ChromaDB initialized")
        print("   - Learning routes registered at /learning/*")
        print("\n📚 Next steps:")
        print("   1. Run database schema: mysql < learning_system_schema.sql")
        print("   2. Index knowledge base: POST /learning/api/index-knowledge")
        print("   3. Visit /learning/hub to start learning!")
    else:
        print("⚠️  No AI API key found in environment variables")
        print("   AI Learning System disabled")
        print("   To enable AI:")
        print("   1. Get key: https://makersuite.google.com/app/apikey")
        print("   2. Set GEMINI_API_KEY and/or ANTHROPIC_API_KEY")
        print("   3. Optional: set AI_PROVIDER=gemini|anthropic|auto")
        print("   3. Restart app")
        
except Exception as e:
    print(f"⚠️  Could not initialize AI Learning System: {e}")
    print("   App will run without learning features")

# ===========================================================================
# AI TRADING COACH
# ===========================================================================

@app.route('/api/trading_coach')
def trading_coach_api():
    """Analyze user's trade history and provide behavioral coaching."""
    if 'user_id' not in session or session.get('expires_at', 0) < datetime.now().timestamp():
        return jsonify({'error': 'Unauthorized'}), 401

    user_id = session['user_id']
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500

    try:
        cursor = conn.cursor(dictionary=True)

        # ── 1. Fetch completed sell trades (closed positions) ──
        cursor.execute("""
            SELECT t.id, t.coin_id, t.amount, t.price AS buy_price,
                   t.sold_price, t.timestamp AS sell_time,
                   t.buy_transaction_id,
                   bt.timestamp AS buy_time
            FROM transactions t
            LEFT JOIN transactions bt ON t.buy_transaction_id = bt.id
            WHERE t.user_id = %s AND t.type = 'sell'
              AND t.sold_price IS NOT NULL AND t.price IS NOT NULL
            ORDER BY t.timestamp DESC
            LIMIT 50
        """, (user_id,))
        sells = cursor.fetchall()

        # ── 2. Fetch order history (for stop-loss / take-profit detection) ──
        cursor.execute("""
            SELECT id, order_type, side, base_currency, status,
                   created_at, filled_at
            FROM orders
            WHERE user_id = %s
            ORDER BY created_at DESC
            LIMIT 100
        """, (user_id,))
        orders = cursor.fetchall()

        # ── 3. Count total buy transactions for overtrading detection ──
        cursor.execute("""
            SELECT COUNT(*) AS total_buys,
                   MIN(timestamp) AS first_trade,
                   MAX(timestamp) AS last_trade
            FROM transactions
            WHERE user_id = %s AND type = 'buy'
        """, (user_id,))
        buy_stats = cursor.fetchone()

        if not sells or len(sells) < 2:
            return jsonify({
                'has_data': False,
                'message': 'Complete at least 2 trades (buy + sell) to unlock your AI coaching report.'
            })

        # ── Build trade summaries ──
        trades = []
        for s in sells:
            bp = float(s['buy_price']) if s['buy_price'] else 0
            sp = float(s['sold_price']) if s['sold_price'] else 0
            amt = float(s['amount']) if s['amount'] else 0

            pl_pct = ((sp - bp) / bp * 100) if bp > 0 else 0
            pl_abs = (sp - bp) * amt

            # Holding time
            hold_seconds = 0
            hold_label = 'Unknown'
            if s.get('buy_time') and s.get('sell_time'):
                delta = s['sell_time'] - s['buy_time']
                hold_seconds = delta.total_seconds()
                if hold_seconds < 300:
                    hold_label = 'Scalp (<5m)'
                elif hold_seconds < 3600:
                    hold_label = 'Short (<1h)'
                elif hold_seconds < 86400:
                    hold_label = 'Intraday'
                elif hold_seconds < 604800:
                    hold_label = 'Swing (days)'
                else:
                    hold_label = 'Position (1w+)'

            # Stop-loss / Take-profit usage detection
            used_sl = False
            used_tp = False
            for o in orders:
                if (o['base_currency'] == s['coin_id']
                        and o['status'] == 'filled'
                        and o['side'] == 'sell'):
                    if o['order_type'] == 'stop_loss':
                        used_sl = True
                    elif o['order_type'] == 'take_profit':
                        used_tp = True

            # Classify entry timing heuristically
            entry_timing = 'Confirmed'
            if hold_seconds > 0 and hold_seconds < 120:
                entry_timing = 'Early'
            elif hold_seconds > 604800:
                entry_timing = 'Late'

            # Detect mistake type
            mistake = None
            if pl_pct < -15:
                mistake = 'Large loss – no stop-loss' if not used_sl else 'Large loss despite stop-loss'
            elif pl_pct < -5 and hold_seconds < 600:
                mistake = 'Panic sell'
            elif pl_pct > 0 and pl_pct < 2 and hold_seconds > 86400:
                mistake = 'Held too long for tiny gain'
            elif pl_pct > 15 and not used_tp:
                mistake = 'No take-profit set on winner'

            trades.append({
                'coin': s['coin_id'],
                'pl_pct': round(pl_pct, 2),
                'pl_abs': round(pl_abs, 2),
                'used_stop_loss': used_sl,
                'used_take_profit': used_tp,
                'entry_timing': entry_timing,
                'hold_time': hold_label,
                'hold_seconds': hold_seconds,
                'mistake': mistake,
            })

        # ── 4. Pattern detection ──
        n = len(trades)
        wins = [t for t in trades if t['pl_pct'] > 0]
        losses = [t for t in trades if t['pl_pct'] <= 0]
        win_rate = len(wins) / n * 100

        sl_count = sum(1 for t in trades if t['used_stop_loss'])
        sl_rate = sl_count / n * 100

        tp_count = sum(1 for t in trades if t['used_take_profit'])
        tp_rate = tp_count / n * 100

        early_count = sum(1 for t in trades if t['entry_timing'] == 'Early')
        early_rate = early_count / n * 100

        panic_sells = sum(1 for t in trades if t['mistake'] == 'Panic sell')
        large_losses = sum(1 for t in trades if t['mistake'] and 'Large loss' in t['mistake'])
        no_tp_on_wins = sum(1 for t in trades if t['mistake'] == 'No take-profit set on winner')

        avg_hold = sum(t['hold_seconds'] for t in trades if t['hold_seconds'] > 0)
        avg_hold = avg_hold / n if n > 0 else 0

        avg_win = sum(t['pl_pct'] for t in wins) / len(wins) if wins else 0
        avg_loss = sum(t['pl_pct'] for t in losses) / len(losses) if losses else 0

        # Overtrading: more than 5 trades per day on average
        total_buys = buy_stats['total_buys'] or 0
        trading_days = 1
        if buy_stats.get('first_trade') and buy_stats.get('last_trade'):
            span = (buy_stats['last_trade'] - buy_stats['first_trade']).total_seconds()
            trading_days = max(span / 86400, 1)
        trades_per_day = total_buys / trading_days
        is_overtrading = trades_per_day > 5

        # ── 5. Classify user type ──
        scores = {
            'Impulsive Trader': 0,
            'Risk-Aware Beginner': 0,
            'Overcautious Trader': 0,
            'Disciplined Trader': 0,
            'Inconsistent Trader': 0,
        }

        # Impulsive
        if early_rate > 40:
            scores['Impulsive Trader'] += 3
        if panic_sells >= 2:
            scores['Impulsive Trader'] += 3
        if is_overtrading:
            scores['Impulsive Trader'] += 2
        if sl_rate < 20:
            scores['Impulsive Trader'] += 2

        # Risk-Aware Beginner
        if sl_rate > 30 and sl_rate < 70:
            scores['Risk-Aware Beginner'] += 3
        if win_rate > 35 and win_rate < 55:
            scores['Risk-Aware Beginner'] += 2
        if avg_hold > 3600:
            scores['Risk-Aware Beginner'] += 1

        # Overcautious
        if avg_hold > 259200:  # 3+ days avg
            scores['Overcautious Trader'] += 3
        if win_rate > 50 and avg_win < 3:
            scores['Overcautious Trader'] += 3
        if tp_rate > 60:
            scores['Overcautious Trader'] += 2

        # Disciplined
        if sl_rate > 60:
            scores['Disciplined Trader'] += 3
        if win_rate > 50:
            scores['Disciplined Trader'] += 2
        if not is_overtrading:
            scores['Disciplined Trader'] += 1
        if panic_sells == 0:
            scores['Disciplined Trader'] += 2

        # Inconsistent
        if sl_rate > 20 and sl_rate < 60:
            scores['Inconsistent Trader'] += 1
        if abs(avg_win) > 0 and abs(avg_loss) > 0:
            rr = abs(avg_win / avg_loss) if avg_loss != 0 else 99
            if 0.5 < rr < 1.5 and win_rate > 40 and win_rate < 60:
                scores['Inconsistent Trader'] += 3
        variations = [t['pl_pct'] for t in trades]
        if len(variations) > 3:
            import statistics
            pl_stdev = statistics.stdev(variations)
            if pl_stdev > 10:
                scores['Inconsistent Trader'] += 2

        user_type = max(scores, key=scores.get)

        # ── 6. Strengths / Weaknesses ──
        strengths = []
        weaknesses = []

        if win_rate >= 55:
            strengths.append(f'Solid win rate of {win_rate:.0f}% – you pick profitable entries')
        elif win_rate >= 45:
            strengths.append(f'Near-balanced win rate ({win_rate:.0f}%) – room to grow but not reckless')

        if sl_rate >= 50:
            strengths.append(f'Uses stop-loss on {sl_rate:.0f}% of trades – good risk management habit')
        if panic_sells == 0 and n >= 3:
            strengths.append('No panic-sell behavior detected – emotionally steady')
        if avg_hold > 3600 and avg_hold < 604800:
            strengths.append('Balanced holding times – lets trades develop without overholding')

        if not strengths:
            strengths.append('Taking trades and gaining experience – every trade teaches something')

        if sl_rate < 30:
            weaknesses.append(f'Stop-loss used on only {sl_rate:.0f}% of trades – high drawdown risk')
        if panic_sells >= 2:
            weaknesses.append(f'Panic-sold {panic_sells} times – reacting emotionally to dips')
        if is_overtrading:
            weaknesses.append(f'Averaging {trades_per_day:.1f} trades/day – signs of overtrading')
        if early_rate > 40:
            weaknesses.append(f'{early_rate:.0f}% of entries are early (< 2 min holds) – entering before confirmation')
        if large_losses >= 2:
            weaknesses.append(f'{large_losses} trades with 15%+ losses – missing downside protection')
        if win_rate < 40:
            weaknesses.append(f'Win rate of {win_rate:.0f}% – more losing trades than winners')

        if not weaknesses:
            weaknesses.append('Keep tracking – more data will reveal clearer patterns')

        # Trim to 2 each
        strengths = strengths[:2]
        weaknesses = weaknesses[:2]

        # ── 7. Critical pattern (ALWAYS meaningful – never generic) ──
        # Compute reward-to-risk ratio for deeper analysis
        rr_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else (99 if avg_win > 0 else 0)

        critical_patterns = []
        if sl_rate < 25:
            critical_patterns.append(('Skipping stop-loss frequently – exposing capital to unlimited downside', 92))
        if panic_sells >= 2:
            critical_patterns.append(('Panic selling during price dips – exits driven by fear, not strategy', 85))
        if is_overtrading:
            critical_patterns.append(('Overtrading – quantity over quality dilutes edge', 80))
        if early_rate > 50:
            critical_patterns.append(('Entering trades too early without confirmation signals', 75))
        if large_losses >= 2 and sl_rate < 40:
            critical_patterns.append(('Taking large unprotected losses – single trades wiping out multiple winners', 88))
        if win_rate < 35:
            critical_patterns.append(('Low win rate indicates poor entry selection or timing', 70))

        # Deeper structural patterns (applied even when no "mistakes" exist)
        if rr_ratio < 1.0 and avg_loss != 0:
            critical_patterns.append((
                f'Losses are larger than wins (avg loss {avg_loss:+.1f}% vs avg win {avg_win:+.1f}%) – '
                f'a single loss erases {1/rr_ratio:.1f}x of your average win',
                86
            ))
        if win_rate < 50 and rr_ratio < 1.5:
            critical_patterns.append((
                f'Win rate ({win_rate:.0f}%) and reward-to-risk ({rr_ratio:.1f}:1) are both below breakeven thresholds – '
                f'you need either higher accuracy or bigger winners to be profitable',
                83
            ))
        if win_rate >= 50 and avg_win < 3:
            critical_patterns.append((
                f'Cutting winners too short – you win {win_rate:.0f}% of trades but average only +{avg_win:.1f}% per win',
                72
            ))
        if no_tp_on_wins >= 2:
            critical_patterns.append((
                f'{no_tp_on_wins} winning trades had no take-profit set – you\'re leaving gains to chance',
                68
            ))
        # Inconsistent trade selection
        if len(variations) > 3:
            import statistics as _stats
            _stdev = _stats.stdev(variations)
            if _stdev > 12:
                critical_patterns.append((
                    f'High P/L variance (σ={_stdev:.1f}%) – trade selection is inconsistent, suggesting no repeatable strategy',
                    74
                ))

        # Fallback: always provide a meaningful limitation
        if not critical_patterns:
            if rr_ratio >= 1.0 and win_rate >= 50:
                critical_patterns.append((
                    f'Solid fundamentals but limited sample ({n} trades) – '
                    f'current edge of {rr_ratio:.1f}:1 R:R at {win_rate:.0f}% accuracy needs validation over 20+ trades',
                    50
                ))
            else:
                critical_patterns.append((
                    'No clear repeatable edge detected – trades appear reactive rather than strategy-driven',
                    55
                ))

        critical_patterns.sort(key=lambda x: x[1], reverse=True)
        critical_pattern = critical_patterns[0][0]

        # ── 8. Edge Insight (profitability structure analysis) ──
        edge_insight = ''
        if avg_loss != 0 and avg_win != 0:
            # Calculate breakeven win rate for this R:R
            breakeven_wr = (1 / (1 + rr_ratio)) * 100 if rr_ratio > 0 else 100
            is_profitable_structure = win_rate > breakeven_wr

            if rr_ratio < 0.8:
                edge_insight = (
                    f'Your average loss ({avg_loss:+.1f}%) is significantly larger than your average win ({avg_win:+.1f}%), '
                    f'giving a reward-to-risk ratio of {rr_ratio:.2f}:1. '
                    f'At this ratio, you need to win {breakeven_wr:.0f}%+ of trades just to break even. '
                    f'Your current win rate of {win_rate:.0f}% {"meets" if is_profitable_structure else "falls short of"} this threshold.'
                )
            elif rr_ratio < 1.2:
                edge_insight = (
                    f'Wins and losses are nearly equal in size (R:R = {rr_ratio:.2f}:1), '
                    f'so your profitability depends almost entirely on win rate. '
                    f'At {win_rate:.0f}%, you are {"slightly profitable" if win_rate > 52 else "near breakeven" if win_rate > 48 else "likely losing money over time"}. '
                    f'Focus on either increasing win rate above 55% OR letting winners run further.'
                )
            elif rr_ratio < 2.0:
                edge_insight = (
                    f'Decent reward-to-risk ratio of {rr_ratio:.2f}:1 – your winners are larger than losers. '
                    f'Breakeven requires just {breakeven_wr:.0f}% accuracy, and you\'re at {win_rate:.0f}%. '
                    f'{"This is a viable edge – protect it with consistent execution." if is_profitable_structure else "Improve entry accuracy to unlock this structural advantage."}'
                )
            else:
                edge_insight = (
                    f'Strong reward-to-risk of {rr_ratio:.2f}:1 – you let winners run. '
                    f'Even with a {win_rate:.0f}% win rate, this structure can be profitable (breakeven at {breakeven_wr:.0f}%). '
                    f'{"You have a quantifiable edge. Focus on consistency and position sizing." if is_profitable_structure else "Your entries need work – the R:R is excellent but accuracy is dragging you down."}'
                )
        elif wins and not losses:
            edge_insight = f'All {len(wins)} trades were profitable – impressive but too few to confirm a durable edge. Keep trading to validate.'
        elif losses and not wins:
            edge_insight = f'All {len(losses)} trades resulted in losses. Re-evaluate your entry criteria before taking more positions.'
        else:
            edge_insight = 'Insufficient data to analyze profitability structure. Complete more trades for a meaningful assessment.'

        # ── 9. Personalized advice ──
        advice_lines = []
        if 'stop-loss' in critical_pattern.lower() or 'unprotected' in critical_pattern.lower():
            advice_lines.append(
                'Set a stop-loss on EVERY trade before entering. '
                'Use the stop_loss order type to automate exits at 5-10% below entry.'
            )
            advice_lines.append(
                'Review your last 3 largest losses – calculate how much you would have saved with a 7% stop-loss.'
            )
        elif 'panic' in critical_pattern.lower():
            advice_lines.append(
                'Before selling during a dip, wait 15 minutes and check if the price is still dropping. '
                'Most panic dips recover within an hour.'
            )
            advice_lines.append(
                'Pre-set your exit plan using take-profit and stop-loss orders so you never sell on emotion.'
            )
        elif 'overtrad' in critical_pattern.lower():
            advice_lines.append(
                f'You are averaging {trades_per_day:.1f} trades/day. '
                'Limit yourself to 2-3 high-conviction trades per day and journal each one.'
            )
            advice_lines.append(
                'Before each trade ask: "Would I bet 10% of my portfolio on this?" If not, skip it.'
            )
        elif 'early' in critical_pattern.lower():
            advice_lines.append(
                'Wait for at least 2 confirmation signals (e.g. volume spike + support level hold) before entering.'
            )
            advice_lines.append(
                'Use limit orders at planned entry prices instead of market orders to enforce discipline.'
            )
        elif 'win rate' in critical_pattern.lower() or 'accuracy' in critical_pattern.lower():
            advice_lines.append(
                'Paper-trade your next 5 ideas and only execute the ones that would have been profitable.'
            )
            advice_lines.append(
                'Start with high-cap coins (BTC, ETH) to reduce picking the wrong asset.'
            )
        elif 'cutting winners' in critical_pattern.lower() or 'too short' in critical_pattern.lower():
            advice_lines.append(
                'Use trailing stop-losses to lock in partial profits while letting strong trends continue.'
            )
            advice_lines.append(
                'Set take-profit targets at 2x your stop-loss distance to enforce a minimum 2:1 reward-to-risk ratio.'
            )
        elif 'losses are larger' in critical_pattern.lower() or 'erases' in critical_pattern.lower():
            advice_lines.append(
                'Size your stop-losses BEFORE entering so that max loss per trade is fixed at 5-8%. '
                'Never move a stop-loss further away after entry.'
            )
            advice_lines.append(
                'Aim for a minimum 1.5:1 reward-to-risk on every trade – if the setup doesn\'t offer it, skip the trade.'
            )
        elif 'variance' in critical_pattern.lower() or 'inconsistent' in critical_pattern.lower():
            advice_lines.append(
                'Define a specific setup you\'ll trade (e.g., breakout above resistance with volume) '
                'and ONLY take trades that match this setup for the next 10 trades.'
            )
            advice_lines.append(
                'Journal every trade with entry reason, exit reason, and what you\'d do differently. '
                'Review weekly to spot repeating errors.'
            )
        else:
            advice_lines.append(
                'Create a written trading plan with entry rules, position sizing, and exit strategy. '
                'Follow it mechanically for 10 trades before making any changes.'
            )
            advice_lines.append(
                'Measure your expectancy: (Win% × Avg Win) – (Loss% × Avg Loss). '
                'If negative, reduce position size and refine entries before scaling up.'
            )

        # ── 10. Next Focus (1 priority improvement) ──
        next_focus = ''
        if sl_rate < 30:
            next_focus = 'Priority: Use a stop-loss on your next 5 trades without exception.'
        elif rr_ratio < 1.0 and avg_loss != 0:
            next_focus = 'Priority: Tighten stops or widen targets to achieve at least a 1:1 reward-to-risk ratio.'
        elif win_rate < 45:
            next_focus = 'Priority: Improve entry accuracy – wait for trend confirmation before buying.'
        elif avg_win < 3 and win_rate >= 50:
            next_focus = 'Priority: Let your next winning trade run 50% longer before taking profit.'
        elif is_overtrading:
            next_focus = 'Priority: Limit to max 3 trades per day for the next week.'
        elif panic_sells > 0:
            next_focus = 'Priority: Pre-set stop-loss and take-profit orders on every trade to eliminate emotional exits.'
        else:
            next_focus = 'Priority: Track your next 10 trades in a journal and compute your real expectancy.'

        # ── 11. Confidence level ──
        if n >= 10:
            confidence = 'High'
            confidence_reason = f'Based on {n} completed trades – patterns are statistically meaningful'
        elif n >= 5:
            confidence = 'Medium'
            confidence_reason = f'Based on {n} trades – patterns are emerging but need more data to confirm'
        else:
            confidence = 'Low'
            confidence_reason = f'Only {n} trades analyzed – too few for reliable behavioral conclusions'

        # ── 12. Build behavior summary ──
        summary_parts = []
        summary_parts.append(
            f'Across {n} completed trades, you have a {win_rate:.0f}% win rate '
            f'with an average gain of {avg_win:+.1f}% on winners and {avg_loss:+.1f}% on losers.'
        )
        if sl_rate > 50:
            summary_parts.append(f'You set stop-losses on most trades ({sl_rate:.0f}%), showing risk awareness.')
        elif sl_rate > 0:
            summary_parts.append(f'Stop-loss usage is inconsistent ({sl_rate:.0f}%), leaving you exposed to large drawdowns.')
        else:
            summary_parts.append('No stop-loss orders detected – you are trading without a safety net.')

        if is_overtrading:
            summary_parts.append(f'Your trading frequency ({trades_per_day:.1f}/day) suggests overtrading tendencies.')
        elif rr_ratio < 1.0 and avg_loss != 0:
            summary_parts.append(f'Your losses outweigh your wins ({rr_ratio:.2f}:1 R:R), which limits long-term profitability.')

        behavior_summary = ' '.join(summary_parts[:3])

        return jsonify({
            'has_data': True,
            'user_type': user_type,
            'behavior_summary': behavior_summary,
            'strengths': strengths,
            'weaknesses': weaknesses,
            'critical_pattern': critical_pattern,
            'edge_insight': edge_insight,
            'advice': advice_lines,
            'next_focus': next_focus,
            'confidence': confidence,
            'confidence_reason': confidence_reason,
            'stats': {
                'total_trades': n,
                'win_rate': round(win_rate, 1),
                'avg_win': round(avg_win, 1),
                'avg_loss': round(avg_loss, 1),
                'sl_rate': round(sl_rate, 1),
                'trades_per_day': round(trades_per_day, 1),
                'rr_ratio': round(rr_ratio, 2),
            },
            'trades': trades[:10],
        })

    except mysql.connector.Error as err:
        print(f"Trading coach DB error: {err}")
        return jsonify({'error': f'Database error: {err}'}), 500
    except Exception as ex:
        print(f"Trading coach error: {ex}")
        traceback.print_exc()
        return jsonify({'error': str(ex)}), 500
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()

# ===========================================================================
# LEARN PAGE — RAG AI Tutor
# ===========================================================================

@app.route('/learn')
def learn():
    if 'user_id' not in session or session.get('expires_at', 0) < datetime.now().timestamp():
        return redirect(url_for('login'))
    conn = get_db_connection()
    user = None
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM users WHERE id = %s", (session['user_id'],))
            user = cursor.fetchone()
        finally:
            if conn.is_connected():
                cursor.close()
                conn.close()
    return render_template('combined.html', section='learn', user=user)


CRYPTO_KNOWLEDGE_BASE = [
    {
        "title": "What is Cryptocurrency?",
        "tags": ["beginner", "crypto", "blockchain"],
        "content": "Cryptocurrency is a digital currency using cryptography on decentralized blockchains. Key concepts: Blockchain (distributed ledger), Decentralization (no single authority), Digital wallets (store private keys), Market cap (price × supply), Volatility (10-20% daily swings possible).",
    },
    {
        "title": "Reading Candlestick Charts",
        "tags": ["charts", "candlestick", "OHLCV", "technical-analysis"],
        "content": "Each candle shows Open, High, Low, Close for a time period. Green = close > open (up). Red = close < open (down). Body = thick part (open-close range). Wicks = thin lines (high/low). Patterns: Doji (indecision), Hammer (reversal), Engulfing (strong reversal), Morning Star (bullish reversal). Volume confirms moves.",
    },
    {
        "title": "Order Types",
        "tags": ["orders", "market-order", "limit-order", "stop-loss", "take-profit"],
        "content": "Market Order: buy/sell immediately at best price. Pros: instant. Cons: slippage. Limit Order: execute only at specific price or better. Stop-Loss: auto-sells when price drops to level — #1 risk tool, ALWAYS use. Take-Profit: auto-sells at target price to lock gains. Stop-Limit: triggers limit order at stop price.",
    },
    {
        "title": "Trading Fees and Slippage",
        "tags": ["fees", "slippage", "spread", "costs"],
        "content": "Fees: 0.1-0.5% per trade. Maker fees (limit) < Taker fees (market). Slippage: difference between expected and actual price. Spread: gap between bid/ask. Impact: 0.3% costs per trade means 0.6% profit needed per round trip to break even. Over many trades, fees compound significantly.",
    },
    {
        "title": "Moving Average Crossover Strategy",
        "tags": ["strategy", "moving-average", "crossover", "golden-cross"],
        "content": "Use short MA (e.g. 50) and long MA (e.g. 200). Buy when short crosses above long (Golden Cross). Sell when short crosses below (Death Cross). SMA = equal weight, EMA = more weight on recent. Pairs: 9/21 EMA (day trading), 20/50 SMA (swing), 50/200 SMA (long-term). Works well in trends, poor in sideways markets. Combine with volume confirmation.",
    },
    {
        "title": "RSI Strategy",
        "tags": ["strategy", "RSI", "momentum", "overbought", "oversold"],
        "content": "RSI ranges 0-100, typically 14-period. Oversold (RSI<30) = potential buy. Overbought (RSI>70) = potential sell. Divergence: price makes new high but RSI doesn't = bearish signal. Centerline: above 50 = bullish, below = bearish. Caveat: RSI can stay extreme in strong trends. Best in range-bound markets.",
    },
    {
        "title": "Breakout Strategy",
        "tags": ["strategy", "breakout", "support", "resistance"],
        "content": "Enter when price moves beyond support/resistance with volume. Buy: close above resistance + high volume. Sell: close below support + high volume. Fakeouts are common — wait for candle close, require 2x+ volume. Set stops just beyond the broken level. Look at recent highs/lows over 20-50 candles.",
    },
    {
        "title": "Mean Reversion Strategy",
        "tags": ["strategy", "mean-reversion", "dip-buying", "bollinger"],
        "content": "Prices tend to return to average. Buy when price drops X% (3-8%) below MA. Sell when price returns to MA. Use Bollinger Bands — buy at lower band, sell at middle. Risk: catching falling knife. Always use stop-loss. Works best in uptrends/sideways, NOT in downtrends.",
    },
    {
        "title": "Position Sizing and 1-2% Rule",
        "tags": ["risk", "position-sizing", "capital-management"],
        "content": "Never risk more than 1-2% of capital per trade. Formula: Position Size = (Account × Risk%) / Stop-Loss%. Example: $10K account, 2% risk, 5% stop = $4,000 position. With 2% rule, 10 consecutive losses = still 80% capital left. With 10% risk, 5 losses = 50% gone. Never go all-in.",
    },
    {
        "title": "Stop-Loss Strategies",
        "tags": ["risk", "stop-loss", "protection"],
        "content": "Types: Fixed % (e.g. 5%), Support-based, ATR-based (dynamic), Trailing (follows price up). Place below swing lows or support, NOT at round numbers. Never move stops further away. Math: 10% loss needs 11.1% to recover; 50% loss needs 100% to recover. Set stop BEFORE entering trade.",
    },
    {
        "title": "Risk-Reward Ratio",
        "tags": ["risk", "risk-reward", "R:R", "profitability"],
        "content": "R:R = Potential Reward / Potential Risk. At 1:1 need >50% win rate. At 2:1 need >33%. At 3:1 need >25%. Minimum acceptable: 2:1. Never take trades below 1:1. Improve with better entries (pullbacks), wider targets, tighter stops. Most profitable traders have 40-50% win rate but 2:1-4:1 R:R.",
    },
    {
        "title": "Portfolio Diversification",
        "tags": ["risk", "diversification", "portfolio", "allocation"],
        "content": "Spread capital across assets. By market cap, sector, strategy. Suggested: 40-50% BTC+ETH, 20-30% established alts, 10-20% small caps, 10-20% stablecoins. Sweet spot: 5-8 positions. Beware correlation — most alts move with BTC.",
    },
    {
        "title": "Support and Resistance",
        "tags": ["technical-analysis", "support", "resistance"],
        "content": "Support = price floor (buying pressure). Resistance = ceiling (selling pressure). More bounces = stronger level. Broken support becomes resistance (role reversal). Identify via: multiple reversals, round numbers, previous highs/lows. S/R are zones, not exact prices.",
    },
    {
        "title": "Volume Analysis",
        "tags": ["technical-analysis", "volume", "confirmation"],
        "content": "Volume = units traded per period. Rising price + rising volume = strong uptrend. Rising price + falling volume = weak (potential reversal). Volume spikes = significant events. Breakouts need 2x+ average volume. Low volume pullbacks = healthy corrections.",
    },
    {
        "title": "Trading Psychology and Emotions",
        "tags": ["psychology", "emotions", "FOMO", "discipline"],
        "content": "Emotions are #1 reason traders lose. FOMO: buying at tops. Fear: panic selling dips. Greed: not taking profits. Revenge trading: bigger bets after losses. Solutions: plan before trading, use backtester, take breaks after 3 losses, journal trades, stick to rules. Process over outcome.",
    },
    {
        "title": "Common Beginner Mistakes",
        "tags": ["psychology", "mistakes", "beginner"],
        "content": "1) No stop-losses. 2) No trading plan. 3) Overtrading (fees compound). 4) Chasing pumps. 5) Ignoring fees. 6) No research. 7) Leverage too early. 8) Trading money you can't afford to lose. 9) No risk management. 10) Comparing to others highlight reels. CoinPrep lets you make these mistakes with VIRTUAL money.",
    },
    {
        "title": "Using CoinPrep Dashboard",
        "tags": ["app", "dashboard", "guide"],
        "content": "Stats: CryptoBucks (virtual currency), USDT balance, Risk Tolerance (from quiz), Active Alerts. Price Alerts section shows triggered alerts with TRADE button. Market Overview table has top coins with price/24h/cap. Archived Trades shows completed trades with P/L. AI Coach (side drawer) analyzes your trading behavior.",
    },
    {
        "title": "Using CoinPrep Backtester",
        "tags": ["app", "backtester", "guide"],
        "content": "1) Select coin. 2) Pick strategy (MA Crossover, RSI, Breakout, Mean Reversion). 3) Set parameters. 4) Configure risk (capital, position size, fees, slippage, stop-loss, take-profit). 5) Run. Results: Total Return, Win Rate, Sharpe Ratio (>1 good, >2 excellent), Max Drawdown, R:R Ratio. Equity curve shows capital over time.",
    },
    {
        "title": "Using CoinPrep Alerts",
        "tags": ["app", "alerts", "guide"],
        "content": "Create alert: select coin → condition (above/below) → target price → save. Set alerts at support/resistance levels, desired buy prices, profit targets, breakout levels. Pro tip: set alerts BEFORE levels are reached to plan trades calmly.",
    },
    {
        "title": "CoinPrep Risk Quiz",
        "tags": ["app", "risk-quiz", "guide"],
        "content": "Determines risk tolerance: Conservative (large-caps, smaller positions), Moderate (balanced), Aggressive (more altcoins, still use stop-losses). Risk tolerance guides position sizing and strategy selection. Retake periodically as experience grows.",
    },
]


def _rag_retrieve(query, top_k=5):
    """Simple keyword-scored RAG retrieval from the knowledge base."""
    words = [w for w in query.lower().split() if len(w) > 2]
    scored = []
    for entry in CRYPTO_KNOWLEDGE_BASE:
        score = 0
        text = f"{entry['title']} {entry['content']} {' '.join(entry['tags'])}".lower()
        for w in words:
            if w in text:
                score += 1
            if w in entry['title'].lower():
                score += 3
            if any(w in t for t in entry['tags']):
                score += 2
        scored.append((score, entry))
    scored.sort(key=lambda x: x[0], reverse=True)
    top = [e for s, e in scored if s > 0][:top_k]
    if not top:
        top = [e for _, e in scored[:3]]
    return "\n\n".join(f"### {e['title']}\n{e['content']}" for e in top)


@app.route('/api/portfolio-context', methods=['GET'])
def get_portfolio_context():
    """
    Returns the current user's live portfolio data for the AI chatbot.
    Shape matches exactly what BottomTutorChat.tsx sends as userContext.
    """
    if 'user_id' not in session or session.get('expires_at', 0) < datetime.now().timestamp():
        return jsonify({'error': 'Not authenticated'}), 401

    user_id = session['user_id']
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database unavailable'}), 500

    try:
        cursor = conn.cursor(dictionary=True)

        # ── 1. User basics ──────────────────────────────────────────────
        cursor.execute(
            "SELECT username, crypto_bucks, tether_balance, risk_tolerance FROM users WHERE id = %s",
            (user_id,)
        )
        user = cursor.fetchone()
        if not user:
            return jsonify({'error': 'User not found'}), 404

        username       = user['username']
        crypto_bucks   = float(user['crypto_bucks'] or 0)
        tether_balance = float(user['tether_balance'] or 0)
        risk_tolerance = user.get('risk_tolerance') or 'Not set'

        # ── 2. Open holdings (buy txns minus sold amounts) ──────────────
        cursor.execute("""
            SELECT coin_id,
                   SUM(amount) AS total_bought,
                   AVG(price)  AS avg_price
            FROM transactions
            WHERE user_id = %s AND type = 'buy'
            GROUP BY coin_id
        """, (user_id,))
        buys = {row['coin_id']: {
            'total_bought': float(row['total_bought'] or 0),
            'avg_price':    float(row['avg_price'] or 0)
        } for row in cursor.fetchall()}

        cursor.execute("""
            SELECT coin_id, SUM(amount) AS total_sold
            FROM transactions
            WHERE user_id = %s AND type = 'sell'
            GROUP BY coin_id
        """, (user_id,))
        sold_map = {row['coin_id']: float(row['total_sold'] or 0)
                    for row in cursor.fetchall()}

        holdings = []
        for coin_id, data in buys.items():
            remaining = data['total_bought'] - sold_map.get(coin_id, 0.0)
            if remaining > 0.000001:
                holdings.append({
                    'coin_id': coin_id,
                    'amount':  round(remaining, 8),
                    'avg_buy_price': round(data['avg_price'], 2)
                })

        # ── 3. Recent sell transactions (last 10) ───────────────────────
        cursor.execute("""
            SELECT coin_id, amount, price AS buy_price, sold_price,
                   ROUND((sold_price - price) * amount, 2) AS profit
            FROM transactions
            WHERE user_id = %s AND type = 'sell' AND sold_price IS NOT NULL
            ORDER BY id DESC
            LIMIT 10
        """, (user_id,))
        recent_sells = cursor.fetchall()

        cursor.close()

        # ── 4. Fetch live prices for open holdings ─────────────────────
        live_prices = {}
        if holdings:
            coin_ids_str = ','.join(h['coin_id'] for h in holdings)
            try:
                resp = requests.get(
                    f"{COINGECKO_API}/coins/markets?vs_currency=usd&ids={coin_ids_str}",
                    timeout=8
                )
                if resp.status_code == 200:
                    for c in resp.json():
                        live_prices[c['id']] = float(c.get('current_price', 0))
            except Exception:
                pass   # fall back to no live price

        # ── 5. Build userContext strings ───────────────────────────────
        portfolio_parts = []
        total_unrealized = 0.0
        for h in holdings:
            coin    = h['coin_id'].upper()
            amount  = h['amount']
            avg_buy = h['avg_buy_price']
            current = live_prices.get(h['coin_id'], 0)
            unreal  = round((current - avg_buy) * amount, 2) if current else None
            if unreal is not None:
                total_unrealized += unreal
                unreal_str = f"(UnrealizedP/L: ${unreal:+.2f})"
            else:
                unreal_str = ""
            portfolio_parts.append(
                f"{amount} {coin} @ avg ${avg_buy} {unreal_str}".strip()
            )

        portfolio_str = "; ".join(portfolio_parts) if portfolio_parts else "No open holdings"

        recent_trades_parts = []
        for t in recent_sells:
            coin    = str(t['coin_id']).upper()
            profit  = float(t['profit'] or 0)
            b_price = float(t['buy_price'] or 0)
            s_price = float(t['sold_price'] or 0)
            recent_trades_parts.append(
                f"{coin}: bought ${b_price:.2f}, sold ${s_price:.2f}, P/L: ${profit:+.2f}"
            )
        recent_trades_str = "; ".join(recent_trades_parts) if recent_trades_parts else "No recent trades"

        return jsonify({
            'username':      username,
            'cryptoBucks':   str(round(crypto_bucks, 2)),
            'tetherBalance': str(round(tether_balance, 2)),
            'riskTolerance': risk_tolerance,
            'portfolio':     portfolio_str,
            'recentTrades':  recent_trades_str,
            # extra structured data for richer display
            'holdingsCount':     len(holdings),
            'totalUnrealized':   round(total_unrealized, 2),
        })

    except Exception as e:
        print(f"Error in /api/portfolio-context: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        if conn.is_connected():
            conn.close()


@app.route('/api/ai-tutor', methods=['POST'])
def ai_tutor_chat():
    """RAG-powered AI tutor endpoint — streams Gemini responses."""
    if 'user_id' not in session or session.get('expires_at', 0) < datetime.now().timestamp():
        return jsonify({'error': 'Not authenticated'}), 401

    try:
        payload = request.get_json(force=True)
        messages = payload.get('messages', [])
        user_context = payload.get('userContext', {})

        # Retrieve RAG context from most recent user message
        last_user = next((m['content'] for m in reversed(messages) if m.get('role') == 'user'), '')
        rag_context = _rag_retrieve(last_user)

        personal_ctx = ""
        if user_context:
            personal_ctx = f"""
CURRENT USER CONTEXT:
- Username: {user_context.get('username', 'Unknown')}
- CryptoBucks Balance: ${user_context.get('cryptoBucks', 0)}
- USDT Balance: ${user_context.get('tetherBalance', 0)}
- Risk Tolerance: {user_context.get('riskTolerance', 'Not set')}
- Portfolio: {user_context.get('portfolio', 'No holdings')}
- Recent Trades: {user_context.get('recentTrades', 'No recent trades')}
"""

        system_prompt = f"""You are the CoinPrep AI Tutor — a friendly, knowledgeable crypto trading educator built into a trading simulator app.

YOUR ROLE:
- Teach users about cryptocurrency trading concepts clearly and practically
- Reference the user's actual portfolio, balance, and trading data when giving personalized advice
- Explain CoinPrep app features when asked
- Always emphasize risk management and responsible trading
- Keep responses focused and actionable
- Use examples with real numbers when possible
- Format responses with markdown (headers, bold, bullet points) for readability

PERSONALITY:
- Encouraging but honest — never hype or promise profits
- Patient with beginners — explain jargon when first used
- Pixel/retro gaming vibe fits the app
- Direct and concise — no filler paragraphs

IMPORTANT RULES:
- NEVER recommend specific coins to buy or give financial advice
- Always remind users this is a SIMULATOR for learning
- Emphasize that past performance doesn't guarantee future results
- When discussing strategies, always mention their limitations
- If unsure about something, say so honestly

{personal_ctx}

RELEVANT KNOWLEDGE BASE CONTEXT:
{rag_context}

Use the knowledge base context above to inform your answers. If the user asks something not covered, provide your best educational response while noting it's general information."""

        api_key = os.environ.get('GEMINI_API_KEY')
        if not api_key:
            return jsonify({'error': 'AI service not configured'}), 500

        # Capture for closure
        _system_prompt = system_prompt
        _messages = messages
        _last_user = last_user

        def generate_stream():
            import json as _json
            try:
                from google import genai as _gai
                client = _gai.Client(api_key=api_key)

                # Build single prompt: system context + full conversation history
                conv_parts = [_system_prompt, '']
                for msg in _messages:
                    prefix = 'User' if msg['role'] == 'user' else 'Assistant'
                    conv_parts.append(f"{prefix}: {msg['content']}")
                conv_parts.append('Assistant:')
                full_prompt = '\n'.join(conv_parts)

                # Try model candidates — gemini-3-flash-preview is the current working model
                candidate_models = ['gemini-3-flash-preview', 'gemini-2.5-flash', 'gemini-2.0-flash-lite', 'gemini-2.0-flash']
                env_model = os.environ.get('GEMINI_MODEL', '').strip()
                if env_model:
                    candidate_models.insert(0, env_model)

                import time as _time
                text = None
                last_error = None
                for model_name in candidate_models:
                    for attempt in range(2):  # retry once per model
                        try:
                            response = client.models.generate_content(
                                model=model_name,
                                contents=full_prompt,
                                config={'temperature': 0.7, 'max_output_tokens': 1024}
                            )
                            text = getattr(response, 'text', None) or str(response)
                            break
                        except Exception as me:
                            last_error = me
                            err_str = str(me).lower()
                            if '429' in err_str or 'resource_exhausted' in err_str or 'quota' in err_str:
                                if attempt == 0:
                                    _time.sleep(10)  # wait for quota reset
                                    continue
                                break  # already retried, try next model
                            if '503' in err_str or 'unavailable' in err_str or 'overloaded' in err_str:
                                _time.sleep(2)
                                continue
                            break  # non-retryable error, try next model
                    if text:
                        break

                if text:
                    # Simulate typewriter streaming — send 8 words at a time
                    words = text.split(' ')
                    chunk_size = 8
                    for i in range(0, len(words), chunk_size):
                        piece = ' '.join(words[i:i + chunk_size])
                        if i + chunk_size < len(words):
                            piece += ' '
                        data = _json.dumps({'choices': [{'delta': {'content': piece}}]})
                        yield f'data: {data}\n\n'
                else:
                    err_str = str(last_error).lower() if last_error else ''
                    if '429' in err_str or 'quota' in err_str or 'resource_exhausted' in err_str:
                        friendly = 'API rate limit reached. Please wait a minute and try again.'
                    else:
                        friendly = str(last_error) if last_error else 'No response from AI'
                    yield f'data: {_json.dumps({"error": friendly})}\n\n'

            except Exception as e:
                import json as _json2
                yield f'data: {_json2.dumps({"error": str(e)})}\n\n'
            finally:
                yield 'data: [DONE]\n\n'

        from flask import Response as FlaskResponse
        return FlaskResponse(generate_stream(), mimetype='text/event-stream',
                             headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})

    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


# ===========================================================================

if __name__ == '__main__':
    try:
        app.run(debug=True, use_reloader=True)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()