"""
Test Script for Price Alerts
=============================
This script helps you test the price alert system by manually triggering the check_price_alerts function.

Usage:
1. Make sure your app is running (python app.py)
2. Set a price alert in the web interface
3. Run this script: python test_alert.py
4. It will check your alerts and trigger them if conditions are met
"""

import mysql.connector
import requests
import json
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Database configuration (should match your app.py)
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': 'Pranavrh123$',
    'database': 'crypto_tracker'
}

COINGECKO_API = "https://api.coingecko.com/api/v3"

# Email configuration (should match your app.py)
EMAIL_CONFIG = {
    'smtp_server': 'smtp.gmail.com',
    'smtp_port': 587,
    'sender_email': 'pranavrh53@gmail.com',  # Your Gmail
    'sender_password': 'sjxw nnlz dfdu nxav'  # Your app password
}


def get_db_connection():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        return conn
    except mysql.connector.Error as err:
        print(f"Database connection error: {err}")
        return None


def send_email_notification(recipient, subject, body):
    """Send email notification"""
    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_CONFIG['sender_email']
        msg['To'] = recipient
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        
        server = smtplib.SMTP(EMAIL_CONFIG['smtp_server'], EMAIL_CONFIG['smtp_port'])
        server.starttls()
        server.login(EMAIL_CONFIG['sender_email'], EMAIL_CONFIG['sender_password'])
        server.send_message(msg)
        server.quit()
        print(f"✅ Email sent to {recipient}")
        return True
    except Exception as e:
        print(f"❌ Failed to send email: {e}")
        return False


def check_price_alerts():
    """Check and trigger price alerts - Same logic as app.py"""
    print("\n" + "="*60)
    print("🔍 Checking price alerts...")
    print("="*60)
    
    conn = get_db_connection()
    if not conn:
        print("❌ Database connection failed")
        return
    
    try:
        cursor = conn.cursor(dictionary=True)
        
        # Get all pending alerts
        cursor.execute("""
            SELECT pa.*, u.email as user_email, u.username 
            FROM price_alerts pa 
            JOIN users u ON pa.user_id = u.id 
            WHERE pa.notified = 0
        """)
        alerts = cursor.fetchall()
        
        if not alerts:
            print("\n📭 No pending alerts found")
            return
        
        print(f"\n📋 Found {len(alerts)} pending alert(s):")
        for i, alert in enumerate(alerts, 1):
            print(f"   {i}. User: {alert['username']} | Coin: {alert['coin_id']} | "
                  f"Target: ${alert['target_price']:.2f} ({alert['alert_type']})")
        
        # Get unique coin IDs
        coin_ids = list(set(alert['coin_id'] for alert in alerts))
        coin_ids_str = ','.join(coin_ids)
        
        # Fetch current prices from CoinGecko
        print(f"\n🌐 Fetching current prices for: {', '.join(coin_ids)}")
        response = requests.get(
            f"{COINGECKO_API}/coins/markets?vs_currency=usd&ids={coin_ids_str}",
            timeout=10
        )
        
        if response.status_code != 200:
            print(f"❌ Failed to fetch prices: {response.status_code}")
            return
        
        prices = {
            coin['id']: float(coin['current_price']) 
            for coin in response.json() 
            if 'current_price' in coin
        }
        
        print("\n💰 Current Prices:")
        for coin_id, price in prices.items():
            print(f"   {coin_id}: ${price:.2f}")
        
        # Check each alert
        print("\n🔔 Checking alerts...")
        triggered_count = 0
        
        for alert in alerts:
            coin_id = alert['coin_id']
            current_price = prices.get(coin_id)
            
            if current_price is None:
                print(f"   ⚠️  No price data for {coin_id}")
                continue
            
            target_price = float(alert['target_price'])
            alert_type = alert['alert_type']
            
            # Check if alert should trigger
            triggered = (
                (alert_type == 'above' and current_price >= target_price) or
                (alert_type == 'below' and current_price <= target_price)
            )
            
            status_icon = "✅" if triggered else "⏳"
            print(f"   {status_icon} {coin_id}: Current=${current_price:.2f} | "
                  f"Target={alert_type} ${target_price:.2f} | "
                  f"{'TRIGGERED!' if triggered else 'Waiting...'}")
            
            if triggered:
                triggered_count += 1
                message = (
                    f"Alert: {coin_id.capitalize()} has reached {alert_type} "
                    f"${target_price:.2f}. Current price: ${current_price:.2f}."
                )
                
                # Insert notification
                cursor.execute(
                    "INSERT INTO notifications (user_id, coin_id, message) VALUES (%s, %s, %s)",
                    (alert['user_id'], coin_id, message)
                )
                
                # Mark alert as notified
                cursor.execute(
                    "UPDATE price_alerts SET notified = 1 WHERE id = %s",
                    (alert['id'],)
                )
                
                conn.commit()
                
                print(f"\n      📧 Sending email to {alert['user_email']}...")
                
                # Send email
                email_sent = send_email_notification(
                    recipient=alert['user_email'],
                    subject=f"🚨 Crypto Price Alert: {coin_id.upper()} {alert_type} ${target_price:.2f}",
                    body=f"""
Hi {alert['username']},

Your price alert has been triggered! 🎯

{message}

Alert Details:
- Cryptocurrency: {coin_id.upper()}
- Target Price: ${target_price:.2f}
- Alert Type: {alert_type.upper()}
- Current Price: ${current_price:.2f}
- Order Type: {alert['order_type'].upper()}

You can view your portfolio and set up new alerts by logging in to your account.

Best regards,
Crypto Tracker Team (Pranav RH)
                    """
                )
        
        print("\n" + "="*60)
        print(f"✅ Check complete! {triggered_count} alert(s) triggered")
        print("="*60)
        
    except mysql.connector.Error as err:
        print(f"❌ Database error: {err}")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


if __name__ == "__main__":
    print("\n" + "="*60)
    print("🧪 Price Alert Testing Script")
    print("="*60)
    print(f"⏰ Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    check_price_alerts()
    
    print("\n💡 Tips for testing:")
    print("   1. Set an alert with a target price near current price")
    print("   2. For 'above' alerts: Set target slightly below current price")
    print("   3. For 'below' alerts: Set target slightly above current price")
    print("   4. Run this script to trigger the check immediately")
    print("   5. Check your email for notifications\n")
