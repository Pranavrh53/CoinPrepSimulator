# 🚀 CoinPrep Simulator

### *Your AI-Powered Crypto Trading Simulator & Learning Platform*

**CoinPrep Simulator** is a cryptocurrency trading simulator with AI-powered learning. It combines real-time market data, professional trading features with multiple order types, personalized risk assessment, and an AI tutor to help users learn crypto trading safely.

---

## ✨ Features

### 📊 Portfolio Management
- Real-time tracking of crypto holdings
- Live price updates via CoinGecko API
- Portfolio value visualization
- Buy/Sell transaction history
- Unrealized P/L tracking
- 0.1% trading fees per transaction

### 💱 Trading System
- **Market Orders** - Instant execution at current price
- **Limit Orders** - Execute when price reaches target
- **Stop Loss** - Auto-sell to prevent losses
- **Take Profit** - Auto-sell to lock in gains
- Trading pairs (USDT/CryptoBucks, Crypto/USDT)
- Order management and tracking
- Background order execution
- 10 default trading pairs (BTC, ETH, BNB, XRP, ADA, SOL, DOT, DOGE, AVAX, USDT)

### 🎯 Price Alerts
- Custom price alerts (above/below)
- Email notifications
- Alert history tracking
- Multi-coin support

### 🧠 Risk Assessment
- 4-part risk assessment quiz
  - Financial Capacity
  - Investment Knowledge
  - Psychological Tolerance
  - Goals & Timeline
- Personalized risk profile
- Diversification recommendations
- Volatility metrics

### 📚 AI Learning Hub
- AI-powered tutor (Google Gemini)
- RAG-based knowledge base with ChromaDB
- Educational materials:
  - Crypto basics introduction
  - Stop loss strategies
  - FOMO and trading psychology
  - Position sizing guide
  - Real case studies (2021 leverage trap)
- Personalized learning paths
- Learning progress tracking

### 📈 Backtesting Engine
- Historical strategy testing
- Performance metrics

### 🔐 Security
- Email verification system
- Bcrypt password encryption
- Session management

---

## ⚡ Quick Start

