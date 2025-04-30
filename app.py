from flask import Flask, session, jsonify, request, render_template, redirect, url_for, Blueprint
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
import random

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:Pranavrh123$@localhost/coinprep'  # Replace with your MySQL credentials
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'your_secret_key'  # Replace with a secure secret key

db = SQLAlchemy(app)


# Models
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    balance = db.Column(db.Float, default=10000.0)

class Stock(db.Model):
    __tablename__ = 'stocks'
    id = db.Column(db.Integer, primary_key=True)
    symbol = db.Column(db.String(10), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    current_price = db.Column(db.Float, nullable=False)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)

class Transaction(db.Model):
    __tablename__ = 'transactions'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    stock_id = db.Column(db.Integer, db.ForeignKey('stocks.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price_per_share = db.Column(db.Float, nullable=False)
    transaction_type = db.Column(db.String(10), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

# Blueprint for API routes
bp = Blueprint('api', __name__)

@bp.route('/api/stocks', methods=['GET'])
def get_stocks():
    stocks = Stock.query.all()
    return jsonify([{'id': s.id, 'symbol': s.symbol, 'name': s.name, 'current_price': s.current_price} for s in stocks])

@bp.route('/api/buy', methods=['POST'])
def buy_stock():
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    data = request.get_json()
    stock_id = data['stock_id']
    quantity = data['quantity']
    
    user = User.query.get(session['user_id'])
    stock = Stock.query.get(stock_id)
    
    if not stock or quantity <= 0:
        return jsonify({'error': 'Invalid stock or quantity'}), 400
    
    total_cost = stock.current_price * quantity
    if user.balance < total_cost:
        return jsonify({'error': 'Insufficient balance'}), 400
    
    user.balance -= total_cost
    transaction = Transaction(
        user_id=user.id,
        stock_id=stock.id,
        quantity=quantity,
        price_per_share=stock.current_price,
        transaction_type='buy'
    )
    db.session.add(transaction)
    db.session.commit()
    return jsonify({'message': 'Stock purchased successfully'})

@bp.route('/api/sell', methods=['POST'])
def sell_stock():
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    data = request.get_json()
    stock_id = data['stock_id']
    quantity = data['quantity']
    
    user = User.query.get(session['user_id'])
    stock = Stock.query.get(stock_id)
    
    if not stock or quantity <= 0:
        return jsonify({'error': 'Invalid stock or quantity'}), 400
    
    transactions = Transaction.query.filter_by(user_id=user.id, stock_id=stock.id).all()
    owned_quantity = sum(t.quantity if t.transaction_type == 'buy' else -t.quantity for t in transactions)
    if owned_quantity < quantity:
        return jsonify({'error': 'Not enough shares owned'}), 400
    
    total_earned = stock.current_price * quantity
    user.balance += total_earned
    transaction = Transaction(
        user_id=user.id,
        stock_id=stock.id,
        quantity=quantity,
        price_per_share=stock.current_price,
        transaction_type='sell'
    )
    db.session.add(transaction)
    db.session.commit()
    return jsonify({'message': 'Stock sold successfully'})

@bp.route('/api/portfolio', methods=['GET'])
def get_portfolio():
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    user = User.query.get(session['user_id'])
    transactions = Transaction.query.filter_by(user_id=user.id).all()
    
    portfolio = {}
    for t in transactions:
        stock = Stock.query.get(t.stock_id)
        if stock.symbol not in portfolio:
            portfolio[stock.symbol] = {'quantity': 0, 'value': 0.0}
        quantity_change = t.quantity if t.transaction_type == 'buy' else -t.quantity
        portfolio[stock.symbol]['quantity'] += quantity_change
        portfolio[stock.symbol]['value'] += quantity_change * stock.current_price
    
    return jsonify({
        'balance': user.balance,
        'portfolio': [
            {'symbol': symbol, 'quantity': data['quantity'], 'value': data['value']}
            for symbol, data in portfolio.items() if data['quantity'] > 0
        ]
    })

@bp.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    user = User.query.filter_by(username=data['username']).first()
    if user and user.password == data['password']:  # Use hashing in production
        session['user_id'] = user.id
        return jsonify({'message': 'Logged in'})
    return jsonify({'error': 'Invalid credentials'}), 401
@bp.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data['username']
    password = data['password']
    
    if User.query.filter_by(username=username).first():
        return jsonify({'error': 'Username already exists'}), 400
    
    new_user = User(username=username, password=password)  # Hash password in production
    db.session.add(new_user)
    db.session.commit()
    return jsonify({'message': 'Registration successful'})
# Register the blueprint
app.register_blueprint(bp, url_prefix='/api')

# Routes for rendering templates
@app.route('/')
def home():
    return redirect(url_for('login_page'))  # Redirect to login_page instead of api.login

@app.route('/login')
def login_page():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/register')
def register_page():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('register.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login_page'))
    return render_template('dashboard.html')

@app.route('/portfolio')
def portfolio():
    if 'user_id' not in session:
        return redirect(url_for('login_page'))
    return render_template('portfolio.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('login_page'))

# Stock price update function
def update_stock_prices():
    stocks = Stock.query.all()
    for stock in stocks:
        change_percent = random.uniform(-0.05, 0.05)  # ±5% fluctuation
        stock.current_price = stock.current_price * (1 + change_percent)
        stock.last_updated = datetime.utcnow()
    db.session.commit()

# Start the scheduler
def start_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(update_stock_prices, 'interval', minutes=10)  # Update every 10 minutes
    scheduler.start()

if __name__ == '__main__':
    try:
        with app.app_context():
            db.create_all()  # Ensure tables are created (skip if already done via database.sql)
    except Exception as e:
        print(f"Database connection failed: {e}")
        raise e
    start_scheduler()
    app.run(debug=True)