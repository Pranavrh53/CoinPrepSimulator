"""
User Profiler: Analyzes trading behavior and calculates skill level
"""

import json
from datetime import datetime, timedelta
from typing import Dict, List


class UserProfiler:
    def __init__(self, db_connection):
        """
        Initialize user profiler
        
        Args:
            db_connection: MySQL connection function
        """
        self.get_db = db_connection
    
    def update_profile(self, user_id: int) -> Dict:
        """
        Analyze user's trading history and update learning profile
        
        Args:
            user_id: User ID to profile
            
        Returns:
            Updated profile dict
        """
        conn = self.get_db()
        cursor = conn.cursor(dictionary=True)
        
        # Get all completed trades
        cursor.execute("""
            SELECT 
                t.*,
                CASE 
                    WHEN t.sold_price > t.price THEN 'win'
                    WHEN t.sold_price < t.price THEN 'loss'
                    ELSE 'neutral'
                END as outcome,
                (t.sold_price - t.price) * t.amount as profit_loss
            FROM transactions t
            WHERE t.user_id = %s 
            AND t.sold_price IS NOT NULL
            ORDER BY t.timestamp DESC
        """, (user_id,))
        
        trades = cursor.fetchall()
        
        if not trades:
            # New user - set beginner defaults
            cursor.execute("""
                INSERT INTO learning_profiles (user_id, skill_level, weak_areas)
                VALUES (%s, 'beginner', %s)
                ON DUPLICATE KEY UPDATE user_id=user_id
            """, (user_id, json.dumps(['risk_management', 'stop_loss'])))
            conn.commit()
            
            cursor.close()
            conn.close()
            
            return {
                'skill_level': 'beginner',
                'total_trades': 0,
                'message': 'New trader profile created'
            }
        
        # Calculate statistics
        stats = self._calculate_stats(trades)
        
        # Identify weak areas
        weak_areas = self._identify_weak_areas(trades, stats)
        
        # Determine skill level
        skill_level = self._calculate_skill_level(stats)
        
        # Find biggest mistake
        biggest_mistake = self._find_biggest_mistake(trades)
        
        # Update database
        cursor.execute("""
            UPDATE learning_profiles SET
                skill_level = %s,
                total_trades = %s,
                winning_trades = %s,
                losing_trades = %s,
                win_rate = %s,
                avg_profit_per_trade = %s,
                avg_loss_per_trade = %s,
                uses_stop_loss_percent = %s,
                avg_leverage_used = %s,
                biggest_mistake = %s,
                weak_areas = %s,
                last_active = NOW()
            WHERE user_id = %s
        """, (
            skill_level,
            stats['total_trades'],
            stats['winning_trades'],
            stats['losing_trades'],
            stats['win_rate'],
            stats['avg_profit'],
            stats['avg_loss'],
            stats['stop_loss_usage'],
            stats['avg_leverage'],
            biggest_mistake,
            json.dumps(weak_areas),
            user_id
        ))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return {
            'skill_level': skill_level,
            'total_trades': stats['total_trades'],
            'win_rate': stats['win_rate'],
            'weak_areas': weak_areas,
            'biggest_mistake': biggest_mistake,
            'stats': stats
        }
    
    def get_learning_recommendations(self, user_id: int) -> List[Dict]:
        """
        Generate personalized learning recommendations
        
        Returns:
            List of recommended lessons/content
        """
        conn = self.get_db()
        cursor = conn.cursor(dictionary=True)
        
        # Get profile
        cursor.execute("""
            SELECT * FROM learning_profiles WHERE user_id = %s
        """, (user_id,))
        profile = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if not profile:
            return []
        
        weak_areas = json.loads(profile.get('weak_areas') or '[]')
        skill_level = profile['skill_level']
        
        recommendations = []
        
        # Map weak areas to content
        content_map = {
            'stop_loss': {
                'title': 'Stop Loss Orders Explained',
                'category': 'risk_management',
                'reason': 'You rarely use stop losses',
                'priority': 'HIGH'
            },
            'risk_management': {
                'title': 'Position Sizing Guide',
                'category': 'trading_strategies',
                'reason': 'Your position sizes are inconsistent',
                'priority': 'HIGH'
            },
            'leverage': {
                'title': 'The 2021 Leverage Trap Case Study',
                'category': 'case_studies',
                'reason': 'You use high leverage frequently',
                'priority': 'CRITICAL'
            },
            'psychology': {
                'title': 'Conquering FOMO',
                'category': 'psychology',
                'reason': 'Emotional trading patterns detected',
                'priority': 'MEDIUM'
            },
            'timing': {
                'title': 'Technical Analysis Basics',
                'category': 'trading_strategies',
                'reason': 'Improve entry/exit timing',
                'priority': 'MEDIUM'
            }
        }
        
        # Add recommendations for weak areas
        for area in weak_areas[:3]:  # Top 3 weaknesses
            if area in content_map:
                recommendations.append(content_map[area])
        
        # Add skill-appropriate content
        if skill_level == 'beginner':
            recommendations.append({
                'title': 'Crypto Basics',
                'category': 'crypto_basics',
                'reason': 'Foundation knowledge',
                'priority': 'MEDIUM'
            })
        
        return recommendations
    
    def track_learning_progress(self, user_id: int, content_id: str, 
                               content_type: str, time_spent: int, 
                               score: int = None) -> bool:
        """
        Track user's learning activity
        
        Args:
            user_id: User ID
            content_id: Lesson/quiz ID
            content_type: 'lesson', 'quiz', 'challenge', etc.
            time_spent: Seconds spent
            score: Optional quiz score
            
        Returns:
            Success boolean
        """
        try:
            conn = self.get_db()
            cursor = conn.cursor()
            
            # Check if exists
            cursor.execute("""
                SELECT id, attempts, time_spent FROM learning_progress
                WHERE user_id = %s AND content_id = %s AND content_type = %s
            """, (user_id, content_id, content_type))
            
            existing = cursor.fetchone()
            
            if existing:
                # Update existing
                cursor.execute("""
                    UPDATE learning_progress SET
                        status = CASE 
                            WHEN %s IS NOT NULL THEN 'completed'
                            ELSE 'in_progress'
                        END,
                        score = COALESCE(%s, score),
                        time_spent = time_spent + %s,
                        attempts = attempts + 1,
                        completed_at = CASE 
                            WHEN %s IS NOT NULL THEN NOW()
                            ELSE completed_at
                        END,
                        updated_at = NOW()
                    WHERE id = %s
                """, (score, score, time_spent, score, existing[0]))
            else:
                # Insert new
                status = 'completed' if score is not None else 'in_progress'
                cursor.execute("""
                    INSERT INTO learning_progress
                    (user_id, content_type, content_id, status, score, time_spent, attempts, completed_at)
                    VALUES (%s, %s, %s, %s, %s, %s, 1, 
                            CASE WHEN %s IS NOT NULL THEN NOW() ELSE NULL END)
                """, (user_id, content_type, content_id, status, score, time_spent, score))
            
            conn.commit()
            
            # Update total learning time
            cursor.execute("""
                UPDATE learning_profiles 
                SET total_learning_time = total_learning_time + %s
                WHERE user_id = %s
            """, (time_spent // 60, user_id))  # Convert to minutes
            
            conn.commit()
            cursor.close()
            conn.close()
            
            return True
            
        except Exception as e:
            print(f"Error tracking progress: {e}")
            return False
    
    # ==================== PRIVATE HELPER METHODS ====================
    
    def _calculate_stats(self, trades: List[Dict]) -> Dict:
        """Calculate trading statistics"""
        total_trades = len(trades)
        winning_trades = sum(1 for t in trades if t['outcome'] == 'win')
        losing_trades = sum(1 for t in trades if t['outcome'] == 'loss')
        
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        
        # Calculate average profit/loss
        profits = [t['profit_loss'] for t in trades if t['outcome'] == 'win']
        losses = [abs(t['profit_loss']) for t in trades if t['outcome'] == 'loss']
        
        avg_profit = sum(profits) / len(profits) if profits else 0
        avg_loss = sum(losses) / len(losses) if losses else 0
        
        # Check stop loss usage (mock - you'd need to add this field to transactions)
        # For now, estimate based on loss amounts
        reasonable_losses = sum(1 for l in losses if l < avg_profit * 2)
        stop_loss_usage = (reasonable_losses / len(losses) * 100) if losses else 0
        
        # Average leverage (mock - you'd need to add this field)
        avg_leverage = 1.0  # Default, enhance later
        
        # Risk-reward ratio
        rr_ratio = avg_profit / avg_loss if avg_loss > 0 else 0
        
        # Largest win/loss
        largest_win = max(profits) if profits else 0
        largest_loss = max(losses) if losses else 0
        
        # Recent performance (last 10 trades)
        recent_trades = trades[:10]
        recent_wins = sum(1 for t in recent_trades if t['outcome'] == 'win')
        recent_win_rate = (recent_wins / len(recent_trades) * 100) if recent_trades else 0
        
        return {
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': round(win_rate, 2),
            'avg_profit': round(avg_profit, 2),
            'avg_loss': round(avg_loss, 2),
            'stop_loss_usage': round(stop_loss_usage, 2),
            'avg_leverage': avg_leverage,
            'rr_ratio': round(rr_ratio, 2),
            'largest_win': round(largest_win, 2),
            'largest_loss': round(largest_loss, 2),
            'recent_win_rate': round(recent_win_rate, 2)
        }
    
    def _identify_weak_areas(self, trades: List[Dict], stats: Dict) -> List[str]:
        """Identify user's weak areas based on trading patterns"""
        weak_areas = []
        
        # Check stop loss usage
        if stats['stop_loss_usage'] < 50:
            weak_areas.append('stop_loss')
        
        # Check risk management
        if stats['largest_loss'] > stats['avg_profit'] * 5:
            weak_areas.append('risk_management')
        
        # Check consistency
        if abs(stats['recent_win_rate'] - stats['win_rate']) > 20:
            weak_areas.append('consistency')
        
        # Check risk-reward ratio
        if stats['rr_ratio'] < 1.5:
            weak_areas.append('risk_reward')
        
        # Check for overtrading
        if stats['total_trades'] > 100 and stats['win_rate'] < 45:
            weak_areas.append('overtrading')
        
        # Emotional trading detection
        recent_losses = [t for t in trades[:5] if t['outcome'] == 'loss']
        if len(recent_losses) >= 3:
            weak_areas.append('psychology')
        
        # Position sizing issues
        position_sizes = [t['amount'] * t['price'] for t in trades[:10]]
        if position_sizes:
            size_variance = max(position_sizes) / min(position_sizes) if min(position_sizes) > 0 else 0
            if size_variance > 10:
                weak_areas.append('position_sizing')
        
        return weak_areas[:4]  # Return top 4
    
    def _calculate_skill_level(self, stats: Dict) -> str:
        """Determine skill level based on stats"""
        score = 0
        
        # Total experience
        if stats['total_trades'] >= 100:
            score += 3
        elif stats['total_trades'] >= 50:
            score += 2
        elif stats['total_trades'] >= 20:
            score += 1
        
        # Win rate
        if stats['win_rate'] >= 60:
            score += 3
        elif stats['win_rate'] >= 50:
            score += 2
        elif stats['win_rate'] >= 40:
            score += 1
        
        # Risk management
        if stats['stop_loss_usage'] >= 80:
            score += 2
        elif stats['stop_loss_usage'] >= 50:
            score += 1
        
        # Risk-reward ratio
        if stats['rr_ratio'] >= 2:
            score += 2
        elif stats['rr_ratio'] >= 1.5:
            score += 1
        
        # Consistency
        if abs(stats['recent_win_rate'] - stats['win_rate']) < 10:
            score += 1
        
        # Determine level
        if score >= 9:
            return 'advanced'
        elif score >= 5:
            return 'intermediate'
        else:
            return 'beginner'
    
    def _find_biggest_mistake(self, trades: List[Dict]) -> str:
        """Identify user's most costly recurring mistake"""
        if not trades:
            return 'none_yet'
        
        # Find largest loss
        losses = [t for t in trades if t['outcome'] == 'loss']
        if not losses:
            return 'none'
        
        biggest_loss = max(losses, key=lambda t: abs(t['profit_loss']))
        loss_amount = abs(biggest_loss['profit_loss'])
        
        # Categorize the mistake
        if loss_amount > 1000:
            return 'no_stop_loss_major_loss'
        elif biggest_loss.get('type') == 'market' and loss_amount > 500:
            return 'panic_selling'
        elif len([t for t in trades[:5] if t['outcome'] == 'loss']) >= 3:
            return 'emotional_trading_streak'
        else:
            return 'poor_timing'


# Factory function for Flask integration
def get_user_profiler(db_connection):
    """Create user profiler instance"""
    return UserProfiler(db_connection)
