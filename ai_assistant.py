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
        BUY / WAIT / BUY WITH CAUTION decisions personalized to user's risk level.
        
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
        rsi = 50.0  # defaults
        ma10 = current_price
        ma50 = current_price
        prediction = 50.0
        
        try:
            # Fetch 60 days of data for MA50 calculation
            api_url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart?vs_currency=usd&days=60"
            resp = req.get(api_url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                prices = [p[1] for p in data.get('prices', [])]
                
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
        
        # 3. Search knowledge base for relevant trading context
        search_query = f"trading strategy {coin_id} risk management buy sell decision"
        relevant_docs = self._search_knowledge(search_query, n_results=2)
        knowledge_context = self._format_docs_for_prompt(relevant_docs)
        
        # 4. Build the trade advisor prompt — educational, coin-specific, beginner-focused
        coin_display = coin_id.replace("-", " ").title()
        rsi_zone = "overbought" if rsi >= 70 else ("oversold" if rsi <= 30 else "neutral")
        trend_word = "bullish (upward)" if ma10 > ma50 else "bearish (downward)"
        ma_gap_pct = abs(ma10 - ma50) / ma50 * 100 if ma50 > 0 else 0

        prompt = f"""You are CoinPrep's AI trading mentor. Your job is to TEACH beginner traders by explaining what each market signal means in plain English — not just what to do, but WHY.

=== TRADE SCENARIO ===
Coin: {coin_display} ({coin_id})
Current Price: ${current_price:,.4f}
24h Change: {price_change_24h:+.2f}%
RSI (14-period): {rsi:.1f} → Zone: {rsi_zone}
10-Day Moving Average: ${ma10:,.4f}
50-Day Moving Average: ${ma50:,.4f}
Trend Direction: {trend_word} (MA gap: {ma_gap_pct:.2f}%)
AI Price Prediction: {prediction:.1f}% chance price rises short-term
User Risk Level: {risk_level.upper()}

=== EDUCATIONAL KNOWLEDGE ===
{knowledge_context}

=== INSTRUCTIONS ===
1. Make a decision: BUY, WAIT, or BUY WITH CAUTION — based on ALL indicators AND the {risk_level} risk profile.
   - LOW risk: prefer WAIT unless signals are strongly aligned
   - MEDIUM risk: can enter with moderate signal alignment
   - HIGH risk: willing to enter on partial signals

2. For each reasoning point, explain the indicator using PLAIN ENGLISH with the actual numbers — imagine explaining to someone who has NEVER seen a chart. Use analogies. Make it specific to {coin_display}.
   - Do NOT say "RSI is 51". Instead say something like: "RSI of 51 means roughly equal buying and selling pressure — the market for {coin_display} isn't showing panic OR excitement right now."
   - Do NOT say "MA10 > MA50". Instead explain what this means in terms the beginner can understand.

3. Give a specific Risk Warning based on the actual current numbers.
4. Give ONE concrete actionable Beginner Tip — something the user can do RIGHT NOW.

IMPORTANT: This is a simulator with fake money. NOT financial advice.

Respond in this EXACT format:

Decision: <BUY / WAIT / BUY WITH CAUTION>

Confidence: <Low / Medium / High>

Key Reasoning:
- <Plain-English explanation of RSI {rsi:.1f} — what this number means for buyer vs seller pressure on {coin_display} right now>
- <Plain-English explanation of MA10 vs MA50 — what the {trend_word} trend and {ma_gap_pct:.2f}% gap tells us>
- <Plain-English explanation of prediction {prediction:.1f}% combined with {price_change_24h:+.2f}% 24h move — what short-term momentum looks like>

Why Consider Buying:
- <1-2 strongest bullish reasons based on current numbers>

Why Not Buy Yet:
- <1-2 strongest bearish/caution reasons based on current numbers>

Risk Warning:
- <Specific risk based on actual numbers: e.g. if RSI near 70 warn about reversal, if price surged 10%+ in 24h warn of correction, if prediction < 50% warn of downside>

Beginner Tip:
- <One concrete action: e.g. 'Set a stop-loss 5% below buy price', 'Wait for RSI to drop below 45', 'Start with 5% of your portfolio max'>"""
        
        # 5. Query AI
        ai_available = True
        ai_error = ""
        try:
            if self.provider == "claude":
                response = self.ai_client.messages.create(
                    model="claude-3-5-sonnet-20241022",
                    max_tokens=1024,
                    temperature=0.6,
                    system="You are an expert crypto trading mentor for a SIMULATOR app. Give clear, structured advice. Always follow the output format exactly.",
                    messages=[{"role": "user", "content": prompt}]
                )
                ai_response = response.content[0].text
                
            elif self.provider == "gemini":
                system_prompt = "You are an expert crypto trading mentor for a SIMULATOR app. Give clear, structured advice. Always follow the output format exactly."
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
                "trend": "Bullish" if ma10 > ma50 else "Bearish",
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
            "reasoning": [],
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
                if 'BUY WITH CAUTION' in decision:
                    parsed['decision'] = 'BUY WITH CAUTION'
                elif 'BUY' in decision and 'WAIT' not in decision:
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
                    
            # Section headers
            elif 'key reasoning' in line.lower():
                current_section = 'reasoning'
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
                elif current_section == 'why_buy':
                    parsed['why_buy'].append(content)
                elif current_section == 'why_not_buy':
                    parsed['why_not_buy'].append(content)
                elif current_section == 'risk_warning':
                    parsed['risk_warning'] = content if not parsed['risk_warning'] else parsed['risk_warning'] + ' ' + content
                elif current_section == 'beginner_tip':
                    parsed['beginner_tip'] = content if not parsed['beginner_tip'] else parsed['beginner_tip'] + ' ' + content
        
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

    def _build_rule_based_trade_advice(
        self,
        coin_id: str,
        risk_level: str,
        rsi: float,
        ma10: float,
        ma50: float,
        prediction: float,
        price_change_24h: float,
        error: str = ""
    ) -> str:
        """
        Fully dynamic rule-based trade analysis used when the LLM is unavailable.
        Performs real multi-signal technical analysis and generates coin-specific,
        beginner-friendly reasoning with 8+ distinct scenario branches.
        """
        bullish = ma10 > ma50
        overbought = rsi >= 70
        oversold = rsi <= 30
        rsi_neutral_high = 60 <= rsi < 70   # heating up but not extreme
        rsi_neutral_low = 30 < rsi < 45     # cooling down, recovering
        ma_gap_pct = abs(ma10 - ma50) / ma50 * 100 if ma50 > 0 else 0
        strong_trend = ma_gap_pct >= 2.0    # MA gap >= 2% is a meaningful trend
        big_drop = price_change_24h <= -5
        big_pump = price_change_24h >= 7
        positive_momentum = price_change_24h > 1

        # ── RSI explanation (always coin-specific and numeric) ──────────────────
        if overbought:
            rsi_explanation = (
                f"RSI is {rsi:.1f} — this is in 'overbought' territory (above 70). "
                "Think of it like a spring stretched too far: most buyers have already bought, "
                "which means fewer buyers remain to push the price higher. A pullback is likely."
            )
        elif oversold:
            rsi_explanation = (
                f"RSI is {rsi:.1f} — this is 'oversold' (below 30). "
                "It means selling pressure has been very heavy and the price may have dropped too far too fast. "
                "This can sometimes signal a bounce opportunity, but it can also mean the trend continues down."
            )
        elif rsi_neutral_high:
            rsi_explanation = (
                f"RSI is {rsi:.1f} — heating up but not yet overbought. "
                "Buyers have the upper hand right now, but the window to enter cleanly may be narrowing. "
                "If RSI crosses 70, the coin could be due for a cool-off."
            )
        elif rsi_neutral_low:
            rsi_explanation = (
                f"RSI is {rsi:.1f} — recovering from weak territory. "
                "The coin has lost some momentum recently but selling pressure is easing. "
                "This is a watchful zone — neither a clear buy nor sell signal."
            )
        else:
            rsi_explanation = (
                f"RSI is {rsi:.1f} — right in the neutral zone (between 45 and 60). "
                "This means buyers and sellers are roughly balanced right now. "
                "There's no extreme urgency to buy or sell — the coin is in a natural resting state."
            )

        # ── MA explanation (trend + strength) ──────────────────────────────────
        if bullish and strong_trend:
            ma_explanation = (
                f"The 10-day average price (${ma10:,.2f}) is {ma_gap_pct:.1f}% above the 50-day average (${ma50:,.2f}). "
                "This is a meaningful upward trend — like a car that's been accelerating faster than its usual speed. "
                "Short-term buyers are in control, which is a positive sign."
            )
        elif bullish and not strong_trend:
            ma_explanation = (
                f"The 10-day average (${ma10:,.2f}) is just slightly above the 50-day average (${ma50:,.2f}) "
                f"by {ma_gap_pct:.1f}%. That's a mild uptrend — like a flat road with a very gentle uphill slope. "
                "The bullish signal exists but it's not strong yet."
            )
        elif not bullish and strong_trend:
            ma_explanation = (
                f"The 10-day average (${ma10:,.2f}) is {ma_gap_pct:.1f}% below the 50-day average (${ma50:,.2f}). "
                "This is a clear downtrend — short-term price action is losing to the longer trend. "
                "Buying into a strong downtrend is risky for beginners."
            )
        else:
            ma_explanation = (
                f"The 10-day average (${ma10:,.2f}) is slightly below the 50-day average (${ma50:,.2f}) "
                f"by only {ma_gap_pct:.1f}%. This is a weak bearish signal — the trend hasn't fully turned down yet, "
                "but upward momentum is currently lacking."
            )

        # ── Momentum/Prediction explanation ────────────────────────────────────
        if big_pump:
            momentum_explanation = (
                f"The price surged {price_change_24h:+.1f}% in the last 24 hours. "
                f"Combined with a {prediction:.0f}% prediction of further increase, this looks exciting — "
                "but sharp run-ups often attract profit-takers, which can cause a sudden drop. "
                "Chasing a coin after a big pump is a classic beginner mistake called FOMO."
            )
        elif big_drop:
            momentum_explanation = (
                f"The price fell {price_change_24h:.1f}% in the last 24 hours — a significant drop. "
                f"The model gives a {prediction:.0f}% chance of a rebound. "
                "Sometimes big drops are opportunities, but they can also keep falling. "
                "This is a 'catching a falling knife' scenario — high risk."
            )
        elif positive_momentum and prediction >= 60:
            momentum_explanation = (
                f"Price is up {price_change_24h:+.1f}% in 24 hours with a {prediction:.0f}% predicted chance of further gains. "
                "Both signals point in the same direction. Momentum is building gradually — "
                "this is generally a healthier entry than chasing a sudden spike."
            )
        elif prediction >= 60:
            momentum_explanation = (
                f"Even though the 24h move is modest ({price_change_24h:+.1f}%), "
                f"the model assigns a {prediction:.0f}% chance of a short-term price increase. "
                "Quiet accumulation before a move is sometimes the best time to enter."
            )
        elif prediction < 45:
            momentum_explanation = (
                f"The model gives only a {prediction:.0f}% chance of a price increase — below 50%, which means "
                "the algorithm sees more risk than opportunity right now. "
                f"Combined with a {price_change_24h:+.1f}% 24h change, short-term momentum is weak."
            )
        else:
            momentum_explanation = (
                f"24h price change: {price_change_24h:+.1f}%, prediction: {prediction:.0f}%. "
                "These are mixed signals — not enough evidence to confidently predict direction. "
                "When signals conflict, doing nothing is a valid strategy."
            )

        # ── Decision logic with 8 branches ─────────────────────────────────────
        if overbought and big_pump:
            decision, confidence = "WAIT", "High"
            risk_warning = (
                f"The coin is overbought (RSI {rsi:.1f}) AND just pumped {price_change_24h:+.1f}% in 24h. "
                "Two classic 'overheated' signals together. Probability of a near-term correction is high."
            )
            tip = "Never buy a coin right after a big spike. Set a price alert for 5-8% lower and buy there instead."

        elif overbought:
            decision, confidence = "WAIT", "High"
            risk_warning = (
                f"RSI at {rsi:.1f} means most buyers have already entered. Overbought coins often pull back "
                "before continuing upward. Waiting for RSI to drop below 60 gives a much safer entry."
            )
            tip = f"Set a price alert when RSI drops below 60 — that's usually a cleaner entry point for {coin_id.title()}."

        elif oversold and bullish and prediction >= 60 and risk_level in ("medium", "high"):
            decision, confidence = "BUY WITH CAUTION", "Medium"
            risk_warning = (
                f"RSI {rsi:.1f} suggests the coin was heavily sold. Potential bounce setup, "
                "but oversold markets can stay oversold for a while. Use a tight stop-loss."
            )
            tip = "If you enter, size it small (no more than 5% of your portfolio) and set a stop-loss immediately."

        elif oversold and risk_level == "low":
            decision, confidence = "WAIT", "Medium"
            risk_warning = (
                f"Even though RSI {rsi:.1f} suggests a possible bounce, your LOW risk profile means "
                "you should wait for the bounce to begin BEFORE entering — don't try to catch the bottom."
            )
            tip = "Wait for RSI to climb above 40 and price to show 2+ green days before considering entry."

        elif bullish and strong_trend and not overbought and prediction >= 58:
            if risk_level == "high":
                decision, confidence = "BUY", "High"
            elif risk_level == "medium":
                decision, confidence = "BUY WITH CAUTION", "High"
            else:
                decision, confidence = "BUY WITH CAUTION", "Medium"
            risk_warning = (
                f"Trend and prediction are aligned positively. Main risk: if the MA gap ({ma_gap_pct:.1f}%) "
                "narrows quickly, the trend could be losing steam. Monitor daily."
            )
            tip = "Enter with a position no larger than 10% of your balance and set a stop-loss 5-7% below your buy price."

        elif bullish and not strong_trend and prediction >= 55 and not overbought:
            decision = "BUY WITH CAUTION" if risk_level != "low" else "WAIT"
            confidence = "Medium"
            risk_warning = (
                f"The bullish trend exists but is weak (MA gap: {ma_gap_pct:.1f}%). "
                "Weak trends can reverse easily. This is a 'maybe' not a strong signal."
            )
            tip = "Consider a 'test buy' with just 3-5% of your portfolio. If it goes well, add more later."

        elif not bullish and prediction >= 65 and rsi < 55:
            decision = "BUY WITH CAUTION" if risk_level == "high" else "WAIT"
            confidence = "Low"
            risk_warning = (
                f"The short-term trend is down (MA bearish), but the model thinks there's a {prediction:.0f}% "
                "chance of a recovery. Contradictory signals mean high uncertainty."
            )
            tip = "When trend and prediction contradict each other, wait for price action to confirm direction before entering."

        elif big_drop and prediction < 50:
            decision, confidence = "WAIT", "High"
            risk_warning = (
                f"Price dropped {price_change_24h:.1f}% and the model shows {prediction:.0f}% confidence of recovery — "
                "below 50%. Buying into a falling coin without confirmation is risky for any risk level."
            )
            tip = "Look for the price to stabilize (2-3 flat/green days) before considering entry after a big drop."

        else:
            decision, confidence = "WAIT", "Medium"
            risk_warning = (
                "Current signals are mixed or weak. No strong entry signal exists right now. "
                "In trading, missing a trade is always better than taking a bad trade."
            )
            tip = "Use this time to study the coin's chart. Set a price alert for a level where signals improve."

        return (
            f"Decision: {decision}\n\n"
            f"Confidence: {confidence}\n\n"
            "Key Reasoning:\n"
            f"- {rsi_explanation}\n"
            f"- {ma_explanation}\n"
            f"- {momentum_explanation}\n"
            "\nWhy Consider Buying:\n"
            f"- {'Trend and momentum are aligned to the upside.' if bullish and prediction >= 55 else 'There is at least partial support for recovery if risk is managed carefully.'}\n"
            f"- {'Prediction is above coin-flip odds, suggesting buyers still have a chance.' if prediction >= 50 else 'If you are aggressive, this could still be watched as a potential setup after confirmation.'}\n"
            "\nWhy Not Buy Yet:\n"
            f"- {'RSI is elevated, which increases pullback risk.' if overbought else 'Signal alignment is not fully strong, so timing risk remains.'}\n"
            f"- {'Recent price movement is too sharp, which can trap late entries.' if big_pump or big_drop else 'Without confirmation candles, entering now can still be premature.'}\n"
            "\nRisk Warning:\n"
            f"- {risk_warning}\n"
            "\nBeginner Tip:\n"
            f"- {tip}"
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
