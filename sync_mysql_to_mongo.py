import os
import json
from datetime import date, datetime, time
from decimal import Decimal

import mysql.connector
from bson.decimal128 import Decimal128
from pymongo import MongoClient


MYSQL_CONFIG = {
    "host": os.getenv("MYSQL_HOST", "localhost"),
    "user": os.getenv("MYSQL_USER", "root"),
    "password": os.getenv("MYSQL_PASSWORD", "Pranavrh123$"),
    "database": os.getenv("MYSQL_DATABASE", "crypto_tracker"),
}

MONGO_URI = os.getenv("MONGO_URI", "mongodb://127.0.0.1:27017/")
MONGO_DB = os.getenv("MONGO_DB_NAME", "crypto_tracker")


def d128(value):
    try:
        return Decimal128(str(Decimal(str(value))))
    except Exception:
        return Decimal128("0")


def to_dt(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, time.min)
    return None


def parse_json_field(value, default):
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return default
    return default


def upsert_simple_by_mysql_id(collection, mysql_id, data):
    collection.update_one(
        {f"mysql_{collection.name[:-1] if collection.name.endswith('s') else collection.name}_id": int(mysql_id)},
        {"$set": data},
        upsert=True,
    )


def main():
    mysql_conn = mysql.connector.connect(**MYSQL_CONFIG)
    mongo = MongoClient(MONGO_URI)[MONGO_DB]

    mysql_cur = mysql_conn.cursor(dictionary=True)

    def user_oid(mysql_user_id):
        doc = mongo.users.find_one({"mysql_user_id": int(mysql_user_id)})
        return doc["_id"] if doc else None

    def wallet_oid(mysql_wallet_id, mysql_user_id):
        doc = mongo.wallets.find_one(
            {"mysql_wallet_id": int(mysql_wallet_id), "mysql_user_id": int(mysql_user_id)}
        )
        return doc["_id"] if doc else None

    def pair_oid(mysql_pair_id):
        if mysql_pair_id is None:
            return None
        doc = mongo.trading_pairs.find_one({"mysql_pair_id": int(mysql_pair_id)})
        return doc["_id"] if doc else None

    def tx_oid(mysql_tx_id):
        if mysql_tx_id is None:
            return None
        doc = mongo.transactions.find_one({"mysql_transaction_id": int(mysql_tx_id)})
        return doc["_id"] if doc else None

    def order_oid(mysql_order_id):
        if mysql_order_id is None:
            return None
        doc = mongo.orders.find_one({"mysql_order_id": int(mysql_order_id)})
        return doc["_id"] if doc else None

    def alert_oid(mysql_alert_id):
        if mysql_alert_id is None:
            return None
        doc = mongo.price_alerts.find_one({"mysql_alert_id": int(mysql_alert_id)})
        return doc["_id"] if doc else None

    # users
    mysql_cur.execute(
        """
        SELECT id, username, email, password, crypto_bucks, tether_balance, risk_tolerance,
               risk_score, verification_code, verified, achievements, created_at
        FROM users
        """
    )
    users = mysql_cur.fetchall() or []
    for u in users:
        achievements = u.get("achievements")
        if isinstance(achievements, str):
            achievements = [a.strip() for a in achievements.split(",") if a.strip()]
        elif achievements is None:
            achievements = []

        existing_user = mongo.users.find_one({"mysql_user_id": int(u["id"])})
        if not existing_user:
            existing_user = mongo.users.find_one({"email": u.get("email")})
        if not existing_user:
            existing_user = mongo.users.find_one({"username": u.get("username")})

        user_filter = {"_id": existing_user["_id"]} if existing_user else {"mysql_user_id": int(u["id"])}

        mongo.users.update_one(
            user_filter,
            {
                "$set": {
                    "mysql_user_id": int(u["id"]),
                    "username": u.get("username") or "",
                    "email": u.get("email") or "",
                    "password": u.get("password") or "",
                    "crypto_bucks": d128(u.get("crypto_bucks", 0)),
                    "tether_balance": d128(u.get("tether_balance", 0)),
                    "risk_tolerance": u.get("risk_tolerance") or "Medium",
                    "risk_score": int(u.get("risk_score") or 0),
                    "verification_code": u.get("verification_code"),
                    "verified": bool(u.get("verified")),
                    "achievements": achievements,
                },
                "$setOnInsert": {
                    "created_at": u.get("created_at") or datetime.now(),
                },
            },
            upsert=True,
        )

    # wallets
    mysql_cur.execute("SELECT id, user_id, name FROM wallets")
    wallets = mysql_cur.fetchall() or []
    for w in wallets:
        user_doc = mongo.users.find_one({"mysql_user_id": int(w["user_id"])})
        if not user_doc:
            continue
        mongo.wallets.update_one(
            {"mysql_wallet_id": int(w["id"]), "mysql_user_id": int(w["user_id"])},
            {
                "$set": {
                    "user_id": user_doc["_id"],
                    "name": w.get("name") or f"Wallet {w['id']}",
                },
                "$setOnInsert": {
                    "created_at": datetime.now(),
                },
            },
            upsert=True,
        )

    # watchlist
    mysql_cur.execute("SELECT id, user_id, coin_id, added_at FROM watchlist")
    for row in mysql_cur.fetchall() or []:
        uoid = user_oid(row["user_id"])
        if not uoid:
            continue
        existing_doc = mongo.watchlist.find_one(
            {
                "user_id": uoid,
                "coin_id": (row.get("coin_id") or "").lower(),
            }
        )
        filter_doc = {"_id": existing_doc["_id"]} if existing_doc else {"mysql_watchlist_id": int(row["id"])}
        mongo.watchlist.update_one(
            filter_doc,
            {
                "$set": {
                    "mysql_watchlist_id": int(row["id"]),
                    "mysql_user_id": int(row["user_id"]),
                    "user_id": uoid,
                    "coin_id": (row.get("coin_id") or "").lower(),
                    "added_at": to_dt(row.get("added_at")) or datetime.now(),
                }
            },
            upsert=True,
        )

    # trading_pairs
    mysql_cur.execute(
        "SELECT id, base_currency, quote_currency, symbol, is_active, created_at FROM trading_pairs"
    )
    for row in mysql_cur.fetchall() or []:
        existing_doc = mongo.trading_pairs.find_one(
            {
                "base_currency": row.get("base_currency") or "",
                "quote_currency": row.get("quote_currency") or "",
            }
        )
        filter_doc = {"_id": existing_doc["_id"]} if existing_doc else {"mysql_pair_id": int(row["id"])}
        mongo.trading_pairs.update_one(
            filter_doc,
            {
                "$set": {
                    "mysql_pair_id": int(row["id"]),
                    "base_currency": row.get("base_currency") or "",
                    "quote_currency": row.get("quote_currency") or "",
                    "symbol": row.get("symbol") or "",
                    "is_active": bool(row.get("is_active")),
                    "created_at": to_dt(row.get("created_at")) or datetime.now(),
                }
            },
            upsert=True,
        )

    # transactions
    mysql_cur.execute(
        """
        SELECT id, user_id, wallet_id, coin_id, amount, price, type, sold_price, buy_transaction_id, timestamp
        FROM transactions
        """
    )
    txs = mysql_cur.fetchall() or []

    for t in txs:
        user_doc = mongo.users.find_one({"mysql_user_id": int(t["user_id"])})
        wallet_doc = mongo.wallets.find_one(
            {"mysql_wallet_id": int(t["wallet_id"]), "mysql_user_id": int(t["user_id"])}
        )
        if not user_doc or not wallet_doc:
            continue

        update = {
            "mysql_transaction_id": int(t["id"]),
            "mysql_user_id": int(t["user_id"]),
            "mysql_wallet_id": int(t["wallet_id"]),
            "user_id": user_doc["_id"],
            "wallet_id": wallet_doc["_id"],
            "coin_id": (t.get("coin_id") or "").lower(),
            "amount": d128(t.get("amount", 0)),
            "price": d128(t.get("price", 0)),
            "type": t.get("type") or "buy",
            "timestamp": t.get("timestamp") or datetime.utcnow(),
        }
        if t.get("sold_price") is not None:
            update["sold_price"] = d128(t.get("sold_price"))
        if t.get("buy_transaction_id") is not None:
            update["buy_transaction_mysql_id"] = int(t.get("buy_transaction_id"))

        mongo.transactions.update_one(
            {"mysql_transaction_id": int(t["id"])},
            {"$set": update},
            upsert=True,
        )

    # orders
    mysql_cur.execute(
        """
        SELECT id, user_id, wallet_id, pair_id, base_currency, quote_currency, order_type, side,
               amount, price, stop_price, filled_amount, status, created_at, filled_at, cancelled_at
        FROM orders
        """
    )
    for row in mysql_cur.fetchall() or []:
        uoid = user_oid(row["user_id"])
        woid = wallet_oid(row["wallet_id"], row["user_id"])
        if not uoid or not woid:
            continue
        poid = pair_oid(row.get("pair_id"))
        mongo.orders.update_one(
            {"mysql_order_id": int(row["id"])},
            {
                "$set": {
                    "mysql_order_id": int(row["id"]),
                    "mysql_user_id": int(row["user_id"]),
                    "mysql_wallet_id": int(row["wallet_id"]),
                    "mysql_pair_id": int(row["pair_id"]) if row.get("pair_id") is not None else None,
                    "user_id": uoid,
                    "wallet_id": woid,
                    "pair_id": poid,
                    "base_currency": row.get("base_currency") or "",
                    "quote_currency": row.get("quote_currency") or "",
                    "order_type": row.get("order_type") or "market",
                    "side": row.get("side") or "buy",
                    "amount": d128(row.get("amount", 0)),
                    "price": d128(row.get("price", 0)) if row.get("price") is not None else None,
                    "stop_price": d128(row.get("stop_price", 0)) if row.get("stop_price") is not None else None,
                    "filled_amount": d128(row.get("filled_amount", 0) or 0),
                    "status": row.get("status") or "pending",
                    "created_at": to_dt(row.get("created_at")) or datetime.now(),
                    "filled_at": to_dt(row.get("filled_at")),
                    "cancelled_at": to_dt(row.get("cancelled_at")),
                }
            },
            upsert=True,
        )

    # order_fills
    mysql_cur.execute(
        "SELECT id, order_id, user_id, filled_amount, filled_price, filled_at FROM order_fills"
    )
    for row in mysql_cur.fetchall() or []:
        uoid = user_oid(row["user_id"])
        ooid = order_oid(row["order_id"])
        if not uoid or not ooid:
            continue
        mongo.order_fills.update_one(
            {"mysql_fill_id": int(row["id"])},
            {
                "$set": {
                    "mysql_fill_id": int(row["id"]),
                    "mysql_order_id": int(row["order_id"]),
                    "mysql_user_id": int(row["user_id"]),
                    "order_id": ooid,
                    "user_id": uoid,
                    "filled_amount": d128(row.get("filled_amount", 0)),
                    "filled_price": d128(row.get("filled_price", 0)),
                    "filled_at": to_dt(row.get("filled_at")) or datetime.now(),
                }
            },
            upsert=True,
        )

    # price_alerts
    mysql_cur.execute(
        """
        SELECT id, user_id, user_email, coin_id, target_price, alert_type, order_type,
               created_at, notified, note, snoozed_until, triggered_at, trigger_price
        FROM price_alerts
        """
    )
    for row in mysql_cur.fetchall() or []:
        uoid = user_oid(row["user_id"])
        if not uoid:
            continue
        order_type = row.get("order_type")
        if order_type not in ("limit", "market", "stop"):
            order_type = None
        mongo.price_alerts.update_one(
            {"mysql_alert_id": int(row["id"])},
            {
                "$set": {
                    "mysql_alert_id": int(row["id"]),
                    "mysql_user_id": int(row["user_id"]),
                    "user_id": uoid,
                    "user_email": row.get("user_email") or "",
                    "coin_id": (row.get("coin_id") or "").lower(),
                    "target_price": d128(row.get("target_price", 0)),
                    "alert_type": row.get("alert_type") or "above",
                    "order_type": order_type,
                    "created_at": to_dt(row.get("created_at")) or datetime.now(),
                    "notified": bool(row.get("notified")),
                    "note": row.get("note"),
                    "snoozed_until": to_dt(row.get("snoozed_until")),
                    "triggered_at": to_dt(row.get("triggered_at")),
                    "trigger_price": d128(row.get("trigger_price", 0)) if row.get("trigger_price") is not None else None,
                }
            },
            upsert=True,
        )

    # notifications
    mysql_cur.execute("SELECT id, user_id, coin_id, message, created_at, is_read FROM notifications")
    for row in mysql_cur.fetchall() or []:
        uoid = user_oid(row["user_id"])
        if not uoid:
            continue
        mongo.notifications.update_one(
            {"mysql_notification_id": int(row["id"])},
            {
                "$set": {
                    "mysql_notification_id": int(row["id"]),
                    "mysql_user_id": int(row["user_id"]),
                    "user_id": uoid,
                    "coin_id": (row.get("coin_id") or "").lower() if row.get("coin_id") else None,
                    "message": row.get("message") or "",
                    "created_at": to_dt(row.get("created_at")) or datetime.now(),
                    "is_read": bool(row.get("is_read")),
                }
            },
            upsert=True,
        )

    # risk_assessments
    mysql_cur.execute(
        """
        SELECT id, user_id, financial_score, knowledge_score, psychological_score,
               goals_score, total_score, risk_category, responses, ai_analysis, completed_at
        FROM risk_assessments
        """
    )
    for row in mysql_cur.fetchall() or []:
        uoid = user_oid(row["user_id"])
        if not uoid:
            continue
        mongo.risk_assessments.update_one(
            {"mysql_assessment_id": int(row["id"])},
            {
                "$set": {
                    "mysql_assessment_id": int(row["id"]),
                    "mysql_user_id": int(row["user_id"]),
                    "user_id": uoid,
                    "financial_score": d128(row.get("financial_score", 0)),
                    "knowledge_score": d128(row.get("knowledge_score", 0)),
                    "psychological_score": d128(row.get("psychological_score", 0)),
                    "goals_score": d128(row.get("goals_score", 0)),
                    "total_score": d128(row.get("total_score", 0)),
                    "risk_category": row.get("risk_category") or "",
                    "responses": parse_json_field(row.get("responses"), {}),
                    "ai_analysis": parse_json_field(row.get("ai_analysis"), {}),
                    "completed_at": to_dt(row.get("completed_at")) or datetime.now(),
                }
            },
            upsert=True,
        )

    # learning_profiles
    mysql_cur.execute("SELECT * FROM learning_profiles")
    for row in mysql_cur.fetchall() or []:
        uoid = user_oid(row["user_id"])
        if not uoid:
            continue
        existing_doc = mongo.learning_profiles.find_one({"user_id": uoid})
        filter_doc = (
            {"_id": existing_doc["_id"]}
            if existing_doc
            else {"mysql_learning_profile_id": int(row["id"])}
        )
        mongo.learning_profiles.update_one(
            filter_doc,
            {
                "$set": {
                    "mysql_learning_profile_id": int(row["id"]),
                    "mysql_user_id": int(row["user_id"]),
                    "user_id": uoid,
                    "skill_level": row.get("skill_level") or "beginner",
                    "total_trades": int(row.get("total_trades") or 0),
                    "winning_trades": int(row.get("winning_trades") or 0),
                    "losing_trades": int(row.get("losing_trades") or 0),
                    "win_rate": d128(row.get("win_rate", 0)),
                    "avg_profit_per_trade": d128(row.get("avg_profit_per_trade", 0)),
                    "avg_loss_per_trade": d128(row.get("avg_loss_per_trade", 0)),
                    "uses_stop_loss_percent": d128(row.get("uses_stop_loss_percent", 0)),
                    "avg_leverage_used": d128(row.get("avg_leverage_used", 1)),
                    "biggest_mistake": row.get("biggest_mistake"),
                    "weak_areas": parse_json_field(row.get("weak_areas"), []),
                    "completed_lessons": parse_json_field(row.get("completed_lessons"), []),
                    "quiz_scores": parse_json_field(row.get("quiz_scores"), {}),
                    "total_learning_time": int(row.get("total_learning_time") or 0),
                    "last_active": to_dt(row.get("last_active")) or datetime.now(),
                    "created_at": to_dt(row.get("created_at")) or datetime.now(),
                }
            },
            upsert=True,
        )

    # knowledge_documents
    mysql_cur.execute("SELECT * FROM knowledge_documents")
    for row in mysql_cur.fetchall() or []:
        existing_doc = mongo.knowledge_documents.find_one({"doc_id": row.get("doc_id") or ""})
        filter_doc = (
            {"_id": existing_doc["_id"]}
            if existing_doc
            else {"mysql_knowledge_doc_id": int(row["id"])}
        )
        mongo.knowledge_documents.update_one(
            filter_doc,
            {
                "$set": {
                    "mysql_knowledge_doc_id": int(row["id"]),
                    "doc_id": row.get("doc_id") or "",
                    "title": row.get("title") or "",
                    "category": row.get("category") or "crypto_basics",
                    "subcategory": row.get("subcategory"),
                    "file_path": row.get("file_path") or "",
                    "content_preview": row.get("content_preview"),
                    "difficulty": row.get("difficulty") or "beginner",
                    "word_count": int(row.get("word_count") or 0),
                    "indexed_at": to_dt(row.get("indexed_at")) or datetime.now(),
                    "updated_at": to_dt(row.get("updated_at")) or datetime.now(),
                }
            },
            upsert=True,
        )

    # ai_conversations
    mysql_cur.execute("SELECT * FROM ai_conversations")
    for row in mysql_cur.fetchall() or []:
        uoid = user_oid(row["user_id"])
        if not uoid:
            continue
        mongo.ai_conversations.update_one(
            {"mysql_ai_conversation_id": int(row["id"])},
            {
                "$set": {
                    "mysql_ai_conversation_id": int(row["id"]),
                    "mysql_user_id": int(row["user_id"]),
                    "user_id": uoid,
                    "session_id": row.get("session_id") or "",
                    "user_question": row.get("user_question") or "",
                    "user_skill_level": row.get("user_skill_level"),
                    "retrieved_docs": parse_json_field(row.get("retrieved_docs"), []),
                    "ai_response": row.get("ai_response") or "",
                    "response_time_ms": int(row.get("response_time_ms")) if row.get("response_time_ms") is not None else None,
                    "user_rating": int(row.get("user_rating")) if row.get("user_rating") is not None else None,
                    "user_feedback": row.get("user_feedback"),
                    "created_at": to_dt(row.get("created_at")) or datetime.now(),
                }
            },
            upsert=True,
        )

    # learning_progress
    mysql_cur.execute("SELECT * FROM learning_progress")
    for row in mysql_cur.fetchall() or []:
        uoid = user_oid(row["user_id"])
        if not uoid:
            continue
        existing_doc = mongo.learning_progress.find_one(
            {
                "user_id": uoid,
                "content_type": row.get("content_type") or "lesson",
                "content_id": row.get("content_id") or "",
            }
        )
        filter_doc = (
            {"_id": existing_doc["_id"]}
            if existing_doc
            else {"mysql_learning_progress_id": int(row["id"])}
        )
        mongo.learning_progress.update_one(
            filter_doc,
            {
                "$set": {
                    "mysql_learning_progress_id": int(row["id"]),
                    "mysql_user_id": int(row["user_id"]),
                    "user_id": uoid,
                    "content_type": row.get("content_type") or "lesson",
                    "content_id": row.get("content_id") or "",
                    "status": row.get("status") or "not_started",
                    "score": int(row.get("score")) if row.get("score") is not None else None,
                    "time_spent": int(row.get("time_spent") or 0),
                    "attempts": int(row.get("attempts") or 0),
                    "completed_at": to_dt(row.get("completed_at")),
                    "created_at": to_dt(row.get("created_at")) or datetime.now(),
                    "updated_at": to_dt(row.get("updated_at")) or datetime.now(),
                }
            },
            upsert=True,
        )

    # trade_mistakes
    mysql_cur.execute("SELECT * FROM trade_mistakes")
    for row in mysql_cur.fetchall() or []:
        uoid = user_oid(row["user_id"])
        if not uoid:
            continue
        tx_ref = tx_oid(row.get("transaction_id"))
        mongo.trade_mistakes.update_one(
            {"mysql_trade_mistake_id": int(row["id"])},
            {
                "$set": {
                    "mysql_trade_mistake_id": int(row["id"]),
                    "mysql_user_id": int(row["user_id"]),
                    "mysql_transaction_id": int(row["transaction_id"]) if row.get("transaction_id") is not None else None,
                    "user_id": uoid,
                    "transaction_id": tx_ref,
                    "mistake_type": row.get("mistake_type") or "fomo",
                    "severity": row.get("severity") or "moderate",
                    "loss_amount": d128(row.get("loss_amount", 0)) if row.get("loss_amount") is not None else None,
                    "ai_analysis": row.get("ai_analysis"),
                    "learned": bool(row.get("learned")),
                    "created_at": to_dt(row.get("created_at")) or datetime.now(),
                }
            },
            upsert=True,
        )

    # daily_challenges
    mysql_cur.execute("SELECT * FROM daily_challenges")
    for row in mysql_cur.fetchall() or []:
        uoid = user_oid(row["user_id"])
        if not uoid:
            continue
        existing_doc = mongo.daily_challenges.find_one(
            {
                "user_id": uoid,
                "challenge_type": row.get("challenge_type") or "",
                "challenge_date": to_dt(row.get("challenge_date")) or datetime.now(),
            }
        )
        filter_doc = (
            {"_id": existing_doc["_id"]}
            if existing_doc
            else {"mysql_daily_challenge_id": int(row["id"])}
        )
        mongo.daily_challenges.update_one(
            filter_doc,
            {
                "$set": {
                    "mysql_daily_challenge_id": int(row["id"]),
                    "mysql_user_id": int(row["user_id"]),
                    "user_id": uoid,
                    "challenge_date": to_dt(row.get("challenge_date")) or datetime.now(),
                    "challenge_type": row.get("challenge_type") or "",
                    "description": row.get("description") or "",
                    "target_metric": row.get("target_metric"),
                    "target_value": d128(row.get("target_value", 0)) if row.get("target_value") is not None else None,
                    "current_value": d128(row.get("current_value", 0) or 0),
                    "completed": bool(row.get("completed")),
                    "reward_crypto_bucks": d128(row.get("reward_crypto_bucks", 0) or 0),
                    "expires_at": to_dt(row.get("expires_at")) or datetime.now(),
                    "completed_at": to_dt(row.get("completed_at")),
                    "created_at": to_dt(row.get("created_at")) or datetime.now(),
                }
            },
            upsert=True,
        )

    # watchlist_scenarios
    mysql_cur.execute("SELECT * FROM watchlist_scenarios")
    for row in mysql_cur.fetchall() or []:
        uoid = user_oid(row["user_id"])
        if not uoid:
            continue
        mongo.watchlist_scenarios.update_one(
            {"mysql_watchlist_scenario_id": int(row["id"])},
            {
                "$set": {
                    "mysql_watchlist_scenario_id": int(row["id"]),
                    "mysql_user_id": int(row["user_id"]),
                    "user_id": uoid,
                    "coin_id": (row.get("coin_id") or "").lower(),
                    "replay_date": to_dt(row.get("replay_date")) or datetime.now(),
                    "entry_price": d128(row.get("entry_price", 0)),
                    "conservative_return": d128(row.get("conservative_return", 0)),
                    "rule_based_return": d128(row.get("rule_based_return", 0)),
                    "emotional_return": d128(row.get("emotional_return", 0)),
                    "best_strategy": row.get("best_strategy") or "",
                    "prep_score": int(row.get("prep_score") or 0),
                    "created_at": to_dt(row.get("created_at")) or datetime.now(),
                }
            },
            upsert=True,
        )

    # price_alert_history
    mysql_cur.execute("SELECT * FROM price_alert_history")
    for row in mysql_cur.fetchall() or []:
        uoid = user_oid(row["user_id"])
        if not uoid:
            continue
        a_oid = alert_oid(row.get("alert_id"))
        mongo.price_alert_history.update_one(
            {"mysql_price_alert_history_id": int(row["id"])},
            {
                "$set": {
                    "mysql_price_alert_history_id": int(row["id"]),
                    "mysql_user_id": int(row["user_id"]),
                    "mysql_alert_id": int(row["alert_id"]) if row.get("alert_id") is not None else None,
                    "user_id": uoid,
                    "alert_id": a_oid,
                    "coin_id": (row.get("coin_id") or "").lower(),
                    "target_price": d128(row.get("target_price", 0)),
                    "trigger_price": d128(row.get("trigger_price", 0)),
                    "alert_type": row.get("alert_type") or "above",
                    "note": row.get("note"),
                    "triggered_at": to_dt(row.get("triggered_at")) or datetime.now(),
                }
            },
            upsert=True,
        )

    mysql_cur.close()
    mysql_conn.close()
    print("MySQL to MongoDB full sync completed.")


if __name__ == "__main__":
    main()
