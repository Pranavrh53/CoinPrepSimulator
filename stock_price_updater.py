# stock_price_updater.py
from app import db, Stock
import random
from datetime import datetime

def update_stock_prices():
    stocks = Stock.query.all()
    for stock in stocks:
        change_percent = random.uniform(-0.05, 0.05)  # ±5% fluctuation
        stock.current_price = stock.current_price * (1 + change_percent)
        stock.last_updated = datetime.utcnow()
    db.session.commit()

# Add to app.py to start the scheduler
def start_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(update_stock_prices, 'interval', minutes=10)  # Update every 10 minutes
    scheduler.start()