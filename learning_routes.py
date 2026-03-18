"""
Learning Mode Routes for AI-Powered Trading Simulator
Handles lessons, AI tutor, quizzes, and progress tracking
"""

from flask import Blueprint, request, jsonify, render_template, session
from functools import wraps
import json
from datetime import datetime
import os
from pathlib import Path
import re
from risk_assessment_data import get_trade_advisor_prompt, get_trade_mistake_analyzer_prompt

# Will be initialized in app.py
ai_assistant = None
user_profiler = None

learning_bp = Blueprint('learning', __name__, url_prefix='/learning')


def login_required(f):
    """Decorator to require login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Not logged in'}), 401
        return f(*args, **kwargs)
    return decorated_function


def _parse_trade_mistake_response(text):
    """Extract structured fields from the AI's formatted response."""
    parsed = {
        'mistake_type': '',
        'confidence_score': '',
        'explanation': '',
        'what_went_well': '',
        'what_went_wrong': '',
        'improvement_tip': ''
        ,
        'action_plan': []
    }

    if not text:
        return parsed

    # Remove safety disclaimer block if present.
    clean_text = text.split('⚠️ IMPORTANT DISCLAIMER:')[0].strip()
    if not clean_text:
        clean_text = text.strip()

    for raw_line in clean_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        # Allow either "- Field:" or "Field:" formats.
        if line.startswith('-'):
            line = line[1:].strip()

        lower = line.lower()
        if lower.startswith('mistake type:'):
            parsed['mistake_type'] = line.split(':', 1)[1].strip()
        elif lower.startswith('confidence score:'):
            parsed['confidence_score'] = line.split(':', 1)[1].strip()
        elif lower.startswith('explanation:'):
            parsed['explanation'] = line.split(':', 1)[1].strip()
        elif lower.startswith('what went well:'):
            parsed['what_went_well'] = line.split(':', 1)[1].strip()
        elif lower.startswith('what went wrong:'):
            parsed['what_went_wrong'] = line.split(':', 1)[1].strip()
        elif lower.startswith('improvement tip:'):
            parsed['improvement_tip'] = line.split(':', 1)[1].strip()
        elif lower.startswith('action plan:'):
            continue
        elif (raw_line.strip().startswith('- ') or raw_line.strip().startswith('• ')) and parsed['improvement_tip']:
            parsed['action_plan'].append(raw_line.strip()[2:].strip())

    # Fallback: if format was not strictly followed, still show useful output.
    if not parsed['explanation']:
        parsed['explanation'] = clean_text.strip()

    return parsed


def _compute_trade_quality_metrics(trade_inputs):
    """Compute 0-100 quality metrics for post-trade graphing."""
    buy_price = _extract_numeric(trade_inputs.get('buy_price')) or 0.0
    sell_price = _extract_numeric(trade_inputs.get('sell_price')) or 0.0
    buy_rsi = _extract_numeric(trade_inputs.get('buy_rsi'))
    sell_rsi = _extract_numeric(trade_inputs.get('sell_rsi'))
    minutes = _extract_numeric(trade_inputs.get('minutes'))

    pnl_pct = ((sell_price - buy_price) / buy_price) * 100 if buy_price > 0 else 0.0

    # Entry timing: best in neutral zones, weaker at extremes.
    if buy_rsi is None:
        entry_timing = 55
    elif 40 <= buy_rsi <= 60:
        entry_timing = 78
    elif 30 <= buy_rsi < 40 or 60 < buy_rsi <= 70:
        entry_timing = 62
    else:
        entry_timing = 40

    # Exit discipline: profitable + not panic-fast exits score better.
    if minutes is None:
        minutes = 30
    exit_discipline = 55
    if pnl_pct > 0:
        exit_discipline += 20
    elif pnl_pct < -2:
        exit_discipline -= 15
    if minutes < 15 and pnl_pct < 0:
        exit_discipline -= 15
    exit_discipline = max(20, min(95, int(exit_discipline)))

    # Risk management: penalize deeper losses.
    risk_management = 75
    if pnl_pct <= -5:
        risk_management = 35
    elif pnl_pct <= -3:
        risk_management = 48
    elif pnl_pct < 0:
        risk_management = 60
    elif pnl_pct > 2:
        risk_management = 80

    # Emotional control: short losing exits and extreme RSI entries lower score.
    emotional = 70
    if minutes < 20 and pnl_pct < 0:
        emotional -= 25
    if buy_rsi is not None and (buy_rsi >= 70 or buy_rsi <= 25):
        emotional -= 10
    emotional = max(20, min(95, int(emotional)))

    overall = int((entry_timing + exit_discipline + risk_management + emotional) / 4)

    return {
        'entry_timing': int(entry_timing),
        'exit_discipline': int(exit_discipline),
        'risk_management': int(risk_management),
        'emotional_control': int(emotional),
        'overall': int(overall)
    }


