<div align="center">

<h1>🚀 CoinPrep Simulator</h1>

<p><strong>Your AI-Powered Crypto Trading Simulator & Learning Platform</strong></p>

<p>
  <img src="https://img.shields.io/badge/Python-3.13+-3776AB?style=for-the-badge&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/Flask-2.3+-000000?style=for-the-badge&logo=flask&logoColor=white" />
  <img src="https://img.shields.io/badge/MySQL-8.0+-4479A1?style=for-the-badge&logo=mysql&logoColor=white" />
  <img src="https://img.shields.io/badge/Google_Gemini-AI-8E75B2?style=for-the-badge&logo=google&logoColor=white" />
  <img src="https://img.shields.io/badge/ChromaDB-RAG-orange?style=for-the-badge" />
  <img src="https://img.shields.io/badge/React-Lovable_UI-61DAFB?style=for-the-badge&logo=react&logoColor=black" />
</p>

<p><em>Trade smarter. Learn faster. Risk nothing.</em></p>

</div>

---

## 📖 Table of Contents

| Section | Description |
|---------|-------------|
| [🎯 Feature Overview](#-feature-overview) | Full feature breakdown |
| [🤖 AI Intelligence System](#-ai-intelligence-system) | RAG + LLM capabilities |
| [📊 Trading Engine](#-trading-engine) | Orders, portfolio, alerts |
| [🧠 Risk Assessment](#-risk-assessment) | 4-part quiz & profiling |
| [🎨 UI Frontends](#-ui-frontends) | Flask + React Lovable UI |
| [⚡ Quick Start](#-quick-start) | Get running in minutes |
| [🛠️ Tech Stack](#️-tech-stack) | Full technology breakdown |
| [📁 Project Structure](#-project-structure) | File & folder layout |
| [🔧 Configuration](#-configuration) | Environment & API setup |
| [📝 Database Schema](#-database-schema) | DB tables explained |


## 🎯 Feature Overview

<details>
<summary><strong>📊 Portfolio Management</strong></summary>

- Real-time tracking of all crypto holdings
- Live price feeds via **CoinGecko API** (with 10-min cache + retry logic)
- Unrealized & Realized P&L calculations
- Average buy price per coin
- Holdings summary by cryptocurrency
- Transaction history with 0.1% fee tracking
- Correlation matrix across holdings (30-day)
- Sharpe Ratio, Volatility, Max Drawdown per coin

</details>

<details>
<summary><strong>💱 Trading System</strong></summary>

| Order Type | Trigger |
|---|---|
| **Market Order** | Instant execution at live price |
| **Limit Buy** | Executes when price ≤ your target |
| **Limit Sell** | Executes when price ≥ your target |
| **Stop Loss** | Auto-sells when price drops below threshold |
| **Take Profit** | Auto-sells when price rises above threshold |

- Supported pairs: `Crypto/USDT` and `CryptoBucks/Crypto`
- 10 default coins: BTC, ETH, BNB, XRP, ADA, SOL, DOT, DOGE, AVAX, USDT
- Background order executor (APScheduler, every 5 minutes)
- Order fills tracked in `order_fills` table
- Insufficient balance → auto-cancel with reason logged

</details>

<details>
<summary><strong>🎯 Price Alerts</strong></summary>

- Set alerts for price **above** or **below** any threshold
- **Snooze** alerts temporarily (`snoozed_until` field)
- Email sent via Gmail SMTP when triggered
- Full trigger history in `price_alert_history`
- Alert notes for context
- Background alert checker runs every 5 minutes

</details>

<details>
<summary><strong>📈 Backtesting Engine</strong></summary>

- Test historical strategies against past price data
- Performance metrics: returns, drawdown, win rate
- Available via `backtester.html` template

</details>

---

## 🤖 AI Intelligence System

### Architecture Overview

```
User Question
      │
      ▼
Is it a portfolio query?
  ├─ YES → Fetch live MySQL data (holdings, orders, balances)
  └─ NO  → Skip portfolio grounding
      │
      ▼
ChromaDB Vector Search (all-MiniLM-L6-v2)
      │
Retrieve top-3 relevant knowledge chunks
      │
      ▼
Build Personalized Prompt
  ├─ User skill level (beginner / intermediate / advanced)
  ├─ Risk tolerance (from DB)
  ├─ Portfolio context (live data if applicable)
  └─ Relevant RAG documents
      │
      ▼
AI Generation (Claude 3.5 Sonnet OR Gemini)
      │
      ▼
Safety Disclaimer appended
      │
      ▼
Response + Sources + Response Time returned
```

### Knowledge Base (RAG Content)

Stored in `./knowledge/` and indexed into ChromaDB:

| Category | Topics Covered |
|---|---|
| `crypto_basics` | Blockchain, wallets, how crypto works |
| `trading_strategies` | Stop loss, position sizing, entry/exit |
| `psychology` | FOMO, emotional trading, discipline |
| `case_studies` | 2021 Leverage Trap, real loss scenarios |
| `risk_management` | Portfolio diversification, drawdown limits |

### AI Provider Support

```
provider = "auto"
├─ API key starts with "sk-ant-" → Claude 3.5 Sonnet
└─ Otherwise → Google Gemini (via google-genai SDK)
```

Both fall back to a **rule-based advisor** if the AI call fails, ensuring the app never breaks.

### Trade Advisor Technical Indicators

Computed from 60 days of CoinGecko OHLC data:

| Indicator | Period | Purpose |
|---|---|---|
| **RSI** | 14-period | Overbought/Oversold signal |
| **MA10** | 10-period | Short-term trend |
| **MA50** | 50-period | Long-term trend |
| **Momentum** | Last 5 prices | Prediction score 10–90% |
| **Volatility** | 60-day range | Risk level (Low/Medium/High) |

### Portfolio Query Detection

The AI recognizes 30+ portfolio-related terms:

```
portfolio • holding • open trade • position • balance • p/l • profit • loss
performance • exposure • allocation • tether • usdt • cryptobucks • my trade
limit order • stop order • take profit • what do I hold • how much • how many
```

---

## 📊 Trading Engine

### Starting Capital

| Balance Type | Initial Amount |
|---|---|
| CryptoBucks (CB$) | 10,000 |
| USDT | 0 (convert from CB$) |
| Crypto | 0 (buy with USDT) |

### Fee Structure
- All trades: **0.1% fee** applied to both buy and sell
- Fee deducted at execution time

### Order Execution Flow

```
Place Order
    │
    ├─ Market → Execute immediately at live price
    │
    └─ Limit / Stop Loss / Take Profit
           │
           └─ APScheduler checks every 5 minutes
                  │
                  ├─ Condition met → Execute + log fill
                  └─ Insufficient balance → Cancel order
```

---

## 🧠 Risk Assessment

A **4-part scientific quiz** that builds your personalized risk profile:

| Section | What It Measures |
|---|---|
| 🏦 Financial Capacity | Income, savings, emergency fund |
| 📚 Investment Knowledge | Market understanding, crypto experience |
| 🧘 Psychological Tolerance | Reaction to losses, emotional resilience |
| 🎯 Goals & Timeline | Investment horizon, targets |

### Risk Profile Output

- **Overall risk score** (0–100%)
- **Risk category**: Conservative → Moderate → Balanced → Growth → Aggressive
- **Asset allocation recommendation** (bonds/equity/crypto split)
- **Strength & concern analysis** with mismatch detection
- **Crypto-specific allocation advice** by profile
- **Action steps** & risk management rules

### Mismatch Detection

```
If |financial_score - psychological_score| > 30:
  → Flag: "High capacity but low tolerance — start conservatively"
If knowledge_score < psychological_score by 30+:
  → Flag: "Risk appetite exceeds knowledge — educate first"
```

---

## 🎨 UI Frontends

### 1. Flask / Jinja2 Frontend (Primary)

**`templates/combined.html`** — monolithic SPA-style dashboard:
- Live market prices with CoinGecko data
- Portfolio tracker with real-time P&L
- Order placement modal (all 4 order types)
- Price alerts management panel
- AI Trade Coach slide-in panel
- Risk assessment result display
- Backtesting interface
- Notification center

**`templates/ai_tutor.html`** — standalone AI chat page (legacy)

### 2. React / Lovable UI (New Frontend)

Located in `lovable_latest_tmp/` — a **Pixelcade-themed** React app:

```
lovable_latest_tmp/
└── src/
    ├── components/
    │   ├── BottomTutorChat.tsx   ← Floating AI chat widget
    │   ├── PixelLayout.tsx       ← App shell & navigation
    │   ├── PixelComponents.tsx   ← Reusable pixel-art UI components
    │   └── NavLink.tsx           ← Sidebar navigation links
    └── lib/
        ├── mockData.ts           ← Demo portfolio/user data
        └── cryptoKnowledge.ts    ← Topic suggestions for chatbot
```

**BottomTutorChat Features:**
- Floating FAB → expands to full chat panel
- SSE streaming via Supabase Edge Function or Flask `/api/ai-tutor`
- Fetches live portfolio context from `/api/portfolio-context`
- Shows `● Live data` or `○ Demo data` badge
- Markdown-aware message rendering (bold, code, lists, headers)
- Quick-topic suggestion chips

---

## ⚡ Quick Start

### Prerequisites

- Python **3.13+**
- MySQL **8.0+**
- Google Gemini API key (free) → [Get one here](https://makersuite.google.com/app/apikey)

### 1️⃣ Clone & Install

```bash
pip install -r requirements.txt
```

### 2️⃣ Create Database

```bash
mysql -u root -p -e "CREATE DATABASE IF NOT EXISTS crypto_tracker;"
```

### 3️⃣ Apply All Schemas (in order)

```powershell
Get-Content database.sql               | mysql -u root -p crypto_tracker
Get-Content trading_schema.sql         | mysql -u root -p crypto_tracker
Get-Content risk_assessment_schema.sql | mysql -u root -p crypto_tracker
Get-Content learning_system_schema.sql | mysql -u root -p crypto_tracker
Get-Content init_trading.sql           | mysql -u root -p crypto_tracker
```

### 4️⃣ Configure Environment

Create a `.env` file (copy from `.env.example`):

```env
GEMINI_API_KEY=AIza-your-key-here
```

### 5️⃣ Run the App

```bash
python app.py
```

🌐 Open: **http://localhost:5000**

### 6️⃣ (Optional) Run Lovable React Frontend

```bash
cd lovable_latest_tmp
npm install
npm run dev
```

🌐 React UI: **http://localhost:5173**

---

## 🛠️ Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| **Backend** | Flask 2.3+ | REST API + Jinja2 templates |
| **Database** | MySQL 8.0+ | User data, trades, orders, alerts |
| **AI – Generation** | Google Gemini / Claude 3.5 Sonnet | Chat responses & trade advice |
| **AI – Retrieval** | ChromaDB 0.5+ | Vector storage for RAG |
| **AI – Embeddings** | `all-MiniLM-L6-v2` (Sentence Transformers) | Local, free semantic search |
| **Market Data** | CoinGecko API | Live prices, charts, history |
| **Scheduling** | APScheduler | Order & alert background jobs |
| **Auth** | Flask-Bcrypt | Password hashing |
| **Email** | Gmail SMTP (smtplib) | Price alert notifications |
| **Analytics** | NumPy + Pandas | RSI, Sharpe, Volatility, Drawdown |
| **React UI** | React + TypeScript + Vite | Lovable floating chat frontend |
| **Streaming** | Supabase Edge Functions (SSE) | Real-time chat streaming |
| **CORS** | Flask-CORS | Cross-origin React ↔ Flask |

---

## 📁 Project Structure

```
crypto_tracker/
│
├── 🐍 BACKEND
│   ├── app.py                         # Main Flask app (4,383 lines)
│   │                                  # Routes: auth, trading, portfolio,
│   │                                  # alerts, risk, AI coach, backtester
│   ├── ai_assistant.py                # RAG AI system (1,676 lines)
│   │                                  # AIAssistant class:
│   │                                  #   .query()                  – chat + RAG
│   │                                  #   .get_trade_advice()       – pre-trade analyzer
│   │                                  #   .analyze_trade_mistake()  – post-trade coach
│   │                                  #   .generate_daily_challenge() – gamification
│   ├── user_profiler.py               # Trading skill profiler
│   │                                  # Computes win rate, RR ratio, weak areas
│   ├── learning_routes.py             # /learning/* Flask Blueprint
│   ├── risk_assessment_data.py        # Quiz questions & scoring logic
│   └── risk_assessment_routes.py     # /risk/* Flask Blueprint
│
├── 🗄️ DATABASE
│   ├── database.sql                   # users, wallets, transactions, alerts
│   ├── trading_schema.sql             # orders, order_fills, trading_pairs
│   ├── risk_assessment_schema.sql     # risk_profiles, assessments
│   ├── learning_system_schema.sql     # learning_profiles, conversations,
│   │                                  # progress, daily_challenges
│   ├── init_trading.sql               # 10 default trading pairs
│   └── update_risk_columns.sql       # Migration: risk column additions
│
├── 🎨 FLASK TEMPLATES
│   ├── combined.html                  # Main dashboard (413KB monolithic SPA)
│   ├── ai_tutor.html                  # Standalone AI tutor page
│   ├── learning_hub.html              # Learning content hub
│   └── backtester.html               # Strategy backtesting UI
│
├── 🌐 REACT FRONTEND (Lovable UI)
│   └── lovable_latest_tmp/
│       └── src/
│           ├── components/
│           │   ├── BottomTutorChat.tsx   # Floating SSE chat widget
│           │   ├── PixelLayout.tsx        # App shell
│           │   ├── PixelComponents.tsx    # UI component library
│           │   └── NavLink.tsx            # Navigation
│           └── lib/
│               ├── mockData.ts            # Demo portfolio/user fixtures
│               └── cryptoKnowledge.ts     # Topic suggestion chips
│
├── 🧠 KNOWLEDGE BASE (RAG Content)
│   └── vector_db/                     # ChromaDB persistent store
│       ├── chroma.sqlite3             # Vector index
│       └── 35102628-.../             # Segment data
│
├── ⚙️ CONFIG & UTILITIES
│   ├── .env                           # API keys (gitignored)
│   ├── .env.example                   # Template for setup
│   ├── requirements.txt               # Python dependencies
│   ├── setup_learning.ps1             # PowerShell setup script
│   ├── update_db_schema.py            # DB migration helper
│   └── test_alert.py                  # Alert system test script
│
└── 📂 STATIC ASSETS
    ├── static/css/                    # Stylesheets
    └── static/js/                     # charts.js, script.js
```

---

## 🔧 Configuration

### `.env` File Setup

```env
# Required
GEMINI_API_KEY=AIza-your-key-here

# Optional: Enable strict AI mode (errors thrown instead of fallback)
AI_STRICT_MODE=false
```

### Database (in `app.py`)

```python
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': 'your-password',
    'database': 'crypto_tracker'
}
```

### Email Alerts (in `app.py`)

```python
EMAIL_CONFIG = {
    'MAIL_SERVER': 'smtp.gmail.com',
    'MAIL_PORT': 587,
    'MAIL_USE_TLS': True,
    'MAIL_USERNAME': 'your-email@gmail.com',
    'MAIL_PASSWORD': 'your-app-password',   # Use Google App Password
    'MAIL_DEFAULT_SENDER': 'your-email@gmail.com'
}
```

> **Tip:** Enable 2FA on Gmail then generate an **App Password** at myaccount.google.com/apppasswords

### React Frontend (`.env` in `lovable_latest_tmp/`)

```env
VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_PUBLISHABLE_KEY=your-anon-key
VITE_FLASK_URL=http://localhost:5000   # For local dev: hit Flask directly
```

---

## 📝 Database Schema

### Core Tables

| Table | File | Purpose |
|---|---|---|
| `users` | `database.sql` | Auth, balances (crypto_bucks, tether_balance), risk profile |
| `wallets` | `database.sql` | User wallet records |
| `transactions` | `database.sql` | Buy/sell history with P&L |
| `price_alerts` | `database.sql` | Active alerts with snooze & trigger tracking |
| `price_alert_history` | `database.sql` | Full history of fired alerts |
| `notifications` | `database.sql` | In-app notifications |
| `orders` | `trading_schema.sql` | All order types (market/limit/SL/TP) |
| `order_fills` | `trading_schema.sql` | Execution records |
| `trading_pairs` | `trading_schema.sql` | Supported pairs & metadata |
| `risk_assessments` | `risk_assessment_schema.sql` | Full quiz responses |
| `risk_profiles` | `risk_assessment_schema.sql` | Computed profile per user |
| `learning_profiles` | `learning_system_schema.sql` | Skill level, weak areas, stats |
| `learning_conversations` | `learning_system_schema.sql` | AI chat history |
| `learning_progress` | `learning_system_schema.sql` | Lesson/quiz completion |
| `daily_challenges` | `learning_system_schema.sql` | Gamified challenges |
| `watchlist_scenarios` | (auto-created) | Scenario replay results |

---

## 🎮 How to Use

### 🚀 First Run

```
1. Register → verify email
2. Complete risk assessment quiz (4 sections)
3. Receive 10,000 CryptoBucks
4. Dashboard loads with live market data
```

### 💰 Start Trading

```
Live Market → Select coin → Trade button
    → Choose order type
    → Enter amount
    → Submit (executes immediately for market, queued for others)
```

### 🤖 Use the AI Tutor

```
Flask UI: Click floating "AI TUTOR" button on dashboard
React UI: Click "AI CHATBOT" button (bottom-right corner)

→ Type your question
→ AI retrieves relevant knowledge + your live portfolio data
→ Streaming response with sources cited
```

### 📈 Get Pre-Trade AI Advice

```
Live Market → Select coin → "AI Advice" button
→ AI fetches 60 days of price data
→ Computes RSI, MA10, MA50, momentum
→ Returns: Decision (BUY/WAIT/AVOID), Market Story, Trigger, Confidence
```

### 🏆 Daily Challenges

```
AI analyzes your weak areas → assigns challenge
Complete challenge → earn CryptoBucks reward
Examples:
  - "Set stop loss on every trade today"   (+500 CB$)
  - "Keep positions under 5% of capital"  (+300 CB$)
```

---

## 📄 License

MIT License — Free to use, modify, and distribute.

---

<div align="center">
  <p>Built with 🧠 AI + 💙 Python + ☕ late nights</p>
  <p><strong>CoinPrep Simulator</strong> — Learn to trade without losing real money</p>
</div>
