from flask import Flask, request, jsonify, render_template, session, redirect, url_for, flash
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
            return type('Response', (), {'text': json.dumps(cached_data), 'raise_for_status': lambda: None})()
        else:
            print(f"Cache expired for {url}")

    throttle_request()
    for attempt in range(retries):
        try:
            print(f"Making API request to {url} (attempt {attempt + 1})")
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            api_cache[url] = (response.json(), time.time())
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
                print(f"Returning expired cached response for {url}")
                return type('Response', (), {'text': json.dumps(cached_data), 'raise_for_status': lambda: None})()
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

# Start background scheduler
scheduler = BackgroundScheduler()
scheduler.add_job(check_price_alerts, 'interval', seconds=CHECK_INTERVAL)
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
            'options': [
                {'value': 1, 'text': 'Sell all investments immediately'},
                {'value': 2, 'text': 'Sell some to reduce risk'},
                {'value': 3, 'text': 'Hold and wait for recovery'},
                {'value': 4, 'text': 'Buy more to lower cost'},
                {'value': 5, 'text': 'Significantly increase position'}
            ]
        },
        {
            'id': 'q2',
            'text': 'What is your investment time horizon?',
            'options': [
                {'value': 1, 'text': 'Less than 1 year'},
                {'value': 3, 'text': '1-3 years'},
                {'value': 5, 'text': '3-5 years'},
                {'value': 8, 'text': '5-10 years'},
                {'value': 10, 'text': '10+ years'}
            ]
        },
        {
            'id': 'q3',
            'text': 'What percentage of your income do you invest?',
            'options': [
                {'value': 1, 'text': 'Less than 5%'},
                {'value': 3, 'text': '5-10%'},
                {'value': 5, 'text': '10-20%'},
                {'value': 7, 'text': '20-30%'},
                {'value': 10, 'text': 'More than 30%'}
            ]
        },
        {
            'id': 'q4',
            'text': 'Your investment knowledge level?',
            'options': [
                {'value': 1, 'text': 'Beginner'},
                {'value': 3, 'text': 'Some knowledge'},
                {'value': 5, 'text': 'Experienced'},
                {'value': 7, 'text': 'Advanced'},
                {'value': 10, 'text': 'Expert'}
            ]
        },
        {
            'id': 'q5',
            'text': 'Your main investment goal?',
            'options': [
                {'value': 1, 'text': 'Preserve capital'},
                {'value': 3, 'text': 'Generate income'},
                {'value': 5, 'text': 'Balanced growth'},
                {'value': 8, 'text': 'Long-term growth'},
                {'value': 10, 'text': 'Maximum returns'}
            ]
        }
    ]
    
    if request.method == 'POST':
        try:
            # Calculate total score (max 45 points)
            score = sum(int(request.form.get(question['id'], 0)) for question in questions)
            
            # Determine risk level
            if score <= 10:
                risk_level = 'Conservative (1/5)'
                risk_percent = 20
            elif score <= 20:
                risk_level = 'Moderate (2/5)'
                risk_percent = 40
            elif score <= 30:
                risk_level = 'Balanced (3/5)'
                risk_percent = 60
            elif score <= 38:
                risk_level = 'Growth (4/5)'
                risk_percent = 80
            else:
                risk_level = 'Aggressive (5/5)'
                risk_percent = 100
            
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
    return render_template('combined.html', 
                         section='risk_quiz', 
                         questions=questions)

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session or session.get('expires_at', 0) < datetime.now().timestamp():
        return redirect(url_for('login'))
    coins = []
    response = fetch_with_retry(f"{COINGECKO_API}/coins/markets?vs_currency=usd&ids=bitcoin,ethereum,binancecoin")
    if response:
        coins = json.loads(response.text)
    else:
        flash("Failed to fetch market data. Please try again later.", "error")
    conn = get_db_connection()
    user = None
    triggered_alerts = []
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT crypto_bucks, risk_tolerance, achievements FROM users WHERE id = %s", (session['user_id'],))
            user = cursor.fetchone()
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
    return render_template('combined.html', section='dashboard', coins=coins, user=user, triggered_alerts=triggered_alerts)

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
    else:
        flash("Failed to fetch live market data. Using cached data if available.", "warning")
    total_coins = 1000
    total_pages = (total_coins + COINS_PER_PAGE - 1) // COINS_PER_PAGE
    conn = get_db_connection()
    user_wallets = []
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
        except mysql.connector.Error as err:
            flash(f"Database error: {err}", "error")
        finally:
            if conn.is_connected():
                cursor.close()
                conn.close()
    return render_template('combined.html', section='live_market', coins=coins, wallets=user_wallets, page=page, total_pages=total_pages)