def _looks_like_ai_provider_error(text):
    """Detect provider/runtime failures returned as plain text responses."""
    if not text:
        return True

    err = text.lower()
    indicators = [
        'i encountered an error',
        'all gemini model attempts failed',
        'model unavailable',
        'quota exceeded',
        'permission denied',
        'authentication failed',
        'provider unavailable',
        'request failed',
    ]
    return any(token in err for token in indicators)


def _extract_numeric(value):
    """Extract the first numeric token from mixed strings like '+1.25 USD'."""
    if isinstance(value, (int, float)):
        return float(value)
    if value is None:
        return None

    match = re.search(r'-?\d+(?:\.\d+)?', str(value))
    return float(match.group(0)) if match else None


def _build_rule_based_trade_mistake(trade_inputs):
    """Generate a constructive fallback analysis when AI provider is unavailable."""
    buy_price = _extract_numeric(trade_inputs.get('buy_price')) or 0.0
    sell_price = _extract_numeric(trade_inputs.get('sell_price')) or 0.0
    buy_rsi = _extract_numeric(trade_inputs.get('buy_rsi'))
    sell_rsi = _extract_numeric(trade_inputs.get('sell_rsi'))
    minutes = _extract_numeric(trade_inputs.get('minutes'))
    pnl_abs = _extract_numeric(trade_inputs.get('profit_loss'))

    pnl_pct = 0.0
    if buy_price > 0:
        pnl_pct = ((sell_price - buy_price) / buy_price) * 100
    elif pnl_abs is not None:
        pnl_pct = pnl_abs

    pnl_negative = (pnl_abs is not None and pnl_abs < 0) or pnl_pct < 0

    mistake_type = 'Good Trade'
    explanation = 'Your trade shows a reasonable decision process based on the available data.'
    tip = 'Keep following a plan with clear entry, exit, and risk limits.'

    # Priority-based classification from strongest signals to weakest.
    if buy_rsi is not None and buy_rsi >= 70 and pnl_negative:
        mistake_type = 'FOMO Buying'
        explanation = (
            f'You entered when RSI was high ({buy_rsi:.1f}), which often means the price was already overheated. '
            f'The trade then moved against you ({pnl_pct:.2f}%).'
        )
        went_wrong = 'Entry happened when momentum was already stretched, so upside was limited and reversal risk was high.'
        went_well = 'You completed the trade and can now review it objectively instead of ignoring the loss.'
        tip = 'Wait for pullbacks or confirmation before buying after sharp moves.'
    elif pnl_negative and minutes is not None and minutes <= 20:
        mistake_type = 'Panic Selling'
        explanation = (
            f'You exited quickly after entry ({int(minutes)} minutes) with a loss ({pnl_pct:.2f}%), '
            'which suggests an emotion-driven exit instead of a planned one.'
        )
        went_wrong = 'The exit looked reactive rather than rule-based, which usually locks in avoidable losses.'
        went_well = 'You contained risk by closing instead of averaging down emotionally.'
        tip = 'Set your stop-loss and target before entering so you do not react emotionally.'
    elif minutes is not None and minutes <= 10 and abs(pnl_pct) <= 1.5:
        mistake_type = 'Overtrading'
        explanation = (
            f'The holding time was very short ({int(minutes)} minutes) with small movement ({pnl_pct:.2f}%). '
            'Frequent quick trades can increase mistakes and fees.'
        )
        went_wrong = 'Trade duration was too short for the setup to develop, making the decision mostly noise-driven.'
        went_well = 'Position sizing appears contained, so the loss impact stayed manageable.'
        tip = 'Trade less often and only when your setup is clearly valid.'
    elif pnl_pct <= -3:
        mistake_type = 'No Stop Loss'
        explanation = (
            f'This trade ended with a larger loss ({pnl_pct:.2f}%). '
            'A predefined stop-loss could have limited downside risk.'
        )
        went_wrong = 'Loss size suggests risk limits were not predefined or not respected during the trade.'
        went_well = 'You closed the position and prevented the loss from growing further.'
        tip = 'Place a stop-loss at entry and cap risk per trade to 1-2% of capital.'
    elif pnl_negative:
        mistake_type = 'Panic Selling'
        explanation = (
            f'This trade closed in loss ({pnl_pct:.2f}%). '
            'Without a strong rule-based exit, small losses are often caused by reactive decisions.'
        )
        went_wrong = 'The trade lacked a clearly documented invalidation rule before entry.'
        went_well = 'Loss remained relatively small, which gives room to improve without major damage.'
        tip = 'Before entering, define your invalidation level and exit only if that rule is hit.'
    elif pnl_pct >= 1:
        mistake_type = 'Good Trade'
        explanation = (
            f'You closed the trade with a positive result ({pnl_pct:.2f}%). '
            'That indicates decent entry/exit discipline for this setup.'
        )
        went_wrong = 'No major behavioral mistake detected in this trade sample.'
        went_well = 'You followed through and captured gains without obvious emotional overreaction.'
        tip = 'Keep journaling why this trade worked so you can repeat good habits.'

    if 'went_well' not in locals():
        went_well = 'You completed and reviewed the trade, which is a strong learning behavior.'
    if 'went_wrong' not in locals():
        went_wrong = 'Signal quality was mixed, so entry/exit clarity could be improved.'

    metrics = _compute_trade_quality_metrics(trade_inputs)
    confidence_score = max(55, min(92, metrics['overall']))

    action_plan = [
        'Write entry, stop-loss, and take-profit before placing the next order.',
        'Limit one-trade risk to 1-2% of account value.',
        'Review this trade after 24 hours and compare plan vs execution.'
    ]

    analysis = (
        f"- Mistake Type: {mistake_type}\n"
        f"- Confidence Score: {confidence_score}\n"
        f"- Explanation: {explanation}\n"
        f"- What Went Well: {went_well}\n"
        f"- What Went Wrong: {went_wrong}\n"
        f"- Improvement Tip: {tip}"
        "\n- Action Plan:\n"
        f"  - {action_plan[0]}\n"
        f"  - {action_plan[1]}\n"
        f"  - {action_plan[2]}"
    )

    return {
        'analysis': analysis,
        'parsed': {
            'mistake_type': mistake_type,
            'confidence_score': str(confidence_score),
            'explanation': explanation,
            'what_went_well': went_well,
            'what_went_wrong': went_wrong,
            'improvement_tip': tip,
            'action_plan': action_plan,
        }
    }


