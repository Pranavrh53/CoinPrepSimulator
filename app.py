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

def get_db_connection():
    try:
        return mysql.connector.connect(**db_config)
    except mysql.connector.Error as err:
        print(f"Database connection failed: {err}")
        return None

def generate_verification_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

@app.route('/')
def index():
    if 'user_id' in session and session.get('expires_at', 0) > datetime.now().timestamp():
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db_connection()
        if conn is None:
            return render_template('login.html', error="Database connection failed")
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE username = %s AND verified = 1", (username,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if user and bcrypt.check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['expires_at'] = (datetime.now() + timedelta(minutes=30)).timestamp()
            return redirect(url_for('dashboard'))
        return render_template('login.html', error="Invalid credentials or unverified account")
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = bcrypt.generate_password_hash(request.form['password']).decode('utf-8')
        conn = get_db_connection()
        if conn is None:
            return render_template('register.html', error="Database connection failed")
        cursor = conn.cursor()
        try:
            verification_code = generate_verification_code()
            cursor.execute("INSERT INTO users (username, email, password, verification_code, verified) VALUES (%s, %s, %s, %s, 0)", 
                          (username, email, password, verification_code))
            cursor.execute("UPDATE users SET achievements = '' WHERE email = %s", (email,))  # Set empty achievements
            
            conn.commit()
            flash(f"Verification code sent to {email}. Please verify.", 'info')
            return redirect(url_for('verify', email=email))
        except mysql.connector.Error as err:
            return render_template('register.html', error=str(err))
        finally:
            cursor.close()
            conn.close()
    return render_template('register.html')

@app.route('/verify/<email>', methods=['GET', 'POST'])
def verify(email):
    if request.method == 'POST':
        code = request.form['code']
        conn = get_db_connection()
        if conn is None:
            return render_template('verify.html', error="Database connection failed")
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = %s AND verification_code = %s", (email, code))
        user = cursor.fetchone()
        if user:
            cursor.execute("UPDATE users SET verified = 1, verification_code = NULL WHERE email = %s", (email,))
            conn.commit()
            flash("Account verified! Please log in.", 'success')
            return redirect(url_for('login'))
        flash("Invalid verification code.", 'error')
        cursor.close()
        conn.close()
    return render_template('verify.html', email=email)