### Prerequisites
- Python 3.13+
- MySQL 8.0+
- Google Gemini API key (free at https://makersuite.google.com/app/apikey)

### Installation

**1️⃣ Install Dependencies**
```bash
cd e:\crypto_tracker
pip install -r requirements.txt
```

**2️⃣ Database Setup**
```bash
mysql -u root -pPranavrh123$ -e "CREATE DATABASE IF NOT EXISTS crypto_tracker;"
```

**3️⃣ Apply Schemas**
```powershell
cd e:\crypto_tracker
Get-Content database.sql | mysql -u root -pPranavrh123$ crypto_tracker
Get-Content trading_schema.sql | mysql -u root -pPranavrh123$ crypto_tracker
Get-Content risk_assessment_schema.sql | mysql -u root -pPranavrh123$ crypto_tracker
Get-Content learning_system_schema.sql | mysql -u root -pPranavrh123$ crypto_tracker
Get-Content init_trading.sql | mysql -u root -pPranavrh123$ crypto_tracker
```

**4️⃣ Set Gemini API Key and Run**
```powershell
$env:GEMINI_API_KEY="AIza-your-key-here"
python app.py
```

**5️⃣ Open in Browser**
Navigate to: http://localhost:5000

---

## 🛠️ Tech Stack

| Component | Technology |
|-----------|------------|
| **Backend** | Flask 2.3+ |
| **Database** | MySQL 8.0+ |
| **Frontend** | HTML5, CSS3, JavaScript |
| **AI** | Google Gemini, ChromaDB, Sentence Transformers |
| **Market Data** | CoinGecko API |
| **Authentication** | Flask-Bcrypt |
| **Scheduling** | APScheduler |
| **Data Analysis** | NumPy, Pandas |

---

## 📁 Project Structure

```
crypto_tracker/
├── app.py                          # Flask main application
├── ai_assistant.py                 # AI learning system with RAG
├── user_profiler.py                # User skill profiling
├── learning_routes.py              # Learning system routes
├── risk_assessment_data.py          # Risk quiz data
├── risk_assessment_routes.py        # Risk assessment endpoints
│
├── templates/
│   ├── ai_tutor.html              # AI learning interface
│   ├── backtester.html            # Backtesting engine
│   ├── learning_hub.html          # Learning content hub
│   └── combined.html              # Combined dashboard
│
├── static/
│   ├── css/style.css              # Main stylesheet
│   └── js/
│       ├── charts.js              # Chart rendering
│       └── script.js              # Frontend logic
│
├── knowledge/                      # Educational content
│   ├── lessons/                   # Crypto education lessons
│   ├── strategies/                # Trading strategies
│   ├── psychology/                # Trading psychology
│   └── case_studies/              # Real trading case studies
│
├── vector_db/                      # ChromaDB storage for RAG
│
├── database.sql                    # User & portfolio schema
├── trading_schema.sql              # Trading system schema
├── risk_assessment_schema.sql      # Risk profile schema
├── learning_system_schema.sql      # Learning system schema
├── init_trading.sql                # Sample trading pairs
│
├── requirements.txt                # Python dependencies
├── README.md                       # This file
├── QUICK_START.md                 # Quick setup guide
├── GEMINI_SETUP.md                # Gemini API setup
├── TRADING_FEATURES.md            # Trading system details
└── IMPLEMENTATION_COMPLETE.md     # Implementation notes
```

---

## 🎮 Usage

### Create Account & Get Started
1. Go to http://localhost:5000
2. Click "Register"
3. Enter email and password
4. Verify email
5. Take risk assessment quiz
6. Start with 10,000 CryptoBucks

### Start Trading
1. Go to Live Market
2. Select a cryptocurrency
3. Click Trade → Buy
4. Choose order type (Market/Limit/Stop Loss/Take Profit)
5. Enter amount and submit

### Monitor Portfolio
1. Click Portfolio to see holdings
2. View unrealized/realized P/L
3. Check trading history

### Use AI Tutor
1. Go to Learning Hub
2. Ask questions about crypto
3. AI tutor provides educated answers with source materials

---

## 📊 Key Functionality

### Trading System
- Users start with **10,000 CryptoBucks** (virtual currency)
- Convert to **USDT** to trade cryptocurrencies
- **All trades incur 0.1% fee**
- Real-time price updates from CoinGecko
- Automatic order execution for pending orders (every 5 minutes)

### Portfolio Tracking
- Real-time P/L calculations
- Average buy price per coin
- Transaction history with fees
- Holdings summary by cryptocurrency

### Price Alerts
- Set custom price levels for notifications
- Automatic email alerts when price targets are hit
- Persistent alert history

### AI Learning
- RAG-powered Q&A system
- Context-aware responses from knowledge base
- Real crypto education content
- Trade mistake analysis
- Personalized learning recommendations

---

## 📝 Database Schema

The application uses 5 main database files:

1. **database.sql** - Users, wallets, transactions
2. **trading_schema.sql** - Orders, trading pairs, order fills
3. **risk_assessment_schema.sql** - Risk profiles and assessments
4. **learning_system_schema.sql** - Learning profiles, conversations, progress
5. **init_trading.sql** - Default trading pairs (10 cryptocurrencies)

---

## 🚀 First Steps

1. **Setup**: Follow the Quick Start section above
2. **Register**: Create a new account
3. **Verify**: Check email for verification code
4. **Risk Quiz**: Complete the 4-part risk assessment
5. **Start Trading**: Begin with live market data
6. **Learn**: Use the AI tutor to improve your trading knowledge

---

## 📞 Configuration

### Email Notifications
Edit `app.py` to configure email:
```python
EMAIL_CONFIG = {
    'MAIL_SERVER': 'smtp.gmail.com',
    'MAIL_PORT': 587,
    'MAIL_USE_TLS': True,
    'MAIL_USERNAME': 'your-email@gmail.com',
    'MAIL_PASSWORD': 'your-app-password',
    'MAIL_DEFAULT_SENDER': 'your-email@gmail.com'
}
```

### Database Credentials
Update in `app.py`:
```python
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': 'Pranavrh123$',
    'database': 'crypto_tracker'
}
```

### Gemini API Key
Set environment variable before running:
```powershell
$env:GEMINI_API_KEY="AIza-your-key-here"
```

---

## 📄 License

MIT License
