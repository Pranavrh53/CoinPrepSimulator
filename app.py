from flask import Flask, request, jsonify, render_template, session, redirect, url_for, flash, json, send_file
from flask_bcrypt import Bcrypt
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

app = Flask(__name__)
app.secret_key = os.urandom(24)
bcrypt = Bcrypt(app)

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
                return type('Response', (), {'text': json.dumps(cached_data), 'json': lambda: cached_data, 'raise_for_status': lambda: None})()
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
                    return type('Response', (), {'text': json.dumps(cached_data), 'json': lambda: cached_data, 'raise_for_status': lambda: None})()
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
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT pa.*, u.email as user_email FROM price_alerts pa JOIN users u ON pa.user_id = u.id WHERE pa.notified = 0")
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
                cursor.execute("UPDATE price_alerts SET notified = 1 WHERE id = %s", (alert['id'],))
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
    
    questions = [
        {
            'id': 'q1',
            'text': 'How would you react to a 20% drop in your portfolio value in a month?',
            'explanation': 'This question helps determine your emotional response to market volatility.',
            'options': [
                {'value': 1, 'text': 'Sell all investments immediately', 'explanation': 'Suggests low risk tolerance and potential panic selling during downturns.'},
                {'value': 2, 'text': 'Sell some to reduce risk', 'explanation': 'Indicates a cautious approach to risk management.'},
                {'value': 3, 'text': 'Hold and wait for recovery', 'explanation': 'Shows a balanced approach to market fluctuations.'},
                {'value': 4, 'text': 'Buy more to lower cost', 'explanation': 'Suggests a contrarian investment strategy and higher risk tolerance.'},
                {'value': 5, 'text': 'Significantly increase position', 'explanation': 'Indicates high risk tolerance and strong belief in long-term growth.'}
            ]
        },
        {
            'id': 'q2',
            'text': 'What is your investment time horizon?',
            'explanation': 'Your investment horizon affects your ability to handle market volatility.',
            'options': [
                {'value': 1, 'text': 'Less than 1 year', 'explanation': 'Short-term horizons require more conservative investments.'},
                {'value': 3, 'text': '1-3 years', 'explanation': 'Medium-term goals can handle some volatility.'},
                {'value': 5, 'text': '3-5 years', 'explanation': 'Allows for a balanced approach between growth and stability.'},
                {'value': 8, 'text': '5-10 years', 'explanation': 'Longer timeframes can accommodate more growth-oriented investments.'},
                {'value': 10, 'text': '10+ years', 'explanation': 'Extended horizons can weather significant market cycles.'}
            ]
        },
        {
            'id': 'q3',
            'text': 'What percentage of your income do you invest?',
            'explanation': 'This helps assess your capacity for risk based on your investment rate.',
            'options': [
                {'value': 1, 'text': 'Less than 5%', 'explanation': 'Conservative approach to investing.'},
                {'value': 3, 'text': '5-10%', 'explanation': 'Moderate investment rate with room for growth.'},
                {'value': 5, 'text': '10-20%', 'explanation': 'Aggressive saving and investing strategy.'},
                {'value': 7, 'text': '20-30%', 'explanation': 'Highly committed to building wealth through investments.'},
                {'value': 10, 'text': 'More than 30%', 'explanation': 'Maximum commitment to long-term wealth building.'}
            ]
        },
        {
            'id': 'q4',
            'text': 'Your investment knowledge level?',
            'explanation': 'Understanding investments helps in making informed decisions during market fluctuations.',
            'options': [
                {'value': 1, 'text': 'Beginner', 'explanation': 'New to investing, still learning the basics.'},
                {'value': 3, 'text': 'Some knowledge', 'explanation': 'Familiar with basic investment concepts.'},
                {'value': 5, 'text': 'Experienced', 'explanation': 'Comfortable with most investment vehicles and strategies.'},
                {'value': 7, 'text': 'Advanced', 'explanation': 'Knowledgeable about complex investment strategies.'},
                {'value': 10, 'text': 'Expert', 'explanation': 'Extensive experience with all aspects of investing.'}
            ]
        },
        {
            'id': 'q5',
            'text': 'Your main investment goal?',
            'explanation': 'Different goals require different investment approaches.',
            'options': [
                {'value': 1, 'text': 'Preserve capital', 'explanation': 'Focus on protecting your initial investment.'},
                {'value': 3, 'text': 'Generate income', 'explanation': 'Focus on regular income generation.'},
                {'value': 5, 'text': 'Balanced growth', 'explanation': 'Mix of income and capital appreciation.'},
                {'value': 8, 'text': 'Long-term growth', 'explanation': 'Focus on capital appreciation over time.'},
                {'value': 10, 'text': 'Maximum returns', 'explanation': 'Pursue highest possible returns, accepting higher risk.'}
            ]
        }
    ]
    
    if request.method == 'POST':
        try:
            # Calculate total score (max 45 points)
            score = sum(int(request.form.get(question['id'], 0)) for question in questions)
            
            # Determine risk level and recommendations
            if score <= 10:
                risk_level = 'Conservative (1/5)'
                risk_percent = 20
                recommendation = '''
                <h4>Recommended Strategy:</h4>
                <ul>
                    <li>Focus on capital preservation with low-volatility assets</li>
                    <li>Consider high-quality bonds and stable dividend stocks</li>
                    <li>Maintain higher cash positions</li>
                    <li>Consider index funds with low volatility</li>
                </ul>
                '''
            elif score <= 20:
                risk_level = 'Moderately Conservative (2/5)'
                risk_percent = 40
                recommendation = '''
                <h4>Recommended Strategy:</h4>
                <ul>
                    <li>Balanced approach with income-generating assets</li>
                    <li>Consider a mix of bonds and blue-chip stocks</li>
                    <li>Diversify across sectors and asset classes</li>
                    <li>Consider target-date or balanced mutual funds</li>
                </ul>
                '''
            elif score <= 30:
                risk_level = 'Balanced (3/5)'
                risk_percent = 60
                recommendation = '''
                <h4>Recommended Strategy:</h4>
                <ul>
                    <li>Equal balance of growth and income investments</li>
                    <li>Mix of stocks and bonds based on your time horizon</li>
                    <li>Consider index funds and ETFs for broad market exposure</li>
                    <li>Rebalance portfolio annually</li>
                </ul>
                '''
            elif score <= 38:
                risk_level = 'Growth-Oriented (4/5)'
                risk_percent = 80
                recommendation = '''
                <h4>Recommended Strategy:</h4>
                <ul>
                    <li>Focus on long-term capital appreciation</li>
                    <li>Higher allocation to stocks, particularly growth stocks</li>
                    <li>Consider sector-specific ETFs or thematic investments</li>
                    <li>Include some international exposure</li>
                </ul>
                '''
            else:
                risk_level = 'Aggressive (5/5)'
                risk_percent = 100
                recommendation = '''
                <h4>Recommended Strategy:</h4>
                <ul>
                    <li>Maximum growth potential with high-risk assets</li>
                    <li>Significant allocation to growth stocks and alternative investments</li>
                    <li>Consider small-cap, emerging markets, and sector-specific funds</li>
                    <li>Be prepared for significant short-term volatility</li>
                </ul>
                '''
            
            # Update database
            conn = get_db_connection()
            if conn:
                try:
                    cursor = conn.cursor()
                    cursor.execute("""
                        UPDATE users 
                        SET risk_tolerance = %s, risk_score = %s 
                        WHERE id = %s
                    """, (risk_level, score, session['user_id']))
                    conn.commit()
                    
                    # Get user's current risk profile
                    cursor.execute("SELECT risk_score, risk_tolerance FROM users WHERE id = %s", (session['user_id'],))
                    user_data = cursor.fetchone()
                    
                    return render_template('combined.html', 
                                       section='risk_quiz_result',
                                       risk_level=risk_level,
                                       risk_percent=risk_percent,
                                       score=score,
                                       max_score=45,
                                       user_data=user_data)
                    
                except mysql.connector.Error as err:
                    flash(f"Database error: {err}", "error")
                    return redirect(url_for('risk_quiz'))
                finally:
                    if conn.is_connected():
                        cursor.close()
                        conn.close()
            return redirect(url_for('dashboard'))
            
        except ValueError as e:
            flash("Invalid input. Please answer all questions.", "error")
            return redirect(url_for('risk_quiz'))
    
    # GET request - show the quiz
    return render_template('combined.html', section='risk_quiz', questions=questions)

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session or session.get('expires_at', 0) < datetime.now().timestamp():
        return redirect(url_for('login'))
    
    coins = []
    top_gainers = []
    top_losers = []
    trending_coins = []
    high_volume_coins = []
    
    # Fetch main coins for Market Overview
    response = fetch_with_retry(f"{COINGECKO_API}/coins/markets?vs_currency=usd&ids=bitcoin,ethereum,binancecoin,tether")
    if response:
        coins = json.loads(response.text)
    else:
        flash("Failed to fetch market data. Please try again later.", "error")
    
    # Fetch extended market data for highlights (top 100 coins)
    response = fetch_with_retry(f"{COINGECKO_API}/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=100&page=1&sparkline=false&price_change_percentage=24h")
    if response:
        all_coins = json.loads(response.text)
        
        # Top 5 Gainers (24h) - sorted by price_change_percentage_24h descending
        top_gainers = sorted(
            [c for c in all_coins if c.get('price_change_percentage_24h') is not None], 
            key=lambda x: x.get('price_change_percentage_24h', 0), 
            reverse=True
        )[:5]
        
        # Top 5 Losers (24h) - sorted by price_change_percentage_24h ascending
        top_losers = sorted(
            [c for c in all_coins if c.get('price_change_percentage_24h') is not None], 
            key=lambda x: x.get('price_change_percentage_24h', 0)
        )[:5]
        
        # High Volume coins (top 5 by volume)
        high_volume_coins = sorted(
            [c for c in all_coins if c.get('total_volume') is not None], 
            key=lambda x: x.get('total_volume', 0), 
            reverse=True
        )[:5]
    
    # Fetch trending coins
    trending_response = fetch_with_retry(f"{COINGECKO_API}/search/trending")
    if trending_response:
        trending_data = json.loads(trending_response.text)
        trending_coins = trending_data.get('coins', [])[:5]
    
    conn = get_db_connection()
    user = None
    triggered_alerts = []
    show_onboarding = False
    
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT crypto_bucks, tether_balance, risk_tolerance, achievements, show_onboarding FROM users WHERE id = %s", (session['user_id'],))
            user = cursor.fetchone()
            if user:
                user['tether_balance'] = float(user.get('tether_balance', 0))
                show_onboarding = user.get('show_onboarding', False)
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
        except mysql.connector.Error as err:
            flash(f"Database error: {err}", "error")
        finally:
            if conn.is_connected():
                cursor.close()
                conn.close()
    
    return render_template('combined.html', 
                          section='dashboard', 
                          coins=coins, 
                          user=user, 
                          triggered_alerts=triggered_alerts,
                          top_gainers=top_gainers,
                          top_losers=top_losers,
                          trending_coins=trending_coins,
                          high_volume_coins=high_volume_coins,
                          show_onboarding=show_onboarding)

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
    page = int(request.args.get('page', 1))
    coins = []
    response = fetch_with_retry(f"{COINGECKO_API}/coins/markets?vs_currency=usd&order=market_cap_desc&per_page={COINS_PER_PAGE}&page={page}&sparkline=false")
    if response:
        coins = json.loads(response.text)
        # Enhance each coin with 24h high/low data
        for coin in coins:
            coin['high_24h'] = coin.get('high_24h', 'N/A')
            coin['low_24h'] = coin.get('low_24h', 'N/A')
            coin['total_volume'] = coin.get('total_volume', 'N/A')
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
                    'current_price': 'N/A',
                    'price_change_percentage_24h': 'N/A',
                    'market_cap': 'N/A'
                })
        else:
            flash("Failed to fetch watchlist data. Using cached data if available.", "warning")
            coins = [{'id': w['coin_id'], 'name': w['coin_id'].capitalize(), 'symbol': w['coin_id'][:3].upper(), 
                      'current_price': 'N/A', 'price_change_percentage_24h': 'N/A', 'market_cap': 'N/A'} 
                     for w in watchlist]
    else:
        flash("Your watchlist is empty. Add some coins to track!", "info")
    return render_template('combined.html', section='watchlist', coins=coins, available_coins=available_coins)

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
        if not all([coin_id, target_price, alert_type, order_type]):
            flash("All fields are required", "error")
            return redirect(url_for('alerts'))
        # Validate coin_id
        coin_exists = any(coin['id'] == coin_id for coin in available_coins)
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
                    (user_id, user_email, coin_id, target_price, alert_type, order_type, notified) 
                    VALUES (%s, %s, %s, %s, %s, %s, 0)
                """, (session['user_id'], user['email'], coin_id, target_price, alert_type, order_type))
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
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM price_alerts WHERE user_id = %s", (session['user_id'],))
            alerts = cursor.fetchall()
            for alert in alerts:
                alert['status'] = 'Triggered' if alert['notified'] else 'Pending'
        except mysql.connector.Error as err:
            flash(f"Database error: {err}", "error")
        finally:
            if conn.is_connected():
                cursor.close()
                conn.close()
    return render_template('combined.html', section='alerts', alerts=alerts, available_coins=available_coins)

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

@app.route('/correlation_matrix')
def correlation_matrix():
    conn = get_db_connection()
    coin_ids = []
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT DISTINCT coin_id FROM transactions WHERE user_id = %s", (session['user_id'],))
            coin_ids = [row['coin_id'] for row in cursor.fetchall()]
        except mysql.connector.Error as err:
            flash(f"Database error: {err}", "error")
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
    print("Backtester route accessed")
    try:
        if 'user_id' not in session or session.get('expires_at', 0) < datetime.now().timestamp():
            print("User not authenticated, redirecting to login")
            return redirect(url_for('login'))
        
        print("Fetching coins from CoinGecko API")
        api_url = f"{COINGECKO_API}/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=100&page=1&sparkline=false"
        print(f"API URL: {api_url}")
        
        response = fetch_with_retry(api_url)
        print(f"Response type: {type(response)}")
        
        if response and hasattr(response, 'json'):
            coins = response.json()
        else:
            print("API fetch failed, using empty list")
            coins = []
        
        print(f"Successfully retrieved {len(coins)} coins")
        return render_template('backtester.html', coins=coins, section='backtester')
        
    except Exception as e:
        error_msg = f"Error in backtester route: {str(e)}\n\n{traceback.format_exc()}"
        print(error_msg)
        return render_template('backtester.html', coins=[], section='backtester', error=str(e))

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
            cursor.execute("SELECT achievements FROM users WHERE id = %s", (session['user_id'],))
            user = cursor.fetchone()
            achievements_list = user['achievements'].split(',') if user and user['achievements'] else []
            return render_template('combined.html', section='achievements', achievements=achievements_list)
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

@app.route('/learning')
def learning():
    """Learning Hub - Interactive tutorials and educational content"""
    if 'user_id' not in session or session.get('expires_at', 0) < datetime.now().timestamp():
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    user_progress = {
        'tutorial_completed': False,
        'lessons_completed': [],
        'show_onboarding': True
    }
    
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT tutorial_completed, tutorial_skipped, lessons_completed, show_onboarding 
                FROM users WHERE id = %s
            """, (session['user_id'],))
            user = cursor.fetchone()
            if user:
                user_progress['tutorial_completed'] = user.get('tutorial_completed', False)
                user_progress['show_onboarding'] = user.get('show_onboarding', True)
                try:
                    import json
                    user_progress['lessons_completed'] = json.loads(user.get('lessons_completed', '[]'))
                except:
                    user_progress['lessons_completed'] = []
        except mysql.connector.Error as err:
            flash(f"Database error: {err}", "error")
        finally:
            if conn.is_connected():
                cursor.close()
                conn.close()
    
    return render_template('combined.html', section='learning', user_progress=user_progress)

