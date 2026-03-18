"""
RAG-Powered AI Assistant for Crypto Trading Simulator
Uses ChromaDB for vector storage and Claude/Gemini for responses
"""

import os
import json
import time
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions
try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

try:
    from google import genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

from pathlib import Path


class AIAssistant:
    def __init__(self, db_connection, api_key: str, provider: str = "auto"):
        """
        Initialize the RAG-powered AI assistant
        
        Args:
            db_connection: MySQL connection function
            api_key: Your AI API key (Claude or Gemini)
            provider: "claude", "gemini", or "auto" (auto-detect)
        """
        self.get_db = db_connection
        self.api_key = api_key
        
        # Determine which AI provider to use
        if provider == "auto":
            if api_key.startswith("sk-ant-") and ANTHROPIC_AVAILABLE:
                self.provider = "claude"
            elif GEMINI_AVAILABLE:
                self.provider = "gemini"
            elif ANTHROPIC_AVAILABLE:
                self.provider = "claude"
            else:
                raise ValueError("No AI provider available. Install: pip install google-generativeai")
        else:
            self.provider = provider
        
        # Initialize AI client
        if self.provider == "claude":
            if not ANTHROPIC_AVAILABLE:
                raise ValueError("Anthropic not installed. Run: pip install anthropic")
            self.ai_client = anthropic.Anthropic(api_key=api_key)
        elif self.provider == "gemini":
            if not GEMINI_AVAILABLE:
                raise ValueError("Google GenAI not installed. Run: pip install google-genai")
            self.genai_client = genai.Client(api_key=api_key)
        else:
            raise ValueError(f"Unknown provider: {provider}")
        
        # Initialize ChromaDB with sentence transformers
        self.chroma_client = chromadb.PersistentClient(
            path="./vector_db",
            settings=Settings(anonymized_telemetry=False)
        )
        
        # Use sentence transformers for embeddings (free, local)
        self.embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"  # Fast, lightweight model
        )
        
        # Get or create collection
        self.collection = self.chroma_client.get_or_create_collection(
            name="crypto_learning_knowledge",
            embedding_function=self.embedding_function,
            metadata={"description": "Crypto trading educational content"}
        )
        
        # Safety disclaimer
        self.SAFETY_DISCLAIMER = """
        ⚠️ IMPORTANT DISCLAIMER:
        - This is educational content for a SIMULATOR using fake money
        - NOT financial advice
        - Real crypto trading involves significant risk
        - Never invest more than you can afford to lose
        - Past performance doesn't guarantee future results
        """
    
    def index_knowledge_base(self, knowledge_dir: str = "./knowledge") -> Dict:
        """
        Index all markdown files from knowledge base into ChromaDB
        
        Returns:
            Dict with indexing statistics
        """
        indexed_files = 0
        total_chunks = 0
        errors = []
        
        knowledge_path = Path(knowledge_dir)
        
        if not knowledge_path.exists():
            return {"error": "Knowledge directory not found", "path": knowledge_dir}
        
        # Find all markdown files
        md_files = list(knowledge_path.rglob("*.md"))
        
        for md_file in md_files:
            try:
                with open(md_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Extract metadata from file path and content
                category = md_file.parent.name
                title = self._extract_title(content)
                difficulty = self._extract_difficulty(content)
                
                # Split into chunks (for long documents)
                chunks = self._split_content(content)
                
                # Store in ChromaDB
                for i, chunk in enumerate(chunks):
                    doc_id = f"{md_file.stem}_chunk_{i}"
                    
                    self.collection.add(
                        documents=[chunk],
                        metadatas=[{
                            "title": title,
                            "category": category,
                            "difficulty": difficulty,
                            "file_path": str(md_file),
                            "chunk_index": i,
                            "total_chunks": len(chunks)
                        }],
                        ids=[doc_id]
                    )
                    total_chunks += 1
                
                # Log to database
                self._log_indexed_document(
                    doc_id=md_file.stem,
                    title=title,
                    category=category,
                    file_path=str(md_file),
                    difficulty=difficulty,
                    word_count=len(content.split())
                )
                
                indexed_files += 1
                
            except Exception as e:
                errors.append(f"{md_file.name}: {str(e)}")
        
        return {
            "indexed_files": indexed_files,
            "total_chunks": total_chunks,
            "errors": errors,
            "timestamp": datetime.now().isoformat()
        }
    
    def query(
        self, 
        user_id: int, 
        question: str, 
        session_id: Optional[str] = None,
        n_results: int = 3
    ) -> Dict:
        """
        Main query method: RAG search + personalized prompt + Claude response
        
        Args:
            user_id: User ID for personalization
            question: User's question
            session_id: Conversation session ID
            n_results: Number of relevant docs to retrieve
            
        Returns:
            Dict with response, sources, and metadata
        """
        start_time = time.time()
        
        # 1. Get user profile for personalization
        user_profile = self._get_user_profile(user_id)
        
        # 2. Search knowledge base (RAG)
        relevant_docs = self._search_knowledge(question, n_results)
        
        # 3. Build personalized prompt
        prompt = self._build_prompt(question, user_profile, relevant_docs)
        
        # 4. Query AI (Claude or Gemini)
        try:
            if self.provider == "claude":
                response = self.ai_client.messages.create(
                    model="claude-3-5-sonnet-20241022",
                    max_tokens=2048,
                    temperature=0.7,
                    system=self._get_system_prompt(user_profile),
                    messages=[{"role": "user", "content": prompt}]
                )
                ai_response = response.content[0].text
                
            elif self.provider == "gemini":
                full_prompt = f"{self._get_system_prompt(user_profile)}\n\n{prompt}"
                ai_response = self._generate_gemini(
                    prompt=full_prompt,
                    temperature=0.7,
                    max_output_tokens=2048
                )
            
        except Exception as e:
            ai_response = f"I encountered an error: {str(e)}. Please try again or rephrase your question."
        
        # 5. Add safety disclaimer
        final_response = f"{ai_response}\n\n{self.SAFETY_DISCLAIMER}"
        
        # 6. Log conversation
        response_time = int((time.time() - start_time) * 1000)
        self._log_conversation(
            user_id=user_id,
            session_id=session_id or f"session_{int(time.time())}",
            question=question,
            response=final_response,
            docs_used=[doc['id'] for doc in relevant_docs],
            response_time=response_time,
            user_skill=user_profile['skill_level']
        )
        
        return {
            "response": final_response,
            "sources": [{"title": doc['metadata']['title'], 
                        "category": doc['metadata']['category']} 
                       for doc in relevant_docs],
            "response_time_ms": response_time,
            "user_level": user_profile['skill_level']
        }
    
    def analyze_trade_mistake(self, user_id: int, transaction_id: int) -> str:
        """
        Generate personalized lesson from a user's losing trade
        
        Args:
            user_id: User ID
            transaction_id: The losing trade ID
            
        Returns:
            Personalized analysis and lesson
        """
        # Get trade details
        conn = self.get_db()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT t.*, u.crypto_bucks, u.risk_tolerance
            FROM transactions t
            JOIN users u ON t.user_id = u.id
            WHERE t.id = %s AND t.user_id = %s
        """, (transaction_id, user_id))
        
        trade = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not trade:
            return "Trade not found."
        
        # Calculate loss
        if trade['sold_price']:
            loss_pct = ((trade['sold_price'] - trade['price']) / trade['price']) * 100
            loss_amount = (trade['sold_price'] - trade['price']) * trade['amount']
        else:
            return "Trade not yet closed."
        
        # Identify mistake type
        mistake_type = self._identify_mistake_type(trade, loss_pct)
        
        # Get relevant knowledge
        search_query = f"common mistakes {mistake_type} how to avoid"
        relevant_docs = self._search_knowledge(search_query, n_results=2)
        
        # Build analysis prompt
        prompt = f"""
        A user just made a losing trade in our simulator. Analyze what went wrong and teach them:

        TRADE DETAILS:
        - Coin: {trade['coin_id']}
        - Buy Price: ${trade['price']}
        - Sell Price: ${trade['sold_price']}
        - Amount: {trade['amount']}
        - Loss: {loss_pct:.2f}% (${abs(loss_amount):.2f})
        - Trade Type: {trade['type']}
        
        IDENTIFIED MISTAKE: {mistake_type}
        
        USER PROFILE:
        - Risk Tolerance: {trade['risk_tolerance']}
        - Remaining Capital: ${trade['crypto_bucks']}
        
        RELEVANT KNOWLEDGE:
        {self._format_docs_for_prompt(relevant_docs)}
        
        Provide:
        1. What specifically went wrong
        2. Why it happened (psychology)
        3. How to prevent it next time
        4. Specific action plan
        
        Be direct, personal, and constructive. Use their specific numbers.
        """
        
        try:
            if self.provider == "claude":
                response = self.ai_client.messages.create(
                    model="claude-3-5-sonnet-20241022",
                    max_tokens=1500,
                    temperature=0.8,
                    messages=[{"role": "user", "content": prompt}]
                )
                analysis = response.content[0].text
            elif self.provider == "gemini":
                analysis = self._generate_gemini(
                    prompt=prompt,
                    temperature=0.8,
                    max_output_tokens=1500
                )
            
            # Log the mistake
            self._log_trade_mistake(user_id, transaction_id, mistake_type, loss_amount, analysis)
            
            return analysis
            
        except Exception as e:
            return f"Could not analyze trade: {str(e)}"
    
    def generate_daily_challenge(self, user_id: int) -> Dict:
        """
        Create personalized daily challenge based on weak areas
        
        Returns:
            Dict with challenge details
        """
        user_profile = self._get_user_profile(user_id)
        weak_areas = user_profile.get('weak_areas', [])
        
        if not weak_areas:
            weak_areas = ['risk_management']  # Default challenge
        
        # Focus on biggest weakness
        focus_area = weak_areas[0]
        
        challenges = {
            'stop_loss': {
                'type': 'use_stop_loss',
                'description': 'Set a stop loss on every trade today',
                'target_metric': 'stop_loss_usage_rate',
                'target_value': 100.0,
                'reward': 500
            },
            'risk_management': {
                'type': 'limit_risk',
                'description': 'Keep position sizes under 5% of capital',
                'target_metric': 'max_position_size_pct',
                'target_value': 5.0,
                'reward': 300
            },
            'leverage': {
                'type': 'no_leverage',
                'description': 'Make 3 trades without using leverage',
                'target_metric': 'trades_without_leverage',
                'target_value': 3,
                'reward': 400
            }
        }
        
        challenge = challenges.get(focus_area, challenges['risk_management'])
        
        # Save to database
        conn = self.get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO daily_challenges 
            (user_id, challenge_date, challenge_type, description, target_metric, 
             target_value, reward_crypto_bucks, expires_at)
            VALUES (%s, CURDATE(), %s, %s, %s, %s, %s, DATE_ADD(NOW(), INTERVAL 24 HOUR))
            ON DUPLICATE KEY UPDATE description=description
        """, (user_id, challenge['type'], challenge['description'], 
              challenge['target_metric'], challenge['target_value'], challenge['reward']))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return challenge
    
    def get_trade_advice(self, user_id: int, coin_id: str, current_price: float, 
                         price_change_24h: float = 0.0) -> Dict:
        """
        Phase 1: Before Trade → Decision Help
        AI-powered trade advisor that analyzes market conditions and gives
        BUY / WAIT / AVOID decisions personalized to user's risk level.
        
        Args:
            user_id: User ID for personalization
            coin_id: The coin being considered (e.g., 'bitcoin')
            current_price: Current market price
            price_change_24h: 24h price change percentage
            
        Returns:
            Dict with AI advice, market analysis, and metadata
        """
        import requests as req
        start_time = time.time()
        
        # 1. Get user's risk tolerance from database
        risk_level = "medium"  # default
        try:
            conn = self.get_db()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT risk_tolerance, risk_score FROM users WHERE id = %s", (user_id,))
            user = cursor.fetchone()
            cursor.close()
            conn.close()
            
            if user and user.get('risk_tolerance'):
                rt = user['risk_tolerance'].lower()
                if 'conservative' in rt or '1/5' in rt:
                    risk_level = "low"
                elif 'moderate' in rt or '2/5' in rt or '3/5' in rt or 'balanced' in rt:
                    risk_level = "medium"
                elif 'growth' in rt or 'aggressive' in rt or '4/5' in rt or '5/5' in rt:
                    risk_level = "high"
        except Exception as e:
            print(f"Error fetching user risk: {e}")
        
        # 2. Fetch historical market data for technical analysis
        coin_display = coin_id.replace("-", " ").title()
        rsi = 50.0  # defaults
        ma10 = current_price
        ma50 = current_price
        prediction = 50.0
        recent_prices = []
        
        try:
            # Fetch 60 days of data for MA50 calculation
            api_url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart?vs_currency=usd&days=60"
            resp = req.get(api_url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                prices = [p[1] for p in data.get('prices', [])]
                recent_prices = prices
                
                if len(prices) >= 14:
                    # Calculate RSI (14-period)
                    rsi = self._calculate_rsi(prices, period=14)
                
                if len(prices) >= 10:
                    # 10-period Moving Average
                    ma10 = sum(prices[-10:]) / 10
                
                if len(prices) >= 50:
                    # 50-period Moving Average
                    ma50 = sum(prices[-50:]) / 50
                
                # Simple prediction model based on momentum
                if len(prices) >= 5:
                    recent_trend = (prices[-1] - prices[-5]) / prices[-5] * 100
                    rsi_factor = (70 - rsi) / 70  # Higher when RSI is low
                    ma_factor = 1.0 if ma10 > ma50 else -0.5
                    prediction = max(10, min(90, 50 + recent_trend * 2 + rsi_factor * 20 + ma_factor * 10))
        except Exception as e:
            print(f"Error calculating technical indicators: {e}")

        market_context = self._analyze_recent_market_behavior(
            coin_id=coin_id,
            coin_name=coin_display,
            prices=recent_prices,
            current_price=current_price,
            price_change_24h=price_change_24h,
            ma10=ma10,
            ma50=ma50
        )
        
        # 3. Keep lightweight knowledge retrieval for logging/source context
        search_query = f"trading strategy {coin_id} risk management buy sell decision"
        relevant_docs = self._search_knowledge(search_query, n_results=2)

        # 4. Build the trade advisor prompt - behavior-first, coin-specific, beginner-focused
        key_events_text = "\n".join(f"- {evt}" for evt in market_context['key_events'])
        prompt = f"""You are an expert crypto trading mentor analyzing real market behavior for a beginner.

Your goal is to THINK like a trader, not describe indicators.

IMPORTANT RULES:
- Do NOT repeat generic phrases like "market is sideways" without explaining WHY
- Do NOT mention RSI/MA unless used in reasoning
- Focus on telling a clear MARKET STORY
- Be decisive and practical

-------------------------------------

User Profile:
- Risk Level: {risk_level}
- Experience: Beginner

Coin: {coin_display}

-------------------------------------

Recent Market Behavior:
{market_context['market_summary']}

Key Events:
{key_events_text}

AI Prediction:
{prediction:.1f}% probability of price increase

-------------------------------------

Task:

1. First, identify the MARKET STORY:
    - What just happened? (drop, pump, consolidation)
    - What is happening NOW? (holding support, breaking down, recovering)

2. Then make a STRONG DECISION:
    - BUY -> only if clear opportunity
    - WAIT -> if setup is forming but not confirmed
    - AVOID -> if conditions are unfavorable

3. Your reasoning MUST:
    - Clearly explain WHY the decision is taken
    - Mention cause-effect (e.g., drop -> support -> possible bounce)
    - Avoid vague words like "sideways" without explanation

4. Add a TRIGGER CONDITION:
    - Tell the user EXACTLY what to wait for
    (example: "Buy only if price breaks above X")

5. Make it feel SPECIFIC and SITUATIONAL, not generic

-------------------------------------

Output Format:

Decision: (BUY / WAIT / AVOID)

Market Story:
(Explain what happened and what is happening now in a clear narrative)

Why This Decision:
- Bullet 1 (cause-effect reasoning)
- Bullet 2 (risk or trend insight)
- Bullet 3 (prediction or confirmation logic)

What To Watch (IMPORTANT):
(1 clear actionable trigger like breakout, higher low, etc.)

Timing Insight:
(Early / Late / Risky / Good - with explanation)

Confidence:
(Low / Medium / High)

Beginner Tip:
(Practical, not generic)

-------------------------------------

STRICT:
- Avoid generic repeated phrases
- Make each response feel unique to the coin's behavior"""
        
        # 5. Query AI
        ai_available = True
        ai_error = ""
        try:
            if self.provider == "claude":
                response = self.ai_client.messages.create(
                    model="claude-3-5-sonnet-20241022",
                    max_tokens=1024,
                    temperature=0.6,
                    system="You are an expert crypto trading mentor for a simulator app. Focus on real recent market behavior and coin-specific context. Avoid generic indicator explanations and follow the output format exactly.",
                    messages=[{"role": "user", "content": prompt}]
                )
                ai_response = response.content[0].text
                
            elif self.provider == "gemini":
                system_prompt = "You are an expert crypto trading mentor for a simulator app. Focus on real recent market behavior and coin-specific context. Avoid generic indicator explanations and follow the output format exactly."
                full_prompt = f"{system_prompt}\n\n{prompt}"
                ai_response = self._generate_gemini(
                    prompt=full_prompt,
                    temperature=0.6,
                    max_output_tokens=1024
                )
                
        except Exception as e:
            ai_available = False
            if self.provider == "gemini":
                ai_error = self._summarize_gemini_error(str(e))
            else:
                ai_error = "Claude API request failed"
            strict_mode = (os.getenv('AI_STRICT_MODE') or 'false').strip().lower() == 'true'
            if strict_mode:
                raise RuntimeError(ai_error)
            ai_response = self._build_rule_based_trade_advice(
                coin_id=coin_id,
                risk_level=risk_level,
                rsi=rsi,
                ma10=ma10,
                ma50=ma50,
                prediction=prediction,
                price_change_24h=price_change_24h,
                market_summary=market_context['market_summary'],
                key_events=market_context['key_events'],
                trend=market_context['trend'],
                volatility_level=market_context['volatility_level'],
                error=str(e)
            )
        
        # 6. Parse the response to extract structured data
        parsed = self._parse_trade_advice(ai_response)

        signal_scores = self._compute_trade_signal_scores(
            rsi=rsi,
            ma10=ma10,
            ma50=ma50,
            prediction=prediction,
            price_change_24h=price_change_24h,
            risk_level=risk_level
        )
        
        response_time = int((time.time() - start_time) * 1000)
        
        # 7. Log the advice
        self._log_conversation(
            user_id=user_id,
            session_id=f"trade_advisor_{int(time.time())}",
            question=f"Trade advice for {coin_id} at ${current_price}",
            response=ai_response,
            docs_used=[doc['id'] for doc in relevant_docs],
            response_time=response_time,
            user_skill=risk_level
        )
        
        return {
            "advice": ai_response,
            "parsed": parsed,
            "market_data": {
                "coin": coin_id,
                "price": current_price,
                "rsi": round(rsi, 1),
                "ma10": round(ma10, 2),
                "ma50": round(ma50, 2),
                "price_change": price_change_24h,
                "prediction": round(prediction, 1),
                "trend": market_context['trend'],
                "volatility_level": market_context['volatility_level'],
                "market_summary": market_context['market_summary'],
                "key_events": market_context['key_events'],
                "signal_scores": signal_scores
            },
            "user_risk_level": risk_level,
            "response_time_ms": response_time,
            "ai_available": ai_available,
            "ai_error": ai_error,
            "provider": self.provider,
            "disclaimer": "⚠️ This is for a SIMULATOR with fake money. NOT financial advice."
        }
    
    def _calculate_rsi(self, prices: list, period: int = 14) -> float:
        """Calculate Relative Strength Index"""
        if len(prices) < period + 1:
            return 50.0
        
        deltas = [prices[i+1] - prices[i] for i in range(len(prices)-1)]
        recent_deltas = deltas[-(period):]
        
        gains = [d for d in recent_deltas if d > 0]
        losses = [-d for d in recent_deltas if d < 0]
        
        avg_gain = sum(gains) / period if gains else 0
        avg_loss = sum(losses) / period if losses else 0.001
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return max(0, min(100, rsi))
    
    def _parse_trade_advice(self, response_text: str) -> Dict:
        """Parse structured advice from AI response"""
        parsed = {
            "decision": "WAIT",
            "confidence": "Medium",
            "market_situation": "",
            "reasoning": [],
            "what_to_watch": "",
            "timing_insight": "",
            "why_buy": [],
            "why_not_buy": [],
            "risk_warning": "",
            "beginner_tip": ""
        }
        
        lines = response_text.strip().split('\n')
        current_section = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Parse Decision
            if line.lower().startswith('decision:'):
                decision = line.split(':', 1)[1].strip().upper()
                if 'AVOID' in decision:
                    parsed['decision'] = 'AVOID'
                elif 'BUY' in decision and 'WAIT' not in decision and 'AVOID' not in decision:
                    parsed['decision'] = 'BUY'
                else:
                    parsed['decision'] = 'WAIT'
                current_section = None
                    
            # Parse Confidence
            elif line.lower().startswith('confidence:'):
                conf = line.split(':', 1)[1].strip().lower()
                if 'high' in conf:
                    parsed['confidence'] = 'High'
                elif 'low' in conf:
                    parsed['confidence'] = 'Low'
                else:
                    parsed['confidence'] = 'Medium'
                current_section = None

            elif line.lower() == 'confidence:':
                current_section = 'confidence'
                    
            # Section headers
            elif 'market situation' in line.lower() or 'market story' in line.lower():
                current_section = 'market_situation'
            elif 'key reasoning' in line.lower() or 'why this decision' in line.lower():
                current_section = 'reasoning'
            elif 'what to watch' in line.lower():
                current_section = 'what_to_watch'
            elif 'timing insight' in line.lower():
                current_section = 'timing_insight'
            elif 'why consider buying' in line.lower():
                current_section = 'why_buy'
            elif 'why not buy yet' in line.lower():
                current_section = 'why_not_buy'
            elif 'risk warning' in line.lower():
                current_section = 'risk_warning'
            elif 'beginner tip' in line.lower():
                current_section = 'beginner_tip'
                
            # Parse content under sections
            elif line.startswith('- ') or line.startswith('• '):
                content = line[2:].strip()
                if current_section == 'reasoning':
                    parsed['reasoning'].append(content)
                elif current_section == 'what_to_watch':
                    parsed['what_to_watch'] = content if not parsed['what_to_watch'] else parsed['what_to_watch'] + ' ' + content
                elif current_section == 'why_buy':
                    parsed['why_buy'].append(content)
                elif current_section == 'why_not_buy':
                    parsed['why_not_buy'].append(content)
                elif current_section == 'risk_warning':
                    parsed['risk_warning'] = content if not parsed['risk_warning'] else parsed['risk_warning'] + ' ' + content
                elif current_section == 'beginner_tip':
                    parsed['beginner_tip'] = content if not parsed['beginner_tip'] else parsed['beginner_tip'] + ' ' + content

            else:
                if current_section == 'market_situation':
                    parsed['market_situation'] = line if not parsed['market_situation'] else parsed['market_situation'] + ' ' + line
                elif current_section == 'what_to_watch':
                    parsed['what_to_watch'] = line if not parsed['what_to_watch'] else parsed['what_to_watch'] + ' ' + line
                elif current_section == 'timing_insight':
                    parsed['timing_insight'] = line if not parsed['timing_insight'] else parsed['timing_insight'] + ' ' + line
                elif current_section == 'confidence':
                    conf = line.strip().lower()
                    if 'high' in conf:
                        parsed['confidence'] = 'High'
                    elif 'low' in conf:
                        parsed['confidence'] = 'Low'
                    else:
                        parsed['confidence'] = 'Medium'
                elif current_section == 'beginner_tip':
                    parsed['beginner_tip'] = line if not parsed['beginner_tip'] else parsed['beginner_tip'] + ' ' + line
        
        return parsed

    # ==================== PRIVATE HELPER METHODS ====================

    def _generate_gemini(self, prompt: str, temperature: float, max_output_tokens: int) -> str:
        """Generate content using Gemini with stable model fallbacks."""
        preferred_model = (os.getenv('GEMINI_MODEL') or '').strip()
        candidate_models = []

        if preferred_model:
            candidate_models.append(preferred_model)

        # Stable defaults across most API keys/projects.
        candidate_models.extend([
            'gemini-1.5-flash',
            'gemini-1.5-pro',
            'gemini-2.0-flash',
        ])

        tried = set()
        errors = []

        for model_name in candidate_models:
            if not model_name or model_name in tried:
                continue
            tried.add(model_name)

            try:
                response = self.genai_client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config={
                        'temperature': temperature,
                        'max_output_tokens': max_output_tokens,
                    }
                )

                text = getattr(response, 'text', None)
                if text:
                    return text

                return str(response)
            except Exception as e:
                errors.append(f"{model_name}: {self._summarize_gemini_error(str(e))}")

        raise RuntimeError("All Gemini model attempts failed. " + " | ".join(errors))

    def _summarize_gemini_error(self, error_text: str) -> str:
        """Compress provider errors into user-friendly diagnostics."""
        err = (error_text or "").lower()

        if "resource_exhausted" in err or "quota" in err or "429" in err:
            return "Quota exceeded for this Gemini API key/project"
        if "not_found" in err or "model" in err and "not found" in err:
            return "Model unavailable for this API key/API version"
        if "permission_denied" in err or "403" in err:
            return "Permission denied for the selected model"
        if "unauthenticated" in err or "401" in err:
            return "Authentication failed for Gemini API"

        return "Gemini request failed"

    def _compute_trade_signal_scores(
        self,
        rsi: float,
        ma10: float,
        ma50: float,
        prediction: float,
        price_change_24h: float,
        risk_level: str
    ) -> Dict:
        """Compute normalized 0-100 scores used by frontend graph panels."""
        # Higher score = stronger support for entering now.
        if rsi >= 75:
            rsi_score = 20
        elif rsi >= 70:
            rsi_score = 30
        elif rsi <= 25:
            rsi_score = 45
        elif rsi <= 35:
            rsi_score = 60
        elif 45 <= rsi <= 60:
            rsi_score = 70
        else:
            rsi_score = 55

        ma_gap_pct = abs(ma10 - ma50) / ma50 * 100 if ma50 else 0
        if ma10 > ma50:
            trend_score = min(90, 60 + int(ma_gap_pct * 10))
        else:
            trend_score = max(15, 45 - int(ma_gap_pct * 10))

        momentum_score = int(max(10, min(90, prediction)))
        if price_change_24h >= 10:
            momentum_score = max(20, momentum_score - 15)
        elif price_change_24h <= -8:
            momentum_score = max(15, momentum_score - 10)

        risk_bias = {'low': -10, 'medium': 0, 'high': 10}.get(risk_level, 0)
        entry_score = int(max(0, min(100, (rsi_score * 0.25 + trend_score * 0.35 + momentum_score * 0.40) + risk_bias)))
        caution_score = int(max(0, min(100, 100 - entry_score + (10 if price_change_24h >= 7 or rsi >= 70 else 0))))

        return {
            'rsi_score': int(rsi_score),
            'trend_score': int(trend_score),
            'momentum_score': int(momentum_score),
            'entry_score': int(entry_score),
            'caution_score': int(caution_score)
        }

    def _analyze_recent_market_behavior(
        self,
        coin_id: str,
        coin_name: str,
        prices: List[float],
        current_price: float,
        price_change_24h: float,
        ma10: float,
        ma50: float
    ) -> Dict:
        """Build coin-specific recent behavior summary and concrete key events."""
        if not prices or len(prices) < 8:
            trend = "Sideways" if abs(price_change_24h) < 2 else ("Uptrend" if price_change_24h > 0 else "Downtrend")
            return {
                "market_summary": (
                    f"Limited recent history for {coin_name}. Current move is {price_change_24h:+.2f}% in 24h, "
                    "so treat this as an early signal and wait for confirmation candles."
                ),
                "key_events": [
                    f"Recent 24h move: {price_change_24h:+.2f}% at approximately ${current_price:,.4f}"
                ],
                "trend": trend,
                "volatility_level": "Medium"
            }

        recent30 = prices[-30:] if len(prices) >= 30 else prices[:]
        recent14 = prices[-14:] if len(prices) >= 14 else prices[:]
        recent7 = prices[-7:] if len(prices) >= 7 else prices[:]
        recent3 = prices[-3:] if len(prices) >= 3 else prices[:]

        last = recent30[-1]
        first30 = recent30[0]
        first7 = recent7[0]
        first3 = recent3[0]

        change30 = ((last - first30) / first30 * 100) if first30 else 0.0
        change7 = ((last - first7) / first7 * 100) if first7 else 0.0
        change3 = ((last - first3) / first3 * 100) if first3 else 0.0

        high30 = max(recent30)
        low30 = min(recent30)
        drawdown_from_high = ((last - high30) / high30 * 100) if high30 else 0.0
        rebound_from_low = ((last - low30) / low30 * 100) if low30 else 0.0

        returns = []
        for i in range(1, len(recent14)):
            prev = recent14[i - 1]
            if prev:
                returns.append((recent14[i] - prev) / prev)

        if returns:
            avg = sum(returns) / len(returns)
            variance = sum((r - avg) ** 2 for r in returns) / len(returns)
            daily_vol_pct = (variance ** 0.5) * 100
        else:
            daily_vol_pct = 0.0

        if daily_vol_pct >= 4.0:
            volatility_level = "High"
        elif daily_vol_pct >= 2.0:
            volatility_level = "Medium"
        else:
            volatility_level = "Low"

        if ma10 > ma50 and change7 > 3:
            trend = "Uptrend"
        elif ma10 < ma50 and change7 < -3:
            trend = "Downtrend"
        else:
            trend = "Sideways"

        near_support = last <= low30 * 1.06
        breakout_attempt = last >= high30 * 0.985 and change7 > 4
        recovering_after_drop = drawdown_from_high <= -10 and change3 > 2

        if recovering_after_drop:
            market_situation = (
                f"{coin_name} is recovering after a sharp pullback. It is still {abs(drawdown_from_high):.1f}% below its recent high "
                f"but has rebounded {change3:+.1f}% in the last 3 days."
            )
        elif trend == "Downtrend":
            market_situation = (
                f"{coin_name} remains in a downtrend with a {change7:+.1f}% move over the last week and weaker short-term structure. "
                "Sellers are still controlling timing."
            )
        elif near_support and abs(change7) < 4:
            market_situation = (
                f"{coin_name} is stabilizing near support after recent weakness, trading close to its 30-day lower range. "
                "Price action is calmer but confirmation is still needed."
            )
        elif breakout_attempt:
            market_situation = (
                f"{coin_name} is testing a breakout near its recent 30-day highs with improving weekly momentum. "
                "The move is promising but can fail if follow-through fades."
            )
        else:
            market_situation = (
                f"{coin_name} is in a mixed phase: {change7:+.1f}% over 7 days and {change30:+.1f}% over 30 days, "
                "with no fully clean trend continuation yet."
            )

        key_events = []
        if drawdown_from_high <= -8:
            key_events.append(f"Price is still {abs(drawdown_from_high):.1f}% below the 30-day high, showing recent downside pressure.")
        if rebound_from_low >= 6:
            key_events.append(f"Coin bounced {rebound_from_low:.1f}% from the 30-day low, signaling dip-buying interest.")
        if breakout_attempt:
            key_events.append("Price is pressing against the recent resistance zone (near 30-day highs), a potential breakout test.")
        if abs(change7) <= 2.5:
            key_events.append(f"Last 7 days are mostly sideways ({change7:+.1f}%), suggesting consolidation before the next move.")
        if abs(price_change_24h) >= 5:
            key_events.append(f"A strong 24h swing of {price_change_24h:+.1f}% indicates elevated short-term reaction risk.")

        if not key_events:
            key_events.append(
                f"No major shock event detected; {coin_name} is showing controlled movement with {volatility_level.lower()} volatility recently."
            )

        return {
            "market_summary": market_situation,
            "key_events": key_events,
            "trend": trend,
            "volatility_level": volatility_level
        }

    def _build_rule_based_trade_advice(
        self,
        coin_id: str,
        risk_level: str,
        rsi: float,
        ma10: float,
        ma50: float,
        prediction: float,
        price_change_24h: float,
        market_summary: str,
        key_events: List[str],
        trend: str,
        volatility_level: str,
        error: str = ""
    ) -> str:
        """Rule-based fallback returning the same compact format expected from the LLM."""
        bullish = ma10 > ma50
        overbought = rsi >= 70
        oversold = rsi <= 30
        ma_gap_pct = abs(ma10 - ma50) / ma50 * 100 if ma50 > 0 else 0
        strong_trend = ma_gap_pct >= 2.0
        big_drop = price_change_24h <= -5
        big_pump = price_change_24h >= 7

        coin_name = coin_id.replace('-', ' ').title()
        event_line = key_events[0] if key_events else f"{coin_name} is in a mixed phase with no dominant catalyst."

        if overbought and (big_pump or prediction < 55):
            decision = "AVOID" if risk_level in ("low", "medium") else "WAIT"
            confidence = "High"
            timing = "Late entry - price is stretched after recent upside and pullback risk is elevated."
            tip = "Wait for a pullback and confirmation candle before re-entering."
        elif not bullish and strong_trend and prediction < 50:
            decision = "AVOID" if risk_level != "high" else "WAIT"
            confidence = "High"
            timing = "Risky entry - trend remains down and recovery probability is not supportive yet."
            tip = "Do not average down; wait for trend structure to improve first."
        elif bullish and prediction >= 62 and not overbought and (risk_level in ("medium", "high")):
            decision = "BUY"
            confidence = "High" if strong_trend else "Medium"
            timing = "Good entry - momentum and trend are currently aligned."
            tip = "Start with a small size and place a strict stop-loss below recent support."
        elif oversold and prediction >= 58:
            decision = "BUY" if risk_level == "high" else "WAIT"
            confidence = "Medium"
            timing = "Early entry - rebound setup is forming but confirmation is still developing."
            tip = "Wait for a higher low on the short-term chart if you want safer timing."
        else:
            decision = "WAIT"
            confidence = "Medium"
            timing = "Risky entry - signal alignment is incomplete for a clean setup."
            tip = "Set alerts at support/resistance and enter only after confirmation."

        if decision == "BUY":
            trigger_condition = "Enter only if price holds above nearby support after a pullback, then prints a higher low."
        elif decision == "WAIT":
            trigger_condition = "Wait for a clean breakout above recent resistance with follow-through volume before entering."
        else:
            trigger_condition = "Avoid until downside pressure fades and price reclaims a key level with stability for at least 1-2 sessions."

        decision_reason_1 = f"Recent move {price_change_24h:+.1f}% combined with the latest structure suggests the market is in a {trend.lower()} transition phase."
        decision_reason_2 = f"Key event: {event_line} This changes timing risk for beginners who panic during volatility."
        decision_reason_3 = f"Prediction at {prediction:.0f}% supports a {decision.lower()} stance only if the trigger confirms price behavior."

        return (
            f"Decision: {decision}\n\n"
            "Market Story:\n"
            f"{market_summary}\n\n"
            "Why This Decision:\n"
            f"- {decision_reason_1}\n"
            f"- {decision_reason_2}\n"
            f"- {decision_reason_3}\n\n"
            "What To Watch (IMPORTANT):\n"
            f"{trigger_condition}\n\n"
            "Timing Insight:\n"
            f"{timing}\n\n"
            "Confidence:\n"
            f"{confidence}\n\n"
            "Beginner Tip:\n"
            f"{tip}"
        )
    
    def _get_user_profile(self, user_id: int) -> Dict:
        """Build comprehensive user profile for personalization"""
        conn = self.get_db()
        cursor = conn.cursor(dictionary=True)
        
        # Get learning profile
        cursor.execute("""
            SELECT * FROM learning_profiles WHERE user_id = %s
        """, (user_id,))
        profile = cursor.fetchone()
        
        if not profile:
            # Create new profile
            cursor.execute("""
                INSERT INTO learning_profiles (user_id) VALUES (%s)
            """, (user_id,))
            conn.commit()
            
            cursor.execute("""
                SELECT * FROM learning_profiles WHERE user_id = %s
            """, (user_id,))
            profile = cursor.fetchone()
        
        # Parse JSON fields
        profile['weak_areas'] = json.loads(profile.get('weak_areas') or '[]')
        profile['completed_lessons'] = json.loads(profile.get('completed_lessons') or '[]')
        profile['quiz_scores'] = json.loads(profile.get('quiz_scores') or '{}')
        
        cursor.close()
        conn.close()
        
        return profile
    
    def _search_knowledge(self, query: str, n_results: int = 3) -> List[Dict]:
        """Search ChromaDB for relevant content"""
        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=n_results
            )
            
            docs = []
            if results['documents'] and results['documents'][0]:
                for i in range(len(results['documents'][0])):
                    docs.append({
                        'id': results['ids'][0][i],
                        'content': results['documents'][0][i],
                        'metadata': results['metadatas'][0][i],
                        'distance': results['distances'][0][i] if 'distances' in results else 0
                    })
            
            return docs
            
        except Exception as e:
            print(f"Search error: {e}")
            return []
    
    def _build_prompt(self, question: str, user_profile: Dict, docs: List[Dict]) -> str:
        """Build personalized prompt with context"""
        
        # Format user context
        user_context = f"""
        USER PROFILE:
        - Skill Level: {user_profile['skill_level']}
        - Total Trades: {user_profile['total_trades']}
        - Win Rate: {user_profile['win_rate']}%
        - Uses Stop Loss: {user_profile['uses_stop_loss_percent']}% of trades
        - Average Leverage: {user_profile['avg_leverage_used']}x
        - Weak Areas: {', '.join(user_profile['weak_areas']) if user_profile['weak_areas'] else 'None identified'}
        - Biggest Mistake: {user_profile['biggest_mistake'] or 'Not yet identified'}
        """
        
        # Format retrieved knowledge
        knowledge_context = self._format_docs_for_prompt(docs)
        
        prompt = f"""
        CONTEXT FROM KNOWLEDGE BASE:
        {knowledge_context}
        
        {user_context}
        
        USER QUESTION:
        {question}
        
        INSTRUCTIONS:
        - Answer using the knowledge base content above
        - Personalize based on the user's profile (skill level, mistakes, weak areas)
        - Reference their specific trading stats when relevant
        - Use concrete examples from their experience level
        - Be encouraging but honest
        - If they're making the same mistake repeatedly, address it directly
        - Keep response under 500 words
        - Use formatting (bullets, bold) for readability
        
        Answer:
        """
        
        return prompt
    
    def _get_system_prompt(self, user_profile: Dict) -> str:
        """System prompt that sets Claude's behavior"""
        return f"""You are an expert crypto trading tutor for a SIMULATOR app helping beginners learn safely.

        CRITICAL RULES:
        1. This is a SIMULATOR with fake money - emphasize this
        2. NEVER give specific price predictions or financial advice
        3. Teach principles, not "hot tips"
        4. Personalize responses to user's skill level: {user_profile['skill_level']}
        5. Focus on risk management and psychology
        6. Be direct about mistakes but encouraging
        7. Use the user's actual trading data in examples
        8. Every answer should be slightly different (avoid templates)
        9. Challenge poor thinking patterns
        10. Celebrate good practices
        
        Your goal: Help them become disciplined traders, not gamblers.
        
        Tone: Friendly mentor who's seen every mistake before and genuinely wants them to succeed.
        """
    
    def _format_docs_for_prompt(self, docs: List[Dict]) -> str:
        """Format retrieved documents for inclusion in prompt"""
        if not docs:
            return "No specific knowledge found. Use general trading principles."
        
        formatted = []
        for i, doc in enumerate(docs, 1):
            formatted.append(f"""
            SOURCE {i} - {doc['metadata']['title']} ({doc['metadata']['category']}):
            {doc['content'][:1000]}...
            """)
        
        return "\n".join(formatted)
    
    def _split_content(self, content: str, chunk_size: int = 1000) -> List[str]:
        """Split long content into chunks for better retrieval"""
        # Simple split by paragraphs
        paragraphs = content.split('\n\n')
        chunks = []
        current_chunk = []
        current_size = 0
        
        for para in paragraphs:
            para_size = len(para)
            if current_size + para_size > chunk_size and current_chunk:
                chunks.append('\n\n'.join(current_chunk))
                current_chunk = [para]
                current_size = para_size
            else:
                current_chunk.append(para)
                current_size += para_size
        
        if current_chunk:
            chunks.append('\n\n'.join(current_chunk))
        
        return chunks if chunks else [content]
    
    def _extract_title(self, content: str) -> str:
        """Extract title from markdown"""
        lines = content.split('\n')
        for line in lines:
            if line.startswith('# '):
                return line.replace('# ', '').strip()
        return "Untitled"
    
    def _extract_difficulty(self, content: str) -> str:
        """Extract difficulty from markdown metadata"""
        if 'Beginner' in content[:500]:
            return 'beginner'
        elif 'Advanced' in content[:500]:
            return 'advanced'
        elif 'Intermediate' in content[:500]:
            return 'intermediate'
        return 'beginner'
    
    def _identify_mistake_type(self, trade: Dict, loss_pct: float) -> str:
        """Identify what went wrong with a trade"""
        # Simple heuristics - can be enhanced
        if abs(loss_pct) > 20:
            return 'no_stop_loss'
        elif trade.get('leverage', 1) > 5:
            return 'high_leverage'
        else:
            return 'poor_timing'
    
    def _log_indexed_document(self, doc_id: str, title: str, category: str, 
                             file_path: str, difficulty: str, word_count: int):
        """Log indexed document to database"""
        try:
            conn = self.get_db()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO knowledge_documents 
                (doc_id, title, category, file_path, difficulty, word_count, content_preview)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE 
                title=VALUES(title), updated_at=NOW()
            """, (doc_id, title, category, file_path, difficulty, word_count, title[:200]))
            
            conn.commit()
            cursor.close()
            conn.close()
        except Exception as e:
            print(f"Error logging document: {e}")
    
    def _log_conversation(self, user_id: int, session_id: str, question: str, 
                         response: str, docs_used: List[str], response_time: int,
                         user_skill: str):
        """Log AI conversation to database"""
        try:
            conn = self.get_db()
            cursor = conn.cursor()
            normalized_skill = (user_skill or "beginner").strip().lower()
            if normalized_skill not in ("beginner", "intermediate", "advanced"):
                normalized_skill = "beginner"
            
            cursor.execute("""
                INSERT INTO ai_conversations 
                (user_id, session_id, user_question, user_skill_level, 
                 retrieved_docs, ai_response, response_time_ms)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (user_id, session_id, question, normalized_skill, 
                  json.dumps(docs_used), response, response_time))
            
            conn.commit()
            cursor.close()
            conn.close()
        except Exception as e:
            print(f"Error logging conversation: {e}")
    
    def _log_trade_mistake(self, user_id: int, transaction_id: int, 
                          mistake_type: str, loss_amount: float, analysis: str):
        """Log identified trading mistake"""
        try:
            conn = self.get_db()
            cursor = conn.cursor()
            
            severity = 'severe' if abs(loss_amount) > 1000 else 'moderate' if abs(loss_amount) > 500 else 'minor'
            
            cursor.execute("""
                INSERT INTO trade_mistakes 
                (user_id, transaction_id, mistake_type, severity, loss_amount, ai_analysis)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (user_id, transaction_id, mistake_type, severity, abs(loss_amount), analysis))
            
            conn.commit()
            cursor.close()
            conn.close()
        except Exception as e:
            print(f"Error logging mistake: {e}")


# Utility function for Flask integration
def get_ai_assistant(db_connection, api_key: str = None, provider: str = "auto") -> AIAssistant:
    """Factory function to create AI assistant instance"""
    if not api_key:
        # Try Gemini first, then Claude
        api_key = os.getenv('GEMINI_API_KEY') or os.getenv('ANTHROPIC_API_KEY')
        
    if not api_key:
        raise ValueError("AI API key required. Set GEMINI_API_KEY or ANTHROPIC_API_KEY environment variable.")
    
    return AIAssistant(db_connection, api_key, provider)