def _load_completed_trade_data(user_id, transaction_id):
    """Load a completed sell trade and derive analysis fields."""
    from app import get_db_connection

    conn = get_db_connection()
    if conn is None:
        raise ValueError('Database connection failed')

    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT
                s.id,
                s.coin_id,
                s.amount,
                s.price AS buy_price,
                s.sold_price,
                s.timestamp AS sold_at,
                s.buy_transaction_id,
                b.timestamp AS bought_at
            FROM transactions s
            LEFT JOIN transactions b
              ON b.id = s.buy_transaction_id
             AND b.user_id = s.user_id
            WHERE s.id = %s
              AND s.user_id = %s
              AND s.type = 'sell'
            LIMIT 1
            """,
            (transaction_id, user_id)
        )
        trade = cursor.fetchone()
    finally:
        cursor.close()
        conn.close()

    if not trade:
        raise ValueError('Completed sell trade not found for this user')

    buy_price = float(trade.get('buy_price') or 0)
    sell_price = float(trade.get('sold_price') or 0)
    amount = float(trade.get('amount') or 0)
    profit_loss_value = round((sell_price - buy_price) * amount, 2)

    bought_at = trade.get('bought_at')
    sold_at = trade.get('sold_at')
    if bought_at and sold_at:
        holding_minutes = max(int((sold_at - bought_at).total_seconds() // 60), 0)
    else:
        holding_minutes = 'Unknown'

    return {
        'coin_id': str(trade.get('coin_id', '')).lower(),
        'coin': str(trade.get('coin_id', '')).upper(),
        'buy_price': buy_price,
        'sell_price': sell_price,
        'buy_rsi': 'N/A',
        'sell_rsi': 'N/A',
        'minutes': holding_minutes,
        'profit_loss': f"{profit_loss_value:+.2f} USD"
    }


# ==================== MAIN PAGES ====================

@learning_bp.route('/hub')
@login_required
def learning_hub():
    """Main learning hub page"""
    return render_template('learning_hub.html')


@learning_bp.route('/ai-tutor')
@login_required
def ai_tutor_page():
    """AI tutor chat interface"""
    return render_template('ai_tutor.html')


# ==================== AI TUTOR ENDPOINTS ====================

@learning_bp.route('/api/ask', methods=['POST'])
@login_required
def ask_ai():
    """
    Ask the AI tutor a question
    
    Body: {
        "question": "Why did my trade fail?",
        "session_id": "optional_session_id"
    }
    """
    try:
        data = request.get_json()
        question = data.get('question', '').strip()
        session_id = data.get('session_id')
        
        if not question:
            return jsonify({'error': 'Question required'}), 400
        
        if len(question) > 500:
            return jsonify({'error': 'Question too long (max 500 chars)'}), 400
        
        # Query AI assistant
        result = ai_assistant.query(
            user_id=session['user_id'],
            question=question,
            session_id=session_id
        )
        
        return jsonify({
            'success': True,
            'response': result['response'],
            'sources': result['sources'],
            'user_level': result['user_level'],
            'response_time': result['response_time_ms']
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@learning_bp.route('/api/analyze-trade/<int:transaction_id>', methods=['POST'])
@login_required
def analyze_trade(transaction_id):
    """
    Get AI analysis of a specific trade (usually a losing trade)
    """
    try:
        analysis = ai_assistant.analyze_trade_mistake(
            user_id=session['user_id'],
            transaction_id=transaction_id
        )
        
        return jsonify({
            'success': True,
            'analysis': analysis
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@learning_bp.route('/api/trade-advisor', methods=['POST'])
@login_required
def trade_advisor():
    """Generate AI pre-trade advice before user confirms buy/sell."""
    try:
        data = request.get_json() or {}

        coin = str(data.get('coin', '')).strip().upper()
        current_price = data.get('current_price')
        rsi = data.get('rsi')
        ma10 = data.get('ma10')
        ma50 = data.get('ma50')
        prediction = data.get('prediction')

        required_fields = [coin, current_price, rsi, ma10, ma50, prediction]
        if any(value in [None, ''] for value in required_fields):
            return jsonify({
                'error': 'Missing required fields: coin, current_price, rsi, ma10, ma50, prediction'
            }), 400

        # Fetch user risk level from DB, fallback to medium if missing.
        from app import get_db_connection
        conn = get_db_connection()
        if conn is None:
            return jsonify({'error': 'Database connection failed'}), 500

        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT risk_tolerance FROM users WHERE id = %s", (session['user_id'],))
        user = cursor.fetchone() or {}
        risk_level = (user.get('risk_tolerance') or 'medium').lower()

        cursor.close()
        conn.close()

        prompt = get_trade_advisor_prompt(
            risk_level=risk_level,
            coin=coin,
            current_price=current_price,
            rsi=rsi,
            ma10=ma10,
            ma50=ma50,
            prediction=prediction
        )

        result = ai_assistant.query(
            user_id=session['user_id'],
            question=prompt,
            session_id=f"trade_advisor_{session['user_id']}"
        )

        return jsonify({
            'success': True,
            'advice': result.get('response', ''),
            'sources': result.get('sources', []),
            'response_time': result.get('response_time_ms')
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@learning_bp.route('/api/trade-mistake-analyzer', methods=['POST'])
@login_required
def trade_mistake_analyzer():
    """Generate AI post-trade mistake analysis after a trade is completed."""
    try:
        if ai_assistant is None:
            return jsonify({'error': 'AI assistant is not initialized'}), 503

        data = request.get_json() or {}

        # Preferred mode: pass transaction_id and let backend derive details.
        transaction_id = data.get('transaction_id')
        if transaction_id not in [None, '']:
            try:
                transaction_id = int(transaction_id)
            except (TypeError, ValueError):
                return jsonify({'error': 'transaction_id must be an integer'}), 400

            try:
                trade_inputs = _load_completed_trade_data(session['user_id'], transaction_id)
            except ValueError as exc:
                return jsonify({'error': str(exc)}), 400
        else:
            # Fallback mode: explicit payload.
            trade_inputs = {
                'coin': str(data.get('coin', '')).strip().upper(),
                'buy_price': data.get('buy_price'),
                'sell_price': data.get('sell_price'),
                'buy_rsi': data.get('buy_rsi', 'N/A'),
                'sell_rsi': data.get('sell_rsi', 'N/A'),
                'minutes': data.get('minutes', 'Unknown'),
                'profit_loss': data.get('profit_loss')
            }

            required_fields = [
                trade_inputs['coin'],
                trade_inputs['buy_price'],
                trade_inputs['sell_price'],
                trade_inputs['profit_loss']
            ]
            if any(value in [None, ''] for value in required_fields):
                return jsonify({
                    'error': 'Missing required fields: coin, buy_price, sell_price, profit_loss (or use transaction_id)'
                }), 400

        prompt = get_trade_mistake_analyzer_prompt(
            coin=trade_inputs['coin'],
            buy_price=trade_inputs['buy_price'],
            sell_price=trade_inputs['sell_price'],
            buy_rsi=trade_inputs['buy_rsi'],
            sell_rsi=trade_inputs['sell_rsi'],
            holding_minutes=trade_inputs['minutes'],
            profit_loss=trade_inputs['profit_loss'],
        )

        result = ai_assistant.query(
            user_id=session['user_id'],
            question=prompt,
            session_id=f"trade_mistake_{session['user_id']}"
        )

        analysis_text = result.get('response', '')

        # If provider call failed, return deterministic local analysis instead of raw errors.
        if _looks_like_ai_provider_error(analysis_text):
            fallback = _build_rule_based_trade_mistake(trade_inputs)
            analysis_text = fallback['analysis']
            parsed = fallback['parsed']
        else:
            parsed = _parse_trade_mistake_response(analysis_text)

        metrics = _compute_trade_quality_metrics(trade_inputs)

        return jsonify({
            'success': True,
            'analysis': analysis_text,
            'parsed': parsed,
            'trade_details': trade_inputs,
            'metrics': metrics,
            'sources': result.get('sources', []),
            'response_time': result.get('response_time_ms'),
            'response_time_ms': result.get('response_time_ms')
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@learning_bp.route('/api/conversation-history')
@login_required
def get_conversation_history():
    """Get recent AI conversations for this user"""
    try:
        from app import get_db_connection
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT 
                id, user_question, ai_response, created_at, user_rating
            FROM ai_conversations
            WHERE user_id = %s
            ORDER BY created_at DESC
            LIMIT 20
        """, (session['user_id'],))
        
        history = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        # Format dates
        for item in history:
            item['created_at'] = item['created_at'].isoformat()
        
        return jsonify({
            'success': True,
            'history': history
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@learning_bp.route('/api/rate-response/<int:conversation_id>', methods=['POST'])
@login_required
def rate_response(conversation_id):
    """
    Rate an AI response (1-5 stars)
    
    Body: {
        "rating": 4,
        "feedback": "Very helpful!"
    }
    """
    try:
        data = request.get_json()
        rating = data.get('rating')
        feedback = data.get('feedback', '')
        
        if not rating or rating < 1 or rating > 5:
            return jsonify({'error': 'Rating must be 1-5'}), 400
        
        from app import get_db_connection
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE ai_conversations
            SET user_rating = %s, user_feedback = %s
            WHERE id = %s AND user_id = %s
        """, (rating, feedback, conversation_id, session['user_id']))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ==================== USER PROFILE & PROGRESS ====================

@learning_bp.route('/api/profile')
@login_required
def get_profile():
    """Get user's learning profile and stats"""
    try:
        # Update profile with latest trade data
        profile = user_profiler.update_profile(session['user_id'])
        
        # Get recommendations
        recommendations = user_profiler.get_learning_recommendations(session['user_id'])
        
        return jsonify({
            'success': True,
            'profile': profile,
            'recommendations': recommendations
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@learning_bp.route('/api/progress')
@login_required
def get_progress():
    """Get all learning progress for user"""
    try:
        from app import get_db_connection
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT * FROM learning_progress
            WHERE user_id = %s
            ORDER BY updated_at DESC
        """, (session['user_id'],))
        
        progress = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        # Format dates
        for item in progress:
            item['created_at'] = item['created_at'].isoformat()
            item['updated_at'] = item['updated_at'].isoformat()
            if item['completed_at']:
                item['completed_at'] = item['completed_at'].isoformat()
        
        return jsonify({
            'success': True,
            'progress': progress
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@learning_bp.route('/api/track-progress', methods=['POST'])
@login_required
def track_progress():
    """
    Track learning activity
    
    Body: {
        "content_id": "stop_loss_guide",
        "content_type": "lesson",
        "time_spent": 120,  // seconds
        "score": 85  // optional, for quizzes
    }
    """
    try:
        data = request.get_json()
        
        success = user_profiler.track_learning_progress(
            user_id=session['user_id'],
            content_id=data['content_id'],
            content_type=data['content_type'],
            time_spent=data.get('time_spent', 0),
            score=data.get('score')
        )
        
        return jsonify({'success': success})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ==================== LESSONS & CONTENT ====================

@learning_bp.route('/api/lessons')
@login_required
def get_lessons():
    """Get available lessons organized by category"""
    try:
        knowledge_path = Path('./knowledge')
        
        lessons = {
            'crypto_basics': [],
            'risk_management': [],
            'trading_strategies': [],
            'psychology': [],
            'case_studies': []
        }
        
        # Map folders to categories
        folder_map = {
            'lessons': ['crypto_basics', 'risk_management'],
            'strategies': ['trading_strategies'],
            'psychology': ['psychology'],
            'case_studies': ['case_studies']
        }
        
        for folder, categories in folder_map.items():
            folder_path = knowledge_path / folder
            if folder_path.exists():
                for md_file in folder_path.glob('*.md'):
                    # Read first few lines for metadata
                    with open(md_file, 'r', encoding='utf-8') as f:
                        content = f.read(500)
                    
                    lesson_info = {
                        'id': md_file.stem,
                        'title': _extract_title(content),
                        'difficulty': _extract_difficulty(content),
                        'file_path': str(md_file),
                        'category': folder
                    }
                    
                    # Add to appropriate category
                    if folder == 'lessons' and 'stop' in md_file.stem.lower():
                        lessons['risk_management'].append(lesson_info)
                    elif folder == 'lessons':
                        lessons['crypto_basics'].append(lesson_info)
                    else:
                        for cat in categories:
                            lessons[cat].append(lesson_info)
        
        return jsonify({
            'success': True,
            'lessons': lessons
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@learning_bp.route('/api/lesson/<lesson_id>')
@login_required
def get_lesson_content(lesson_id):
    """Get full content of a specific lesson"""
    try:
        # Find the file
        knowledge_path = Path('./knowledge')
        md_file = None
        
        for file in knowledge_path.rglob('*.md'):
            if file.stem == lesson_id:
                md_file = file
                break
        
        if not md_file or not md_file.exists():
            return jsonify({'error': 'Lesson not found'}), 404
        
        with open(md_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        return jsonify({
            'success': True,
            'content': content,
            'title': _extract_title(content),
            'category': md_file.parent.name
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ==================== DAILY CHALLENGES ====================

@learning_bp.route('/api/daily-challenge')
@login_required
def get_daily_challenge():
    """Get today's personalized challenge"""
    try:
        from app import get_db_connection
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Check if challenge exists for today
        cursor.execute("""
            SELECT * FROM daily_challenges
            WHERE user_id = %s 
            AND challenge_date = CURDATE()
            AND expires_at > NOW()
        """, (session['user_id'],))
        
        challenge = cursor.fetchone()
        
        if not challenge:
            # Generate new challenge
            challenge_data = ai_assistant.generate_daily_challenge(session['user_id'])
            
            cursor.execute("""
                SELECT * FROM daily_challenges
                WHERE user_id = %s 
                AND challenge_date = CURDATE()
            """, (session['user_id'],))
            
            challenge = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if challenge:
            challenge['created_at'] = challenge['created_at'].isoformat()
            challenge['expires_at'] = challenge['expires_at'].isoformat()
            if challenge['completed_at']:
                challenge['completed_at'] = challenge['completed_at'].isoformat()
        
        return jsonify({
            'success': True,
            'challenge': challenge
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@learning_bp.route('/api/complete-challenge/<int:challenge_id>', methods=['POST'])
@login_required
def complete_challenge(challenge_id):
    """Mark challenge as completed and award crypto bucks"""
    try:
        from app import get_db_connection
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Get challenge
        cursor.execute("""
            SELECT * FROM daily_challenges
            WHERE id = %s AND user_id = %s AND completed = 0
        """, (challenge_id, session['user_id']))
        
        challenge = cursor.fetchone()
        
        if not challenge:
            return jsonify({'error': 'Challenge not found or already completed'}), 404
        
        # Mark complete
        cursor.execute("""
            UPDATE daily_challenges
            SET completed = 1, completed_at = NOW()
            WHERE id = %s
        """, (challenge_id,))
        
        # Award crypto bucks
        cursor.execute("""
            UPDATE users
            SET crypto_bucks = crypto_bucks + %s
            WHERE id = %s
        """, (challenge['reward_crypto_bucks'], session['user_id']))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'reward': float(challenge['reward_crypto_bucks'])
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ==================== QUIZ SYSTEM ====================

@learning_bp.route('/api/quiz/<quiz_id>')
@login_required
def get_quiz(quiz_id):
    """Get quiz questions"""
    # Simple quiz system - expand as needed
    quizzes = {
        'crypto_basics': {
            'title': 'Crypto Basics Quiz',
            'questions': [
                {
                    'id': 1,
                    'question': 'What makes cryptocurrency different from traditional money?',
                    'options': [
                        'It\'s digital only',
                        'No central authority controls it',
                        'Uses blockchain technology',
                        'All of the above'
                    ],
                    'correct': 3
                },
                {
                    'id': 2,
                    'question': 'What is the best way to learn crypto trading?',
                    'options': [
                        'Jump in with real money',
                        'Follow influencers on social media',
                        'Practice in a simulator first',
                        'Copy other traders'
                    ],
                    'correct': 2
                }
            ]
        },
        'stop_loss': {
            'title': 'Stop Loss Mastery Quiz',
            'questions': [
                {
                    'id': 1,
                    'question': 'What is the recommended maximum risk per trade for beginners?',
                    'options': ['1-2%', '5-10%', '20%', 'All in!'],
                    'correct': 0
                },
                {
                    'id': 2,
                    'question': 'When should you move your stop loss?',
                    'options': [
                        'When price approaches it',
                        'Only upward to lock profits',
                        'Never',
                        'When you feel like it'
                    ],
                    'correct': 1
                }
            ]
        }
    }
    
    quiz = quizzes.get(quiz_id)
    
    if not quiz:
        return jsonify({'error': 'Quiz not found'}), 404
    
    return jsonify({
        'success': True,
        'quiz': quiz
    })


@learning_bp.route('/api/submit-quiz', methods=['POST'])
@login_required
def submit_quiz():
    """
    Submit quiz answers
    
    Body: {
        "quiz_id": "crypto_basics",
        "answers": [3, 2],
        "time_spent": 120
    }
    """
    try:
        data = request.get_json()
        quiz_id = data['quiz_id']
        answers = data['answers']
        time_spent = data.get('time_spent', 0)
        
        # Get correct answers (simplified - should validate from quiz data)
        # For now, just calculate score
        total_questions = len(answers)
        # You'd compare with actual correct answers here
        score = 80  # Placeholder
        
        # Track progress
        user_profiler.track_learning_progress(
            user_id=session['user_id'],
            content_id=quiz_id,
            content_type='quiz',
            time_spent=time_spent,
            score=score
        )
        
        return jsonify({
            'success': True,
            'score': score,
            'passed': score >= 70
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ==================== ADMIN/SETUP ENDPOINTS ====================

@learning_bp.route('/api/index-knowledge', methods=['POST'])
def index_knowledge():
    """Index all knowledge base content (admin only - add auth in production)"""
    try:
        result = ai_assistant.index_knowledge_base()
        return jsonify({
            'success': True,
            'result': result
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ==================== HELPER FUNCTIONS ====================

def _extract_title(content: str) -> str:
    """Extract title from markdown"""
    lines = content.split('\n')
    for line in lines:
        if line.startswith('# '):
            return line.replace('# ', '').strip()
    return "Untitled"


def _extract_difficulty(content: str) -> str:
    """Extract difficulty from markdown"""
    if 'Beginner' in content[:500]:
        return 'beginner'
    elif 'Advanced' in content[:500]:
        return 'advanced'
    elif 'Intermediate' in content[:500]:
        return 'intermediate'
    return 'beginner'


# Initialize function (called from app.py)
def init_learning_system(assistant, profiler):
    """Initialize the learning system with AI assistant and profiler"""
    global ai_assistant, user_profiler
    ai_assistant = assistant
    user_profiler = profiler