@app.route('/complete_lesson', methods=['POST'])
def complete_lesson():
    """Mark a lesson as completed"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    lesson_id = request.json.get('lesson_id')
    if not lesson_id:
        return jsonify({'success': False, 'error': 'Lesson ID required'}), 400
    
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT lessons_completed FROM users WHERE id = %s", (session['user_id'],))
            user = cursor.fetchone()
            
            import json
            lessons = json.loads(user.get('lessons_completed', '[]')) if user else []
            
            if lesson_id not in lessons:
                lessons.append(lesson_id)
                cursor.execute("""
                    UPDATE users 
                    SET lessons_completed = %s, tutorial_completed = %s 
                    WHERE id = %s
                """, (json.dumps(lessons), len(lessons) >= 7, session['user_id']))
                conn.commit()
            
            cursor.close()
            conn.close()
            return jsonify({'success': True, 'completed_count': len(lessons)})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
    
    return jsonify({'success': False, 'error': 'Database connection failed'}), 500

@app.route('/skip_onboarding', methods=['POST'])
def skip_onboarding():
    """Skip the onboarding tutorial"""
    if 'user_id' not in session:
        return jsonify({'success': False}), 401
    
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE users 
                SET show_onboarding = FALSE, tutorial_skipped = TRUE 
                WHERE id = %s
            """, (session['user_id'],))
            conn.commit()
            cursor.close()
            conn.close()
            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
    
    return jsonify({'success': False}), 500

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

if __name__ == '__main__':
    try:
        app.run(debug=True)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()