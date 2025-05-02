from flask import Flask, request, jsonify, render_template, session, redirect, url_for, flash
from flask_bcrypt import Bcrypt
import mysql.connector
import requests
import json
from datetime import datetime, timedelta
import os
import random
import string
import hashlib
import time

app = Flask(__name__)
app.secret_key = os.urandom(24)
bcrypt = Bcrypt(app)

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
CACHE_DURATION = 300  # Cache API responses for 5 minutes (increased from 60 seconds)
api_cache = {}  # In-memory cache: {url: (response_data, timestamp)}

def get_db_connection():
    try:
        return mysql.connector.connect(**db_config)
    except mysql.connector.Error as err:
        print(f"Database connection failed: {err}")
        return None

def generate_verification_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

def fetch_with_retry(url, retries=3, delay=5):
    # Check cache first
    if url in api_cache:
        cached_data, timestamp = api_cache[url]
        if time.time() - timestamp < CACHE_DURATION:
            print(f"Cache hit for {url}")
            return type('Response', (), {'text': json.dumps(cached_data), 'raise_for_status': lambda: None})()
        else:
            print(f"Cache expired for {url}")
    
    for attempt in range(retries):
        try:
            print(f"Making API request to {url} (attempt {attempt + 1})")
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            # Cache the response
            api_cache[url] = (response.json(), time.time())
            print(f"API request successful for {url}")
            return response
        except requests.RequestException as e:
            if attempt < retries - 1:
                time.sleep(delay)
                continue
            print(f"API request failed after {retries} attempts: {e}")
            # Fallback: Return the last cached response if available, even if expired
            if url in api_cache:
                cached_data, timestamp = api_cache[url]
                print(f"Returning expired cached response for {url}")
                return type('Response', (), {'text': json.dumps(cached_data), 'raise_for_status': lambda: None})()
            return None
    return None

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
    if request.method == 'POST':
        try:
            score = sum(int(request.form.get(f'q{i}', 0)) for i in range(1, 6))
            risk_level = 'Low' if score <= 10 else 'Medium' if score <= 20 else 'High'
            conn = get_db_connection()
            if conn:
                try:
                    cursor = conn.cursor()
                    cursor.execute("UPDATE users SET risk_tolerance = %s WHERE id = %s", (risk_level, session['user_id']))
                    conn.commit()
                    flash(f"Your risk tolerance is {risk_level}.", "info")
                except mysql.connector.Error as err:
                    flash(f"Database error: {err}", "error")
                finally:
                    if conn.is_connected():
                        cursor.close()
                        conn.close()
            return redirect(url_for('dashboard'))
        except ValueError:
            flash("Invalid input for quiz questions", "error")
        return render_template('combined.html', section='risk_quiz')
    return render_template('combined.html', section='risk_quiz')

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
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT crypto_bucks, risk_tolerance, achievements FROM users WHERE id = %s", (session['user_id'],))
            user = cursor.fetchone()
        except mysql.connector.Error as err:
            flash(f"Database error: {err}", "error")
        finally:
            if conn.is_connected():
                cursor.close()
                conn.close()
    return render_template('combined.html', section='dashboard', coins=coins, user=user)

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
    total_coins = 1000  # Approximate total coins for pagination
    total_pages = (total_coins + COINS_PER_PAGE - 1) // COINS_PER_PAGE
    conn = get_db_connection()
    user_wallets = []
    if conn:
        try:
            cursor = conn.cursor()
            # Check if the user has any wallets
            cursor.execute("SELECT id, name FROM wallets WHERE user_id = %s", (session['user_id'],))
            user_wallets = cursor.fetchall()
            # If no wallets exist, create a default one
            if not user_wallets:
                cursor.execute("INSERT INTO wallets (user_id, name) VALUES (%s, %s)", 
                              (session['user_id'], 'Default Wallet'))
                conn.commit()
                # Fetch the newly created wallet
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
    if not all([coin_id, amount, current_price, wallet_id, action]) or action not in ['buy', 'sell']:
        flash("All fields are required", "error")
        return redirect(url_for('live_market'))
    try:
        amount = float(amount)
        current_price = float(current_price)
        wallet_id = int(wallet_id)
    except ValueError:
        flash("Invalid amount, price, or wallet", "error")
        return redirect(url_for('live_market'))
    if amount <= 0 or current_price <= 0:
        flash("Amount and price must be positive", "error")
        return redirect(url_for('live_market'))
    conn = get_db_connection()
    if conn is None:
        flash("Database connection failed", "error")
        return redirect(url_for('live_market'))
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT crypto_bucks FROM users WHERE id = %s", (session['user_id'],))
        crypto_bucks = cursor.fetchone()[0]
        total_cost = amount * current_price
        if action == 'buy':
            if total_cost > crypto_bucks:
                flash("Insufficient CryptoBucks", "error")
                return redirect(url_for('live_market'))
            cursor.execute("UPDATE users SET crypto_bucks = crypto_bucks - %s WHERE id = %s", (total_cost, session['user_id']))
            cursor.execute("INSERT INTO transactions (user_id, wallet_id, coin_id, amount, price, type) VALUES (%s, %s, %s, %s, %s, %s)",
                          (session['user_id'], wallet_id, coin_id, amount, current_price, 'buy'))
        else:  # sell
            cursor.execute("SELECT SUM(amount) as total FROM transactions WHERE user_id = %s AND coin_id = %s AND type = 'buy'",
                          (session['user_id'], coin_id))
            total_bought = cursor.fetchone()[0] or 0
            cursor.execute("SELECT SUM(amount) as total FROM transactions WHERE user_id = %s AND coin_id = %s AND type = 'sell'",
                          (session['user_id'], coin_id))
            total_sold = cursor.fetchone()[0] or 0
            available = total_bought - total_sold
            if amount > available:
                flash("Insufficient coin amount to sell", "error")
                return redirect(url_for('live_market'))
            cursor.execute("UPDATE users SET crypto_bucks = crypto_bucks + %s WHERE id = %s", (total_cost, session['user_id']))
            cursor.execute("INSERT INTO transactions (user_id, wallet_id, coin_id, amount, price, type) VALUES (%s, %s, %s, %s, %s, %s)",
                          (session['user_id'], wallet_id, coin_id, amount, current_price, 'sell'))
        conn.commit()
        flash(f"Successfully {action} {amount} {coin_id}", "success")
    except mysql.connector.Error as err:
        flash(f"Database error: {err}", "error")
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()
    return redirect(url_for('live_market'))

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
        except ValueError:
            flash("Invalid amount or purchase price", "error")
            return redirect(url_for('portfolio'))
        conn = get_db_connection()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM wallets WHERE user_id = %s", (session['user_id'],))
                existing_wallets = cursor.fetchall()
                if not existing_wallets:
                    cursor.execute("INSERT INTO wallets (user_id, name) VALUES (%s, %s)", 
                                 (session['user_id'], 'Default Wallet'))
                    conn.commit()
                    cursor.execute("SELECT LAST_INSERT_ID()")
                    wallet_id = cursor.fetchone()[0]
                elif wallet_id and not any(w[0] == int(wallet_id) for w in existing_wallets):
                    wallet_id = existing_wallets[0][0]
                else:
                    wallet_id = int(wallet_id) if wallet_id else existing_wallets[0][0]
                
                cursor.execute("SELECT crypto_bucks FROM users WHERE id = %s", (session['user_id'],))
                crypto_bucks = cursor.fetchone()[0]
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
    transactions = []
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM transactions WHERE user_id = %s", (session['user_id'],))
            transactions = cursor.fetchall()
            # Convert Decimal fields to float to avoid type mismatch in template
            for transaction in transactions:
                if 'price' in transaction:
                    transaction['price'] = float(transaction['price'])
                if 'amount' in transaction:
                    transaction['amount'] = float(transaction['amount'])
        except mysql.connector.Error as err:
            flash(f"Database error: {err}", "error")
        finally:
            if conn.is_connected():
                cursor.close()
                conn.close()
    coin_ids = ','.join(set(t['coin_id'] for t in transactions)) or 'bitcoin'
    current_prices = {}
    response = fetch_with_retry(f"{COINGECKO_API}/coins/markets?vs_currency=usd&ids={coin_ids}")
    if response:
        data = json.loads(response.text)
        current_prices = {coin['id']: coin['current_price'] for coin in data if 'current_price' in coin}
    else:
        flash("Failed to fetch current prices. Using cached data if available.", "warning")
    conn = get_db_connection()
    user_wallets = []
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT id, name FROM wallets WHERE user_id = %s", (session['user_id'],))
            user_wallets = cursor.fetchall()
        except mysql.connector.Error as err:
            flash(f"Database error: {err}", "error")
        finally:
            if conn.is_connected():
                cursor.close()
                conn.close()
    return render_template('combined.html', section='portfolio', transactions=transactions, current_prices=current_prices, wallets=user_wallets)

