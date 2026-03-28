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
        'entry_timing': '',
        'market_condition_at_entry': '',
        'why_result_happened': '',
        'skill_vs_luck_meter': '',
        'trade_quality_insight': '',
        'explanation': '',
        'what_went_well': '',
        'risk_still_existed': '',
        'what_went_wrong': '',
        'behavioral_insight': '',
        'improvement_tip': '',
        'repeat_or_improve': '',
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
        elif lower.startswith('entry timing:'):
            parsed['entry_timing'] = line.split(':', 1)[1].strip()
        elif lower.startswith('market condition at entry:'):
            parsed['market_condition_at_entry'] = line.split(':', 1)[1].strip()
        elif lower.startswith('why this result happened:') or lower.startswith('outcome driver:'):
            parsed['why_result_happened'] = line.split(':', 1)[1].strip()
        elif lower.startswith('skill vs luck meter:'):
            parsed['skill_vs_luck_meter'] = line.split(':', 1)[1].strip()
        elif lower.startswith('trade quality insight:'):
            parsed['trade_quality_insight'] = line.split(':', 1)[1].strip()
        elif lower.startswith('explanation:'):
            parsed['explanation'] = line.split(':', 1)[1].strip()
        elif lower.startswith('what went well:'):
            parsed['what_went_well'] = line.split(':', 1)[1].strip()
        elif lower.startswith('risk still existed:'):
            parsed['risk_still_existed'] = line.split(':', 1)[1].strip()
        elif lower.startswith('what went wrong:'):
            parsed['what_went_wrong'] = line.split(':', 1)[1].strip()
        elif lower.startswith('behavioral insight:'):
            parsed['behavioral_insight'] = line.split(':', 1)[1].strip()
        elif lower.startswith('improvement tip:'):
            parsed['improvement_tip'] = line.split(':', 1)[1].strip()
        elif lower.startswith('repeat or improve:'):
            parsed['repeat_or_improve'] = line.split(':', 1)[1].strip()
        elif lower.startswith('action plan:'):
            continue
        elif (raw_line.strip().startswith('- ') or raw_line.strip().startswith('• ')):
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


_PORTFOLIO_QUERY_RE = re.compile(
    r'\b(analy[sz]e|analysis|review|summarize|evaluate|check)\b.*\b(portfolio|holdings|positions|p/?l|profit|loss|performance)\b|'
    r'\b(portfolio|holdings|positions|allocation|exposure|p/?l|profit|loss|performance|'
    r'order|orders|open order|pending order|limit order|stop order|take profit|how am i doing)\b',
    re.IGNORECASE
)


def _looks_like_portfolio_question(text: str) -> bool:
    return bool(_PORTFOLIO_QUERY_RE.search((text or '').strip()))