@app.route('/risk_quiz', methods=['GET', 'POST'])
def risk_quiz():
    if 'user_id' not in session or session.get('expires_at', 0) < datetime.now().timestamp():
        return redirect(url_for('login'))
    if request.method == 'POST':
        score = sum(int(request.form.get(f'q{i}', 0)) for i in range(1, 6))
        risk_level = 'Low' if score <= 10 else 'Medium' if score <= 20 else 'High'
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET risk_tolerance = %s WHERE id = %s", (risk_level, session['user_id']))
            conn.commit()
            cursor.close()
            conn.close()
        flash(f"Your risk tolerance is {risk_level}.", 'info')
        return redirect(url_for('dashboard'))
    return render_template('risk_quiz.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session or session.get('expires_at', 0) < datetime.now().timestamp():
        return redirect(url_for('login'))
    try:
        response = requests.get(f"{COINGECKO_API}/coins/markets?vs_currency=usd&ids=bitcoin,ethereum,binancecoin", timeout=10)
        response.raise_for_status()
        coins = json.loads(response.text)
    except requests.RequestException:
        coins = []
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT crypto_bucks, risk_tolerance, achievements FROM users WHERE id = %s", (session['user_id'],))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
    return render_template('dashboard.html', coins=coins, user=user)

@app.route('/portfolio', methods=['GET', 'POST'])
def portfolio():
    if 'user_id' not in session or session.get('expires_at', 0) < datetime.now().timestamp():
        return redirect(url_for('login'))
    if request.method == 'POST':
        coin_id = request.form['coin_id'].lower()
        amount = float(request.form['amount'])
        purchase_price = float(request.form['purchase_price'])
        wallet_id = request.form.get('wallet_id')
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            # Get or create a wallet for the user
            cursor.execute("SELECT id FROM wallets WHERE user_id = %s", (session['user_id'],))
            existing_wallets = cursor.fetchall()
            if not existing_wallets:
                cursor.execute("INSERT INTO wallets (user_id, name) VALUES (%s, %s)", 
                             (session['user_id'], 'Default Wallet'))
                conn.commit()
                cursor.execute("SELECT LAST_INSERT_ID()")
                wallet_id = cursor.fetchone()[0]
            elif wallet_id and not any(w[0] == int(wallet_id) for w in existing_wallets):
                wallet_id = existing_wallets[0][0]  # Default to first wallet if selected wallet_id is invalid
            else:
                wallet_id = int(wallet_id) if wallet_id else existing_wallets[0][0]  # Use first wallet if none selected
            
            cursor.execute("SELECT crypto_bucks FROM users WHERE id = %s", (session['user_id'],))
            crypto_bucks = cursor.fetchone()[0]
            total_cost = amount * purchase_price
            if total_cost <= crypto_bucks and amount > 0 and purchase_price > 0:
                cursor.execute("UPDATE users SET crypto_bucks = crypto_bucks - %s WHERE id = %s", (total_cost, session['user_id']))
                cursor.execute("INSERT INTO transactions (user_id, wallet_id, coin_id, amount, price, type) VALUES (%s, %s, %s, %s, %s, 'buy')",
                             (session['user_id'], wallet_id, coin_id, amount, purchase_price))
                conn.commit()
            cursor.close()
            conn.close()
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM transactions WHERE user_id = %s", (session['user_id'],))
        transactions = cursor.fetchall()
        cursor.close()
        conn.close()
    coin_ids = ','.join(set(t['coin_id'] for t in transactions)) or 'bnb'  # Default to bnb if empty
    current_prices = {}
    try:
        response = requests.get(f"{COINGECKO_API}/coins/markets?vs_currency=usd&ids={coin_ids}", timeout=10)
        response.raise_for_status()
        data = json.loads(response.text)
        print(f"API Response: {data}")  # Debug full response
        current_prices = {coin['id']: coin['current_price'] for coin in data if 'current_price' in coin}
        print(f"Current Prices: {current_prices}")  # Debug processed prices
    except requests.RequestException as e:
        print(f"API Error: {e}")
    except Exception as e:
        print(f"Data Processing Error: {e}")
    # Fetch user's wallets for the dropdown
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name FROM wallets WHERE user_id = %s", (session['user_id'],))
        user_wallets = cursor.fetchall()
        cursor.close()
        conn.close()
    return render_template('portfolio.html', transactions=transactions, current_prices=current_prices, wallets=user_wallets)    

@app.route('/watchlist', methods=['GET', 'POST'])
def watchlist():
    if 'user_id' not in session or session.get('expires_at', 0) < datetime.now().timestamp():
        return redirect(url_for('login'))
    if request.method == 'POST':
        coin_id = request.form['coin_id'].lower()
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO watchlist (user_id, coin_id) VALUES (%s, %s)", (session['user_id'], coin_id))
            conn.commit()
            cursor.close()
            conn.close()
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT coin_id FROM watchlist WHERE user_id = %s", (session['user_id'],))
        watchlist = cursor.fetchall()
        cursor.close()
        conn.close()
    coin_ids = ','.join([w['coin_id'] for w in watchlist])
    try:
        response = requests.get(f"{COINGECKO_API}/coins/markets?vs_currency=usd&ids={coin_ids}", timeout=10)
        response.raise_for_status()
        coins = json.loads(response.text)
    except requests.RequestException:
        coins = []
    return render_template('watchlist.html', coins=coins)

@app.route('/alerts', methods=['GET', 'POST'])
def alerts():
    if 'user_id' not in session or session.get('expires_at', 0) < datetime.now().timestamp():
        return redirect(url_for('login'))
    if request.method == 'POST':
        coin_id = request.form['coin_id'].lower()
        target_price = float(request.form['target_price'])
        alert_type = request.form['alert_type']
        order_type = request.form.get('order_type', 'limit')
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO price_alerts (user_id, coin_id, target_price, alert_type, order_type) VALUES (%s, %s, %s, %s, %s)",
                          (session['user_id'], coin_id, target_price, alert_type, order_type))
            conn.commit()
            cursor.close()
            conn.close()
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM price_alerts WHERE user_id = %s", (session['user_id'],))
        alerts = cursor.fetchall()
        cursor.close()
        conn.close()
    return render_template('alerts.html', alerts=alerts)

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('expires_at', None)
    return redirect(url_for('login'))

@app.route('/historical/<coin_id>')
def historical(coin_id):
    try:
        response = requests.get(f"{COINGECKO_API}/coins/{coin_id}/market_chart?vs_currency=usd&days=30", timeout=10)
        response.raise_for_status()
        data = json.loads(response.text)
        dates = [datetime.fromtimestamp(item[0]/1000).strftime('%Y-%m-%d') for item in data['prices']]
        prices = [item[1] for item in data['prices']]
        return jsonify({'dates': dates, 'prices': prices})
    except requests.RequestException:
        return jsonify({'error': 'Failed to fetch historical data'}), 500

@app.route('/achievements')
def achievements():
    if 'user_id' not in session or session.get('expires_at', 0) < datetime.now().timestamp():
        return redirect(url_for('login'))
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT achievements FROM users WHERE id = %s", (session['user_id'],))
        user = cursor.fetchone()
        achievements_list = user['achievements'].split(',') if user['achievements'] else []
        cursor.close()
        conn.close()
    return render_template('achievements.html', achievements=achievements_list)

@app.route('/update_achievements', methods=['POST'])
def update_achievements():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    achievement = request.form.get('achievement')
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        cursor.execute("SELECT achievements FROM users WHERE id = %s", (session['user_id'],))
        user = cursor.fetchone()
        current_achievements = user['achievements'].split(',') if user['achievements'] else []
        if achievement not in current_achievements:
            current_achievements.append(achievement)
            cursor.execute("UPDATE users SET achievements = %s WHERE id = %s", (','.join(current_achievements), session['user_id']))
            conn.commit()
        cursor.close()
        conn.close()
    return redirect(url_for('achievements'))