@app.route('/watchlist', methods=['GET', 'POST'])
def watchlist():
    if 'user_id' not in session or session.get('expires_at', 0) < datetime.now().timestamp():
        return redirect(url_for('login'))
    if request.method == 'POST':
        coin_id = request.form.get('coin_id', '').lower()
        if not coin_id:
            flash("Coin ID is required", "error")
            return redirect(url_for('watchlist'))
        conn = get_db_connection()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO watchlist (user_id, coin_id) VALUES (%s, %s)", (session['user_id'], coin_id))
                conn.commit()
                flash("Coin added to watchlist", "success")
            except mysql.connector.Error as err:
                flash(f"Database error: {err}", "error")
            finally:
                if conn.is_connected():
                    cursor.close()
                    conn.close()
    conn = get_db_connection()
    watchlist = []
    if conn:
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
    coin_ids = ','.join([w['coin_id'] for w in watchlist]) or 'bitcoin'
    coins = []
    response = fetch_with_retry(f"{COINGECKO_API}/coins/markets?vs_currency=usd&ids={coin_ids}")
    if response:
        coins = json.loads(response.text)
    else:
        flash("Failed to fetch watchlist data. Using cached data if available.", "warning")
    return render_template('combined.html', section='watchlist', coins=coins)

@app.route('/alerts', methods=['GET', 'POST'])
def alerts():
    if 'user_id' not in session or session.get('expires_at', 0) < datetime.now().timestamp():
        return redirect(url_for('login'))
    if request.method == 'POST':
        coin_id = request.form.get('coin_id', '').lower()
        target_price = request.form.get('target_price')
        alert_type = request.form.get('alert_type')
        order_type = request.form.get('order_type', 'limit')
        if not all([coin_id, target_price, alert_type]):
            flash("All fields are required", "error")
            return redirect(url_for('alerts'))
        try:
            target_price = float(target_price)
        except ValueError:
            flash("Invalid target price", "error")
            return redirect(url_for('alerts'))
        conn = get_db_connection()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO price_alerts (user_id, coin_id, target_price, alert_type, order_type) VALUES (%s, %s, %s, %s, %s)",
                              (session['user_id'], coin_id, target_price, alert_type, order_type))
                conn.commit()
                flash("Alert set successfully", "success")
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
        except mysql.connector.Error as err:
            flash(f"Database error: {err}", "error")
        finally:
            if conn.is_connected():
                cursor.close()
                conn.close()
    return render_template('combined.html', section='alerts', alerts=alerts)

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
        return jsonify({'dates': dates, 'prices': prices})
    return jsonify({'error': 'Failed to fetch historical data'}), 500

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
            cursor = conn.cursor()
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

if __name__ == '__main__':
    app.run(debug=True)