def _build_rule_based_portfolio_analysis(user_id: int) -> str:
    """Build a useful portfolio analysis from DB when AI provider is unavailable."""
    from app import get_db_connection

    conn = get_db_connection()
    if not conn:
        return (
            "## Portfolio Analysis\n"
            "I could not access your portfolio data right now because the database connection is unavailable. "
            "Please retry in a moment.\n\n"
            "⚠️ IMPORTANT DISCLAIMER:\n"
            "- This is educational content for a SIMULATOR using fake money\n"
            "- NOT financial advice\n"
            "- Real crypto trading involves significant risk\n"
            "- Never invest more than you can afford to lose\n"
            "- Past performance doesn't guarantee future results"
        )

    try:
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            "SELECT username, crypto_bucks, tether_balance, risk_tolerance FROM users WHERE id = %s",
            (user_id,)
        )
        user = cursor.fetchone() or {}

        if not user:
            return (
                "## Portfolio Analysis\n"
                "I could not find your user profile to analyze your portfolio.\n\n"
                "⚠️ IMPORTANT DISCLAIMER:\n"
                "- This is educational content for a SIMULATOR using fake money\n"
                "- NOT financial advice\n"
                "- Real crypto trading involves significant risk\n"
                "- Never invest more than you can afford to lose\n"
                "- Past performance doesn't guarantee future results"
            )

        cursor.execute("""
            SELECT coin_id,
                   SUM(CASE WHEN type='buy' THEN amount ELSE 0 END) AS total_bought,
                   SUM(CASE WHEN type='sell' THEN amount ELSE 0 END) AS total_sold,
                   AVG(CASE WHEN type='buy' THEN price ELSE NULL END) AS avg_buy
            FROM transactions
            WHERE user_id = %s
            GROUP BY coin_id
        """, (user_id,))
        holding_rows = cursor.fetchall() or []

        open_holdings = []
        for row in holding_rows:
            bought = float(row.get('total_bought') or 0)
            sold = float(row.get('total_sold') or 0)
            remaining = bought - sold
            if remaining > 1e-8:
                open_holdings.append({
                    'coin': str(row.get('coin_id') or '').upper(),
                    'amount': remaining,
                    'avg_buy': float(row.get('avg_buy') or 0),
                })

        cursor.execute("""
            SELECT coin_id, amount, price AS buy_price, sold_price,
                   ROUND((sold_price - price) * amount, 2) AS profit
            FROM transactions
            WHERE user_id = %s AND type = 'sell' AND sold_price IS NOT NULL
            ORDER BY id DESC
            LIMIT 20
        """, (user_id,))
        closed_trades = cursor.fetchall() or []

        wins = [float(t.get('profit') or 0) for t in closed_trades if float(t.get('profit') or 0) > 0]
        losses = [float(t.get('profit') or 0) for t in closed_trades if float(t.get('profit') or 0) < 0]
        total_realized = sum(float(t.get('profit') or 0) for t in closed_trades)
        win_rate = (len(wins) / len(closed_trades) * 100.0) if closed_trades else 0.0
        avg_win = (sum(wins) / len(wins)) if wins else 0.0
        avg_loss = (sum(losses) / len(losses)) if losses else 0.0

        open_orders = []
        filled_orders = []
        cancelled_orders = 0
        try:
            cursor.execute("""
                SELECT id, base_currency, quote_currency, order_type, side,
                       amount, price, stop_price, status, created_at
                FROM orders
                WHERE user_id = %s AND status IN ('pending', 'partially_filled')
                ORDER BY created_at DESC
                LIMIT 12
            """, (user_id,))
            open_orders = cursor.fetchall() or []

            cursor.execute("""
                SELECT id, base_currency, quote_currency, order_type, side,
                       amount, price, stop_price, status, filled_at
                FROM orders
                WHERE user_id = %s AND status = 'filled'
                ORDER BY filled_at DESC, created_at DESC
                LIMIT 8
            """, (user_id,))
            filled_orders = cursor.fetchall() or []

            cursor.execute("""
                SELECT COUNT(*) AS cancelled_count
                FROM orders
                WHERE user_id = %s AND status = 'cancelled'
            """, (user_id,))
            cancelled_orders = int((cursor.fetchone() or {}).get('cancelled_count') or 0)
        except Exception:
            open_orders = []
            filled_orders = []
            cancelled_orders = 0

        lines = [
            "## Portfolio Analysis",
            f"User: **{user.get('username', 'Unknown')}**",
            f"Risk tolerance: **{user.get('risk_tolerance') or 'Not set'}**",
            "",
            "### Account Snapshot",
            f"- CryptoBucks balance: **${float(user.get('crypto_bucks') or 0):,.2f}**",
            f"- USDT balance: **${float(user.get('tether_balance') or 0):,.2f}**",
            f"- Open holdings count: **{len(open_holdings)}**",
            f"- Closed trades analyzed: **{len(closed_trades)}**",
            f"- Open/pending orders: **{len(open_orders)}**",
            f"- Recently filled orders analyzed: **{len(filled_orders)}**",
            f"- Cancelled orders: **{cancelled_orders}**",
            "",
        ]

        if open_holdings:
            lines.append("### Open Holdings")
            for h in open_holdings[:8]:
                lines.append(f"- {h['coin']}: {h['amount']:.6f} units, avg buy ${h['avg_buy']:.2f}")
            if len(open_holdings) > 8:
                lines.append(f"- ...and {len(open_holdings) - 8} more holdings")
            lines.append("")
        else:
            lines.extend([
                "### Open Holdings",
                "- No open holdings found.",
                "",
            ])

        lines.extend([
            "### Closed Trade Performance",
            f"- Win rate: **{win_rate:.1f}%**",
            f"- Net realized P/L (recent closed trades): **${total_realized:+,.2f}**",
            f"- Average winning trade: **${avg_win:+,.2f}**",
            f"- Average losing trade: **${avg_loss:+,.2f}**",
            "",
            "### Coaching Notes",
        ])

        if open_orders:
            lines.append("")
            lines.append("### Open Orders")
            for o in open_orders[:8]:
                base = str(o.get('base_currency') or '').upper()
                quote = str(o.get('quote_currency') or '').upper()
                pair = f"{base}/{quote}" if base and quote else base or quote or "UNKNOWN"
                amount = float(o.get('amount') or 0)
                price = o.get('price')
                stop_price = o.get('stop_price')
                px = f" @ ${float(price):,.4f}" if price is not None else " @ market"
                stop = f", stop ${float(stop_price):,.4f}" if stop_price is not None else ""
                lines.append(
                    f"- #{o.get('id')}: {str(o.get('side') or '').upper()} {amount:.6f} {pair} "
                    f"({str(o.get('order_type') or '').replace('_', ' ')}, {str(o.get('status') or '').replace('_', ' ')}){px}{stop}"
                )
            if len(open_orders) > 8:
                lines.append(f"- ...and {len(open_orders) - 8} more open orders")
        else:
            lines.append("")
            lines.append("### Open Orders")
            lines.append("- No open/pending orders found.")

        if filled_orders:
            lines.append("")
            lines.append("### Recently Filled Orders")
            for o in filled_orders[:6]:
                base = str(o.get('base_currency') or '').upper()
                quote = str(o.get('quote_currency') or '').upper()
                pair = f"{base}/{quote}" if base and quote else base or quote or "UNKNOWN"
                amount = float(o.get('amount') or 0)
                price = o.get('price')
                px = f" @ ${float(price):,.4f}" if price is not None else " @ market"
                lines.append(
                    f"- #{o.get('id')}: {str(o.get('side') or '').upper()} {amount:.6f} {pair} "
                    f"({str(o.get('order_type') or '').replace('_', ' ')}){px}"
                )

        if not closed_trades:
            lines.append("- Not enough closed-trade history yet. Focus on consistent position sizing and stop-loss discipline.")
        else:
            if win_rate < 45:
                lines.append("- Your win rate is currently low. Prioritize selective entries over frequent trades.")
            elif win_rate >= 55:
                lines.append("- Your win rate is healthy. Keep protecting capital with strict invalidation rules.")
            else:
                lines.append("- Your win rate is moderate. Improving entry quality can meaningfully raise consistency.")

            if abs(avg_loss) > avg_win and avg_loss != 0:
                lines.append("- Average losses are larger than winners. Tighten stop-losses and avoid moving stops away from risk.")
            else:
                lines.append("- Your win/loss size balance is reasonable. Maintain risk caps per trade.")

            if total_realized < 0:
                lines.append("- Net realized P/L is negative in recent history. Reduce size and trade only your highest-conviction setups.")
            else:
                lines.append("- Net realized P/L is positive in recent history. Stay process-focused and avoid overconfidence.")

        lines.extend([
            "",
            "⚠️ IMPORTANT DISCLAIMER:",
            "- This is educational content for a SIMULATOR using fake money",
            "- NOT financial advice",
            "- Real crypto trading involves significant risk",
            "- Never invest more than you can afford to lose",
            "- Past performance doesn't guarantee future results",
        ])

        return "\n".join(lines)
    except Exception:
        return (
            "## Portfolio Analysis\n"
            "I could not complete portfolio analysis right now due to a temporary backend issue. Please try again.\n\n"
            "⚠️ IMPORTANT DISCLAIMER:\n"
            "- This is educational content for a SIMULATOR using fake money\n"
            "- NOT financial advice\n"
            "- Real crypto trading involves significant risk\n"
            "- Never invest more than you can afford to lose\n"
            "- Past performance doesn't guarantee future results"
        )
    finally:
        if conn and conn.is_connected():
            conn.close()


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
    explanation = 'This trade closed green, but the quality depends on how strong your entry timing and risk plan were.'
    tip = 'Keep following a written plan with clear entry, exit, and risk limits.'
    entry_timing = 'Entry timing could not be fully verified because RSI-at-entry data was unavailable.'
    market_condition = 'Market condition at entry appears mixed from available signals.'
    why_result_happened = 'The result came from short-term price movement between your buy and sell levels.'
    skill_vs_luck_meter = '55/100'
    trade_quality_insight = 'This outcome shows some execution skill but still includes market luck.'
    risk_still_existed = 'Risk remained because the trade context was partially uncertain at entry.'
    repeat_or_improve = 'Repeat the planning discipline and improve by recording your entry trigger before each trade.'
    behavioral_insight = 'This trade suggests your process can improve by defining risk rules before entry.'

    # Priority-based classification from strongest signals to weakest.
    if buy_rsi is not None and buy_rsi >= 70 and pnl_negative:
        mistake_type = 'FOMO Buying'
        entry_timing = f'Late/risky entry: RSI at entry was {buy_rsi:.1f}, suggesting you bought after a strong run.'
        market_condition = 'Failed bounce conditions: momentum was stretched, then selling resumed.'
        why_result_happened = f'Cause: you entered late into strength. Mistake: trend continuation was assumed without confirmation. Consequence: price reversed and loss reached {pnl_pct:.2f}%.'
        skill_vs_luck_meter = '28/100'
        trade_quality_insight = 'The outcome was mostly driven by poor timing rather than a high-probability setup.'
        risk_still_existed = 'Reversal risk was high the moment you entered.'
        repeat_or_improve = 'Avoid chasing green candles; wait for pullback + confirmation.'
        behavioral_insight = 'This reflects impulse-entry behavior and low confirmation discipline under momentum pressure.'
        explanation = (
            f'You entered when RSI was high ({buy_rsi:.1f}), which often means the price was already overheated. '
            f'The trade then moved against you ({pnl_pct:.2f}%).'
        )
        went_wrong = 'Entry happened when momentum was already stretched, so upside was limited and reversal risk was high.'
        went_well = 'You completed the trade and can now review it objectively instead of ignoring the loss.'
        tip = 'Wait for pullbacks or confirmation before buying after sharp moves.'
    elif pnl_negative and minutes is not None and minutes <= 20:
        mistake_type = 'Panic Selling'
        entry_timing = 'Entry timing may not be the core issue; the main issue was an emotion-driven early exit.'
        market_condition = 'Likely continued downtrend or failed bounce during a weak tape.'
        why_result_happened = f'Cause: price stayed weak after entry. Mistake: reactive exit under pressure without plan. Consequence: trade closed in loss after {int(minutes)} minutes ({pnl_pct:.2f}%).'
        skill_vs_luck_meter = '40/100'
        trade_quality_insight = 'This looks more like emotional reaction than systematic execution.'
        risk_still_existed = 'Without predefined invalidation, short-term volatility can force poor exits.'
        repeat_or_improve = 'Predefine stop-loss and hold only to rule-based invalidation.'
        behavioral_insight = 'This suggests emotional reactivity and low tolerance for normal pullbacks without a predefined exit rule.'
        explanation = (
            f'You exited quickly after entry ({int(minutes)} minutes) with a loss ({pnl_pct:.2f}%), '
            'which suggests an emotion-driven exit instead of a planned one.'
        )
        went_wrong = 'The exit looked reactive rather than rule-based, which usually locks in avoidable losses.'
        went_well = 'You contained risk by closing instead of averaging down emotionally.'
        tip = 'Set your stop-loss and target before entering so you do not react emotionally.'
    elif minutes is not None and minutes <= 10 and abs(pnl_pct) <= 1.5:
        mistake_type = 'Overtrading'
        entry_timing = f'Timing was low-conviction: very short hold ({int(minutes)} min) indicates a rushed setup.'
        market_condition = 'Likely range-bound/noisy market rather than a clean directional move.'
        why_result_happened = f'Cause: setup quality was weak in choppy conditions. Mistake: rapid entry/exit without edge. Consequence: outcome stayed near noise at {pnl_pct:.2f}%.'
        skill_vs_luck_meter = '38/100'
        trade_quality_insight = 'The trade looked reactive and too short to validate a full setup.'
        risk_still_existed = 'Frequent short trades increase random outcomes and decision fatigue.'
        repeat_or_improve = 'Trade less often and only when your setup checklist is fully met.'
        behavioral_insight = 'This indicates a compulsion to trade activity rather than waiting for high-quality setups.'
        explanation = (
            f'The holding time was very short ({int(minutes)} minutes) with small movement ({pnl_pct:.2f}%). '
            'Frequent quick trades can increase mistakes and fees.'
        )
        went_wrong = 'Trade duration was too short for the setup to develop, making the decision mostly noise-driven.'
        went_well = 'Position sizing appears contained, so the loss impact stayed manageable.'
        tip = 'Trade less often and only when your setup is clearly valid.'
    elif pnl_pct <= -3:
        mistake_type = 'No Stop Loss'
        entry_timing = 'Entry was early in a weak market and likely against the active trend.'
        market_condition = 'Continued downtrend with no confirmed reversal signal.'
        why_result_happened = f'Cause: selling pressure continued after entry. Mistake: no predefined stop-loss. Consequence: loss expanded to {pnl_pct:.2f}% instead of being capped.'
        skill_vs_luck_meter = '35/100'
        trade_quality_insight = 'Execution quality was limited by missing risk boundaries.'
        risk_still_existed = 'Downside risk remained fully open throughout the trade.'
        repeat_or_improve = 'Always set stop-loss at entry and cap risk to 1-2% per trade.'
        behavioral_insight = 'This suggests a tendency to hold losers without predefined exits, which compounds risk quickly.'
        explanation = (
            f'This trade ended with a larger loss ({pnl_pct:.2f}%). '
            'A predefined stop-loss could have limited downside risk.'
        )
        went_wrong = 'Loss size suggests risk limits were not predefined or not respected during the trade.'
        went_well = 'You closed the position and prevented the loss from growing further.'
        tip = 'Place a stop-loss at entry and cap risk per trade to 1-2% of capital.'
    elif pnl_negative:
        mistake_type = 'Panic Selling'
        entry_timing = 'Entry was early in a weak/uncertain market with limited confirmation.'
        market_condition = 'Likely weak trend or failed bounce where sellers remained in control.'
        why_result_happened = f'Cause: market failed to recover after entry. Mistake: entry lacked confirmation and risk plan. Consequence: trade closed at {pnl_pct:.2f}% loss.'
        skill_vs_luck_meter = '45/100'
        trade_quality_insight = 'This trade was partly process-driven but lacked strong pre-trade structure.'
        risk_still_existed = 'Ambiguous exit criteria left room for emotional execution.'
        repeat_or_improve = 'Document invalidation and expected scenario before every entry.'
        behavioral_insight = 'This suggests planning gaps: the trade thesis and exit rules were not concrete before execution.'
        explanation = (
            f'This trade closed in loss ({pnl_pct:.2f}%). '
            'Without a strong rule-based exit, small losses are often caused by reactive decisions.'
        )
        went_wrong = 'The trade lacked a clearly documented invalidation rule before entry.'
        went_well = 'Loss remained relatively small, which gives room to improve without major damage.'
        tip = 'Before entering, define your invalidation level and exit only if that rule is hit.'
    elif pnl_pct >= 1:
        mistake_type = 'Good Trade'
        if buy_rsi is None:
            entry_timing = f'Entry timing appears acceptable: the trade reached profit with a {pnl_pct:.2f}% move.'
        elif buy_rsi <= 35:
            entry_timing = f'Strong timing: you entered after weakness (RSI {buy_rsi:.1f}), then captured recovery.'
        elif buy_rsi >= 65:
            entry_timing = f'Late-but-worked timing: entry at RSI {buy_rsi:.1f} was riskier and relied on continuation.'
        else:
            entry_timing = f'Balanced timing: entry RSI {buy_rsi:.1f} was near neutral, reducing chase risk.'

        if minutes is not None and minutes <= 45:
            market_condition = 'Short-term recovery/bounce environment favored quick profit-taking.'
        elif minutes is not None and minutes > 180:
            market_condition = 'Trend-following environment likely supported a longer hold.'
        else:
            market_condition = 'Moderate trend conditions likely supported a controlled move.'

        if buy_rsi is not None and buy_rsi >= 65:
            why_result_happened = 'Profit likely came from favorable continuation in market momentum, not low-risk timing.'
            skill_vs_luck_meter = '58/100'
            trade_quality_insight = 'This winner had execution skill, but continuation luck also helped.'
        else:
            why_result_happened = 'Profit came from a reasonably timed entry plus controlled exit discipline.'
            skill_vs_luck_meter = '72/100'
            trade_quality_insight = 'This result appears primarily skill-based with moderate market tailwind.'

        risk_still_existed = 'Even profitable trades can fail if trend strength fades suddenly.'
        repeat_or_improve = 'Repeat your entry discipline and improve by documenting exact setup tags in your journal.'
        behavioral_insight = 'This trade shows improving discipline, but consistency still depends on repeating the same pre-trade checklist.'
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
        f"- Entry Timing: {entry_timing}\n"
        f"- Market Condition at Entry: {market_condition}\n"
        f"- Why This Result Happened: {why_result_happened}\n"
        f"- Skill vs Luck Meter: {skill_vs_luck_meter}\n"
        f"- Trade Quality Insight: {trade_quality_insight}\n"
        f"- Explanation: {explanation}\n"
        f"- What Went Well: {went_well}\n"
        f"- Risk Still Existed: {risk_still_existed}\n"
        f"- What Went Wrong: {went_wrong}\n"
        f"- Behavioral Insight: {behavioral_insight}\n"
        f"- Improvement Tip: {tip}\n"
        f"- Repeat or Improve: {repeat_or_improve}"
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
            'entry_timing': entry_timing,
            'market_condition_at_entry': market_condition,
            'why_result_happened': why_result_happened,
            'skill_vs_luck_meter': skill_vs_luck_meter,
            'trade_quality_insight': trade_quality_insight,
            'explanation': explanation,
            'what_went_well': went_well,
            'risk_still_existed': risk_still_existed,
            'what_went_wrong': went_wrong,
            'behavioral_insight': behavioral_insight,
            'improvement_tip': tip,
            'repeat_or_improve': repeat_or_improve,
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

        response_text = result.get('response', '')
        if _looks_like_ai_provider_error(response_text):
            if _looks_like_portfolio_question(question):
                response_text = _build_rule_based_portfolio_analysis(session['user_id'])
            else:
                response_text = (
                    "I am temporarily unable to reach the AI provider, so here is a quick learning-first fallback:\n\n"
                    "### Risk Management Checklist\n"
                    "- Define max risk per trade before entry (for beginners: 1-2% of account).\n"
                    "- Set stop-loss at invalidation, not at random round numbers.\n"
                    "- Use position sizing so one loss cannot damage your account.\n"
                    "- Avoid revenge trades after losses and avoid FOMO after pumps.\n"
                    "\n"
                    "Ask a more specific question like: \"Analyze my portfolio\" or \"Review my last losing trade\" and I will give a structured breakdown.\n\n"
                    "⚠️ IMPORTANT DISCLAIMER:\n"
                    "- This is educational content for a SIMULATOR using fake money\n"
                    "- NOT financial advice\n"
                    "- Real crypto trading involves significant risk\n"
                    "- Never invest more than you can afford to lose\n"
                    "- Past performance doesn't guarantee future results"
                )
        
        return jsonify({
            'success': True,
            'response': response_text,
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

        # Fill missing advanced fields with deterministic trade-context hints.
        context_defaults = _build_rule_based_trade_mistake(trade_inputs).get('parsed', {})
        for key in [
            'entry_timing',
            'market_condition_at_entry',
            'why_result_happened',
            'skill_vs_luck_meter',
            'trade_quality_insight',
            'risk_still_existed',
            'repeat_or_improve',
            'behavioral_insight'
        ]:
            if not parsed.get(key):
                parsed[key] = context_defaults.get(key, '')

        # Enforce non-generic losing-trade explanation quality.
        pnl_value = _extract_numeric(trade_inputs.get('profit_loss'))
        is_losing_trade = pnl_value is not None and pnl_value < 0
        generic_markers = [
            'market moved against',
            'moved against you',
            'adverse market movement',
            'unfavorable market movement'
        ]
        explanation_text = (parsed.get('explanation') or '').lower()
        if is_losing_trade and (not explanation_text or any(marker in explanation_text for marker in generic_markers)):
            parsed['explanation'] = context_defaults.get('explanation') or parsed.get('explanation', '')
            parsed['why_result_happened'] = context_defaults.get('why_result_happened') or parsed.get('why_result_happened', '')
            parsed['market_condition_at_entry'] = context_defaults.get('market_condition_at_entry') or parsed.get('market_condition_at_entry', '')
            parsed['entry_timing'] = context_defaults.get('entry_timing') or parsed.get('entry_timing', '')
            parsed['behavioral_insight'] = context_defaults.get('behavioral_insight') or parsed.get('behavioral_insight', '')

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
