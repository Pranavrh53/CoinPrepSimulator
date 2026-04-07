<div align="center">

# 🚀 CoinPrep Simulator

**Your AI-Powered Crypto Trading Simulator & Learning Platform**

![Python](https://img.shields.io/badge/Python-3.13+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-2.3+-000000?style=for-the-badge&logo=flask&logoColor=white)
![MongoDB](https://img.shields.io/badge/MongoDB-6.0+-47A248?style=for-the-badge&logo=mongodb&logoColor=white)
![Gemini](https://img.shields.io/badge/Google_Gemini-AI-8E75B2?style=for-the-badge&logo=google&logoColor=white)
![ChromaDB](https://img.shields.io/badge/ChromaDB-RAG-orange?style=for-the-badge)
![React](https://img.shields.io/badge/React-Lovable_UI-61DAFB?style=for-the-badge&logo=react&logoColor=black)

*Trade smarter. Learn faster. Risk nothing.*

</div>

---

## Table of Contents

- [What's New](#whats-new)
- [Features](#features)
- [AI Intelligence System](#ai-intelligence-system)
- [Trading Engine](#trading-engine)
- [Risk Assessment](#risk-assessment)
- [UI Frontends](#ui-frontends)
- [Quick Start](#quick-start)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Configuration](#configuration)
- [Database Schema](#database-schema)
- [How to Use](#how-to-use)

---

## What's New

> Major additions since the original release:

| Feature | Description |
|---|---|
| **RAG AI Tutor** | Full Retrieval-Augmented Generation pipeline with ChromaDB + Sentence Transformers |
| **Live Portfolio Chat** | AI grounded in real-time portfolio holdings, balances & trade history — no hallucination |
| **AI Trade Advisor** | Pre-trade BUY/WAIT/AVOID decisions using RSI, MA10, MA50 from 60-day price data |
| **AI Trading Coach** | Post-trade mistake analysis: Edge Insight, Critical Pattern, Next Focus + download report |
| **Daily Challenges** | AI-assigned personalized challenges based on weakest trading skills + CB$ rewards |
| **Watchlist Replay** | Replay historical scenarios (Conservative / Rule-Based / Emotional) with prep score |
| **Enhanced Alerts** | Snooze alerts, full trigger history table, persistent notes per alert |
| **React Floating Chat** | `BottomTutorChat.tsx` — streaming SSE chat widget with live/demo data badge |
| **Dual Frontend** | Flask (port 5000) + React/Vite (port 5173) with CORS support |

---

## Features

### Portfolio Management
- Real-time holdings tracker with live CoinGecko prices (10-min cache + retry)
- Unrealized & Realized P&L, average buy price per coin
- 30-day Sharpe Ratio, Volatility, Max Drawdown, Correlation Matrix

### Trading System

| Order Type | Behaviour |
|---|---|
| Market Order | Instant execution at live price |
| Limit Buy/Sell | Executes when price hits target |
| Stop Loss | Auto-sells when price drops below threshold |
| Take Profit | Auto-sells when price rises above threshold |

- 10 default coins: BTC, ETH, BNB, XRP, ADA, SOL, DOT, DOGE, AVAX, USDT
- 0.1% fee on all trades · Background executor every 5 min (APScheduler)
- Insufficient balance → auto-cancel with reason logged

### Price Alerts
- Above/below threshold alerts with snooze support
- Gmail SMTP email on trigger · Full history in `price_alert_history`

### Backtesting Engine
- Historical strategy testing: returns, drawdown, win rate

### Security
- Email verification on registration · Bcrypt password hashing · Session management

---

## AI Intelligence System

### RAG Pipeline

```
User Question
      │
      ├─ Portfolio query? → Fetch live database data (holdings / orders / balances)
      │
      ▼
ChromaDB Vector Search  →  top-3 relevant knowledge chunks
      │
      ▼
Build Prompt  (skill level + risk tolerance + portfolio context + RAG docs)
      │
      ▼
Claude 3.5 Sonnet  OR  Google Gemini  →  Safety Disclaimer  →  Response
```

### Knowledge Base

| Category | Topics |
|---|---|
| `crypto_basics` | Blockchain, wallets, how crypto works |
| `trading_strategies` | Stop loss, position sizing, entry/exit |
| `psychology` | FOMO, emotional trading, discipline |
| `case_studies` | 2021 Leverage Trap, real loss scenarios |

### Trade Advisor Indicators (60-day CoinGecko data)

| Indicator | Period | Use |
|---|---|---|
| RSI | 14-period | Overbought / Oversold |
| MA10 | 10-period | Short-term trend |
| MA50 | 50-period | Long-term trend |
| Momentum score | Last 5 prices | Prediction 10–90% |

### Portfolio Query Detection
Recognises 30+ intent keywords: `portfolio`, `holding`, `balance`, `p/l`, `profit`, `open order`, `what do I hold`, `how much`, `my trade`, etc.

### AI Provider Fallback
```
"auto" mode  →  sk-ant-* key → Claude 3.5 Sonnet
             →  otherwise   → Google Gemini
             →  both fail   → Rule-based advisor (app never breaks)
```

---

## Trading Engine

### Starting Capital

| Currency | Amount |
|---|---|
| CryptoBucks (CB$) | 10,000 |
| USDT | 0 (convert from CB$) |
| Crypto | 0 (buy with USDT) |

### Order Execution Flow
```
Market order  →  immediate execution
Limit / SL / TP  →  APScheduler checks every 5 min
                      ├─ Condition met  →  execute + log fill
                      └─ Low balance   →  auto-cancel
```

---

## Risk Assessment

A 4-part quiz that builds a personalised risk profile:

| Section | Measures |
|---|---|
| Financial Capacity | Income, savings, emergency fund |
| Investment Knowledge | Market experience, crypto familiarity |
| Psychological Tolerance | Reaction to losses, emotional resilience |
| Goals & Timeline | Investment horizon, return targets |

**Output:** Risk score (0–100%) · Category (Conservative → Aggressive) · Asset allocation · Crypto % recommendation · Strength/concern flags · Mismatch detection

---

## UI Frontends

### 1 · Flask / Jinja2 (Primary — `combined.html`)
- Live market, portfolio P&L, order placement, price alerts, AI coach panel, backtester, notifications

### 2 · React / Lovable UI (`lovable_latest_tmp/`)
Pixelcade-themed frontend with floating AI chat:

| Component | Role |
|---|---|
| `BottomTutorChat.tsx` | Streaming SSE chat widget (bottom-right FAB) |
| `PixelLayout.tsx` | App shell & sidebar nav |
| `PixelComponents.tsx` | Reusable pixel-art UI kit |
| `mockData.ts` | Demo portfolio fixtures (fallback) |
| `cryptoKnowledge.ts` | Quick-topic suggestion chips |

Chat connects to Supabase Edge Function (prod) or Flask `/api/ai-tutor` (dev). Shows **● Live data** or **○ Demo data** badge.

---

## Quick Start

### Prerequisites
- Python 3.13+ · MongoDB 6.0+ · [Google Gemini API key (free)](https://makersuite.google.com/app/apikey)

### 1 · Install

```bash
pip install -r requirements.txt
```

### 2 · Initialize MongoDB Database

```powershell
mongosh --eval "use('crypto_tracker')"
```

### 3 · Apply Schema + Seed Data

```powershell
mongosh mongodb/schema.js
mongosh mongodb/seed.js
```

### 4 · Set API Key

```bash
# Linux / macOS
export GEMINI_API_KEY="AIza-your-key"

# Windows PowerShell
$env:GEMINI_API_KEY="AIza-your-key"
```

Or add to `.env` (copied from `.env.example`):
```env
GEMINI_API_KEY=AIza-your-key-here
```

### 5 · Run Flask App

```bash
python app.py
```
→ Open **http://localhost:5000**

### 6 · (Optional) Run React Frontend

```bash
cd lovable_latest_tmp
npm install && npm run dev
```
→ Open **http://localhost:5173**

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Flask 2.3+ |
| Database | MongoDB 6.0+ |
| AI Generation | Google Gemini / Claude 3.5 Sonnet |
| AI Retrieval | ChromaDB 0.5+ |
| AI Embeddings | `all-MiniLM-L6-v2` (Sentence Transformers, local) |
| Market Data | CoinGecko API |
| Scheduling | APScheduler |
| Auth | Flask-Bcrypt |
| Email | Gmail SMTP (smtplib) |
| Analytics | NumPy + Pandas |
| React Frontend | React + TypeScript + Vite |
| Streaming | Supabase Edge Functions (SSE) |
| CORS | Flask-CORS |

---

## Project Structure

```
crypto_tracker/
├── app.py                        # Flask app — auth, trading, portfolio, alerts, AI coach
├── ai_assistant.py               # RAG AI engine — chat, trade advisor, coaching, challenges
├── user_profiler.py              # Skill profiler — win rate, RR ratio, weak areas
├── learning_routes.py            # /learning/* Blueprint
├── risk_assessment_data.py       # Quiz questions & scoring
├── risk_assessment_routes.py     # /risk/* Blueprint
│
├── templates/
│   ├── combined.html             # Main dashboard (monolithic SPA)
│   ├── ai_tutor.html             # Standalone AI chat page
│   ├── learning_hub.html         # Learning hub
│   └── backtester.html           # Backtesting UI
│
├── lovable_latest_tmp/           # React / Lovable frontend
│   └── src/
│       ├── components/
│       │   ├── BottomTutorChat.tsx
│       │   ├── PixelLayout.tsx
│       │   ├── PixelComponents.tsx
│       │   └── NavLink.tsx
│       └── lib/
│           ├── mockData.ts
│           └── cryptoKnowledge.ts
│
├── vector_db/                    # ChromaDB persistent store
│
├── database.sql                  # Core schema
├── trading_schema.sql            # Orders & fills
├── risk_assessment_schema.sql    # Risk profiles
├── learning_system_schema.sql    # Learning + challenges
├── init_trading.sql              # Default trading pairs
│
├── .env.example                  # Environment template
├── requirements.txt              # Python dependencies
└── setup_learning.ps1            # PowerShell setup helper
```

---

## Configuration

### `.env`
```env
GEMINI_API_KEY=AIza-your-key-here
AI_STRICT_MODE=false        # true = raise errors instead of rule-based fallback
```

### Database (`app.py`)
```python
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': 'your-password',
    'database': 'crypto_tracker'
}
```

### Email (`app.py`)
```python
EMAIL_CONFIG = {
    'MAIL_SERVER': 'smtp.gmail.com',
    'MAIL_PORT': 587,
    'MAIL_USE_TLS': True,
    'MAIL_USERNAME': 'your@gmail.com',
    'MAIL_PASSWORD': 'your-app-password'   # Google App Password
}
```

### React `.env` (`lovable_latest_tmp/.env`)
```env
VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_PUBLISHABLE_KEY=your-anon-key
VITE_FLASK_URL=http://localhost:5000
```

---

## Database Schema

| Collection | Schema File | Purpose |
|---|---|---|
| `users` | `mongodb/schema.js` | Auth, CB$ balance, USDT balance, risk profile |
| `wallets` | `mongodb/schema.js` | Wallet records |
| `transactions` | `mongodb/schema.js` | Buy/sell history with P&L |
| `price_alerts` | `mongodb/schema.js` | Alerts with snooze & trigger fields |
| `price_alert_history` | `mongodb/schema.js` | Every fired alert |
| `notifications` | `mongodb/schema.js` | In-app notifications |
| `orders` | `mongodb/schema.js` | All order types (market/limit/SL/TP) |
| `order_fills` | `mongodb/schema.js` | Execution records |
| `trading_pairs` | `mongodb/schema.js` | Supported pairs |
| `risk_assessments` | `mongodb/schema.js` | Full quiz responses |
| `user_risk_profiles_view` | `mongodb/schema.js` | Latest profile projection per user |
| `learning_profiles` | `mongodb/schema.js` | Skill level, weak areas |
| `ai_conversations` | `mongodb/schema.js` | AI chat history |
| `learning_progress` | `mongodb/schema.js` | Lesson completion |
| `daily_challenges` | `mongodb/schema.js` | Gamified challenges |
| `watchlist_scenarios` | `mongodb/schema.js` | Scenario replay results |
| seed data (`admin`, pairs, docs) | `mongodb/seed.js` | Initial bootstrap records |

---

## How to Use

**First Run**
1. Register → verify email → complete 4-part risk quiz → receive 10,000 CB$

**Trade**
1. Live Market → select coin → Trade → pick order type → enter amount → submit

**AI Tutor**
- Flask: floating "AI TUTOR" button on dashboard
- React: "AI CHATBOT" FAB (bottom-right)
- AI pulls live portfolio + knowledge base before answering

**Pre-Trade AI Advice**
- Live Market → select coin → "AI Advice" — returns Decision + Market Story + Trigger + Confidence

**Daily Challenges**
- AI detects your weak area → sets challenge (e.g. *"Use stop loss on every trade"* → +500 CB$)

---

<div align="center">

Built with 🧠 AI · 💙 Python · ☕ Late nights

**CoinPrep Simulator** — Learn to trade without losing real money

</div>