@app.route('/trade', methods=['POST'])
def trade():
    if 'user_id' not in session or session.get('expires_at', 0) < datetime.now().timestamp():
        return redirect(url_for('login'))
    coin_id = request.form.get('coin_id', '').lower()
    amount = request.form.get('amount')
    current_price = request.form.get('current_price')
    wallet_id = request.form.get('wallet_id')
    action = request.form.get('action')
    source = request.form.get('source', 'live_market')
    if not all([coin_id, amount, current_price, wallet_id, action]) or action not in ['buy', 'sell']:
        flash("All fields are required", "error")
        return redirect(url_for(source))
    try:
        amount = float(amount)
        current_price = float(current_price)
        wallet_id = int(wallet_id)
    except ValueError:
        flash("Invalid amount, price, or wallet", "error")
        return redirect(url_for(source))
    if amount <= 0 or current_price <= 0:
        flash("Amount and price must be positive", "error")
        return redirect(url_for(source))
    conn = get_db_connection()
    if conn is None:
        flash("Database connection failed", "error")
        return redirect(url_for(source))
    try:
        cursor = conn.cursor(dictionary=True)
        if action == 'buy':
            cursor.execute("SELECT crypto_bucks FROM users WHERE id = %s", (session['user_id'],))
            crypto_bucks = float(cursor.fetchone()['crypto_bucks'])
            total_cost = amount * current_price
            if total_cost > crypto_bucks:
                flash("Insufficient CryptoBucks", "error")
                return redirect(url_for(source))
            cursor.execute("UPDATE users SET crypto_bucks = crypto_bucks - %s WHERE id = %s", (total_cost, session['user_id']))
            cursor.execute("INSERT INTO transactions (user_id, wallet_id, coin_id, amount, price, type) VALUES (%s, %s, %s, %s, %s, %s)",
                          (session['user_id'], wallet_id, coin_id, amount, current_price, 'buy'))
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
            cursor.execute("UPDATE users SET crypto_bucks = crypto_bucks + %s WHERE id = %s", (revenue, session['user_id']))
            cursor.execute(
                "INSERT INTO transactions (user_id, wallet_id, coin_id, amount, price, type, sold_price, buy_transaction_id) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                (session['user_id'], wallet_id, coin_id, amount, purchase_price, 'sell', current_price, buy_transaction_id)
            )
        conn.commit()
        flash(f"Successfully {action}ed {amount} {coin_id}", "success")
    except mysql.connector.Error as err:
        flash(f"Database error: {err}", "error")
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
    total_profit = 0.0
    current_prices = {}
    risk_metrics = {}
    transactions = []
    user_wallets = []
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT id, name FROM wallets WHERE user_id = %s", (session['user_id'],))
            user_wallets = cursor.fetchall()
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
            for buy in buy_transactions:
                buy_id = buy['id']
                total_bought = float(buy['amount'] or 0)
                total_sold = sold_amounts.get(buy_id, 0.0)
                remaining_amount = total_bought - total_sold
                if remaining_amount > 0:
                    transactions.append({
                        'wallet_id': buy['wallet_id'],
                        'coin_id': buy['coin_id'],
                        'amount': remaining_amount,
                        'price': float(buy['price'] or 0),
                        'buy_transaction_id': buy_id
                    })
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
    return render_template('combined.html', section='portfolio', transactions=transactions, sold_transactions=sold_transactions, total_profit=round(total_profit, 2), current_prices=current_prices, wallets=user_wallets, risk_metrics=risk_metrics, correlation_data=correlation_data)

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

@app.route('/achievements')
def achievements():
    if 'user_id' not in session or session.get('expires_at', 0) < datetime.now().timestamp():
        return redirect(url_for('login'))
    conn = get_db_connection()
    achievements_list = []
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT achievements FROM users WHERE id = %s", (session['user_id'],))
            user = cursor.fetchone()
            achievements_list = user['achievements'].split(',') if user['achievements'] else []
        except mysql.connector.Error as err:
            flash(f"Database error: {err}", "error")
        finally:
            if conn.is_connected():
                cursor.close()
                conn.close()
    return render_template('combined.html', section='achievements', achievements=achievements_list)

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

if __name__ == '__main__':
    try:
        app.run(debug=True)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()