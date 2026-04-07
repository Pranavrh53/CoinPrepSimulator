// MongoDB schema setup for crypto_tracker
// Run with: mongosh mongodb/schema.js

use('crypto_tracker');

function createCollectionWithValidator(name, validator) {
  const existing = db.getCollectionNames().includes(name);
  if (!existing) {
    db.createCollection(name, { validator, validationLevel: 'moderate' });
    print(`Created collection: ${name}`);
    return;
  }

  db.runCommand({
    collMod: name,
    validator,
    validationLevel: 'moderate'
  });
  print(`Updated validator: ${name}`);
}

createCollectionWithValidator('users', {
  $jsonSchema: {
    bsonType: 'object',
    required: ['username', 'email', 'password'],
    properties: {
      username: { bsonType: 'string', minLength: 1, maxLength: 50 },
      email: { bsonType: 'string', minLength: 3, maxLength: 100 },
      password: { bsonType: 'string', minLength: 1, maxLength: 255 },
      crypto_bucks: { bsonType: ['decimal', 'double', 'int', 'long'] },
      tether_balance: { bsonType: ['decimal', 'double', 'int', 'long'] },
      risk_tolerance: { bsonType: 'string', maxLength: 50 },
      risk_score: { bsonType: ['int', 'long', 'double', 'decimal'] },
      verification_code: { bsonType: ['string', 'null'], maxLength: 6 },
      verified: { bsonType: ['bool', 'int'] },
      achievements: { bsonType: ['array', 'string', 'null'] },
      last_assessment_id: { bsonType: ['objectId', 'null'] },
      last_assessment_date: { bsonType: ['date', 'null'] },
      created_at: { bsonType: 'date' }
    }
  }
});

createCollectionWithValidator('wallets', {
  $jsonSchema: {
    bsonType: 'object',
    required: ['user_id', 'name'],
    properties: {
      user_id: { bsonType: 'objectId' },
      name: { bsonType: 'string', minLength: 1, maxLength: 50 },
      created_at: { bsonType: 'date' }
    }
  }
});

createCollectionWithValidator('transactions', {
  $jsonSchema: {
    bsonType: 'object',
    required: ['user_id', 'wallet_id', 'coin_id', 'amount', 'price', 'type'],
    properties: {
      user_id: { bsonType: 'objectId' },
      wallet_id: { bsonType: 'objectId' },
      coin_id: { bsonType: 'string', minLength: 1, maxLength: 50 },
      amount: { bsonType: ['decimal', 'double', 'int', 'long'] },
      price: { bsonType: ['decimal', 'double', 'int', 'long'] },
      type: {
        enum: ['buy', 'sell', 'limit', 'market', 'stop']
      },
      sold_price: { bsonType: ['decimal', 'double', 'int', 'long', 'null'] },
      buy_transaction_id: { bsonType: ['objectId', 'null'] },
      timestamp: { bsonType: 'date' }
    }
  }
});

createCollectionWithValidator('watchlist', {
  $jsonSchema: {
    bsonType: 'object',
    required: ['user_id', 'coin_id'],
    properties: {
      user_id: { bsonType: 'objectId' },
      coin_id: { bsonType: 'string', minLength: 1, maxLength: 50 },
      added_at: { bsonType: 'date' }
    }
  }
});

createCollectionWithValidator('price_alerts', {
  $jsonSchema: {
    bsonType: 'object',
    required: ['user_id', 'user_email', 'coin_id', 'target_price', 'alert_type'],
    properties: {
      user_id: { bsonType: 'objectId' },
      user_email: { bsonType: 'string', minLength: 3, maxLength: 100 },
      coin_id: { bsonType: 'string', minLength: 1, maxLength: 50 },
      target_price: { bsonType: ['decimal', 'double', 'int', 'long'] },
      alert_type: { enum: ['above', 'below'] },
      order_type: { enum: ['limit', 'market', 'stop', null] },
      note: { bsonType: ['string', 'null'], maxLength: 500 },
      snoozed_until: { bsonType: ['date', 'null'] },
      triggered_at: { bsonType: ['date', 'null'] },
      trigger_price: { bsonType: ['decimal', 'double', 'int', 'long', 'null'] },
      created_at: { bsonType: 'date' },
      notified: { bsonType: ['bool', 'int'] }
    }
  }
});

createCollectionWithValidator('notifications', {
  $jsonSchema: {
    bsonType: 'object',
    required: ['user_id', 'message'],
    properties: {
      user_id: { bsonType: 'objectId' },
      coin_id: { bsonType: ['string', 'null'], maxLength: 50 },
      message: { bsonType: 'string' },
      created_at: { bsonType: 'date' },
      is_read: { bsonType: ['bool', 'int'] }
    }
  }
});

createCollectionWithValidator('trading_pairs', {
  $jsonSchema: {
    bsonType: 'object',
    required: ['base_currency', 'quote_currency', 'symbol'],
    properties: {
      base_currency: { bsonType: 'string', minLength: 1, maxLength: 20 },
      quote_currency: { bsonType: 'string', minLength: 1, maxLength: 20 },
      symbol: { bsonType: 'string', minLength: 1, maxLength: 20 },
      is_active: { bsonType: ['bool', 'int'] },
      created_at: { bsonType: 'date' }
    }
  }
});

createCollectionWithValidator('orders', {
  $jsonSchema: {
    bsonType: 'object',
    required: ['user_id', 'wallet_id', 'base_currency', 'quote_currency', 'order_type', 'side', 'amount', 'status'],
    properties: {
      user_id: { bsonType: 'objectId' },
      wallet_id: { bsonType: 'objectId' },
      pair_id: { bsonType: ['objectId', 'null'] },
      base_currency: { bsonType: 'string', minLength: 1, maxLength: 20 },
      quote_currency: { bsonType: 'string', minLength: 1, maxLength: 20 },
      order_type: { enum: ['market', 'limit', 'stop_loss', 'take_profit'] },
      side: { enum: ['buy', 'sell'] },
      amount: { bsonType: ['decimal', 'double', 'int', 'long'] },
      price: { bsonType: ['decimal', 'double', 'int', 'long', 'null'] },
      stop_price: { bsonType: ['decimal', 'double', 'int', 'long', 'null'] },
      filled_amount: { bsonType: ['decimal', 'double', 'int', 'long'] },
      status: { enum: ['pending', 'filled', 'cancelled', 'partially_filled'] },
      created_at: { bsonType: 'date' },
      filled_at: { bsonType: ['date', 'null'] },
      cancelled_at: { bsonType: ['date', 'null'] }
    }
  }
});

createCollectionWithValidator('order_fills', {
  $jsonSchema: {
    bsonType: 'object',
    required: ['order_id', 'user_id', 'filled_amount', 'filled_price'],
    properties: {
      order_id: { bsonType: 'objectId' },
      user_id: { bsonType: 'objectId' },
      filled_amount: { bsonType: ['decimal', 'double', 'int', 'long'] },
      filled_price: { bsonType: ['decimal', 'double', 'int', 'long'] },
      filled_at: { bsonType: 'date' }
    }
  }
});

createCollectionWithValidator('risk_assessments', {
  $jsonSchema: {
    bsonType: 'object',
    required: ['user_id', 'financial_score', 'knowledge_score', 'psychological_score', 'goals_score', 'total_score', 'risk_category', 'responses', 'ai_analysis'],
    properties: {
      user_id: { bsonType: 'objectId' },
      financial_score: { bsonType: ['decimal', 'double', 'int', 'long'] },
      knowledge_score: { bsonType: ['decimal', 'double', 'int', 'long'] },
      psychological_score: { bsonType: ['decimal', 'double', 'int', 'long'] },
      goals_score: { bsonType: ['decimal', 'double', 'int', 'long'] },
      total_score: { bsonType: ['decimal', 'double', 'int', 'long'] },
      risk_category: { bsonType: 'string', minLength: 1, maxLength: 50 },
      responses: { bsonType: 'object' },
      ai_analysis: { bsonType: 'object' },
      completed_at: { bsonType: 'date' }
    }
  }
});

createCollectionWithValidator('learning_profiles', {
  $jsonSchema: {
    bsonType: 'object',
    required: ['user_id'],
    properties: {
      user_id: { bsonType: 'objectId' },
      skill_level: { enum: ['beginner', 'intermediate', 'advanced'] },
      total_trades: { bsonType: ['int', 'long'] },
      winning_trades: { bsonType: ['int', 'long'] },
      losing_trades: { bsonType: ['int', 'long'] },
      win_rate: { bsonType: ['decimal', 'double', 'int', 'long'] },
      avg_profit_per_trade: { bsonType: ['decimal', 'double', 'int', 'long'] },
      avg_loss_per_trade: { bsonType: ['decimal', 'double', 'int', 'long'] },
      uses_stop_loss_percent: { bsonType: ['decimal', 'double', 'int', 'long'] },
      avg_leverage_used: { bsonType: ['decimal', 'double', 'int', 'long'] },
      biggest_mistake: { bsonType: ['string', 'null'], maxLength: 100 },
      weak_areas: { bsonType: ['array', 'string', 'null'] },
      completed_lessons: { bsonType: ['array', 'string', 'null'] },
      quiz_scores: { bsonType: ['object', 'string', 'null'] },
      total_learning_time: { bsonType: ['int', 'long'] },
      last_active: { bsonType: 'date' },
      created_at: { bsonType: 'date' }
    }
  }
});

createCollectionWithValidator('knowledge_documents', {
  $jsonSchema: {
    bsonType: 'object',
    required: ['doc_id', 'title', 'category', 'file_path'],
    properties: {
      doc_id: { bsonType: 'string', minLength: 1, maxLength: 100 },
      title: { bsonType: 'string', minLength: 1, maxLength: 255 },
      category: { enum: ['crypto_basics', 'trading_strategies', 'risk_management', 'psychology', 'case_studies', 'common_mistakes'] },
      subcategory: { bsonType: ['string', 'null'], maxLength: 100 },
      file_path: { bsonType: 'string', minLength: 1, maxLength: 500 },
      content_preview: { bsonType: ['string', 'null'] },
      difficulty: { enum: ['beginner', 'intermediate', 'advanced'] },
      word_count: { bsonType: ['int', 'long'] },
      indexed_at: { bsonType: 'date' },
      updated_at: { bsonType: 'date' }
    }
  }
});

createCollectionWithValidator('ai_conversations', {
  $jsonSchema: {
    bsonType: 'object',
    required: ['user_id', 'session_id', 'user_question', 'ai_response'],
    properties: {
      user_id: { bsonType: 'objectId' },
      session_id: { bsonType: 'string', minLength: 1, maxLength: 100 },
      user_question: { bsonType: 'string' },
      user_skill_level: { enum: ['beginner', 'intermediate', 'advanced', null] },
      retrieved_docs: { bsonType: ['array', 'string', 'null'] },
      ai_response: { bsonType: 'string' },
      response_time_ms: { bsonType: ['int', 'long', 'null'] },
      user_rating: { bsonType: ['int', 'null'] },
      user_feedback: { bsonType: ['string', 'null'] },
      created_at: { bsonType: 'date' }
    }
  }
});

createCollectionWithValidator('learning_progress', {
  $jsonSchema: {
    bsonType: 'object',
    required: ['user_id', 'content_type', 'content_id'],
    properties: {
      user_id: { bsonType: 'objectId' },
      content_type: { enum: ['lesson', 'quiz', 'challenge', 'trade_analysis'] },
      content_id: { bsonType: 'string', minLength: 1, maxLength: 100 },
      status: { enum: ['not_started', 'in_progress', 'completed'] },
      score: { bsonType: ['int', 'long', 'null'] },
      time_spent: { bsonType: ['int', 'long'] },
      attempts: { bsonType: ['int', 'long'] },
      completed_at: { bsonType: ['date', 'null'] },
      created_at: { bsonType: 'date' },
      updated_at: { bsonType: 'date' }
    }
  }
});

createCollectionWithValidator('trade_mistakes', {
  $jsonSchema: {
    bsonType: 'object',
    required: ['user_id', 'mistake_type'],
    properties: {
      user_id: { bsonType: 'objectId' },
      transaction_id: { bsonType: ['objectId', 'null'] },
      mistake_type: { enum: ['no_stop_loss', 'high_leverage', 'emotional_trading', 'poor_timing', 'no_research', 'overtrading', 'fomo', 'panic_sell'] },
      severity: { enum: ['minor', 'moderate', 'severe'] },
      loss_amount: { bsonType: ['decimal', 'double', 'int', 'long', 'null'] },
      ai_analysis: { bsonType: ['string', 'null'] },
      learned: { bsonType: ['bool', 'int'] },
      created_at: { bsonType: 'date' }
    }
  }
});

createCollectionWithValidator('daily_challenges', {
  $jsonSchema: {
    bsonType: 'object',
    required: ['user_id', 'challenge_date', 'challenge_type', 'description', 'expires_at'],
    properties: {
      user_id: { bsonType: 'objectId' },
      challenge_date: { bsonType: 'date' },
      challenge_type: { bsonType: 'string', minLength: 1, maxLength: 50 },
      description: { bsonType: 'string' },
      target_metric: { bsonType: ['string', 'null'], maxLength: 100 },
      target_value: { bsonType: ['decimal', 'double', 'int', 'long', 'null'] },
      current_value: { bsonType: ['decimal', 'double', 'int', 'long'] },
      completed: { bsonType: ['bool', 'int'] },
      reward_crypto_bucks: { bsonType: ['decimal', 'double', 'int', 'long'] },
      expires_at: { bsonType: 'date' },
      completed_at: { bsonType: ['date', 'null'] },
      created_at: { bsonType: 'date' }
    }
  }
});

createCollectionWithValidator('watchlist_scenarios', {
  $jsonSchema: {
    bsonType: 'object',
    required: ['user_id', 'coin_id', 'replay_date', 'entry_price', 'conservative_return', 'rule_based_return', 'emotional_return', 'best_strategy', 'prep_score'],
    properties: {
      user_id: { bsonType: 'objectId' },
      coin_id: { bsonType: 'string', minLength: 1, maxLength: 64 },
      replay_date: { bsonType: 'date' },
      entry_price: { bsonType: ['decimal', 'double', 'int', 'long'] },
      conservative_return: { bsonType: ['decimal', 'double', 'int', 'long'] },
      rule_based_return: { bsonType: ['decimal', 'double', 'int', 'long'] },
      emotional_return: { bsonType: ['decimal', 'double', 'int', 'long'] },
      best_strategy: { bsonType: 'string', minLength: 1, maxLength: 64 },
      prep_score: { bsonType: ['int', 'long'] },
      created_at: { bsonType: 'date' }
    }
  }
});

createCollectionWithValidator('price_alert_history', {
  $jsonSchema: {
    bsonType: 'object',
    required: ['user_id', 'coin_id', 'target_price', 'trigger_price', 'alert_type', 'triggered_at'],
    properties: {
      user_id: { bsonType: 'objectId' },
      alert_id: { bsonType: ['objectId', 'null'] },
      coin_id: { bsonType: 'string', minLength: 1, maxLength: 50 },
      target_price: { bsonType: ['decimal', 'double', 'int', 'long'] },
      trigger_price: { bsonType: ['decimal', 'double', 'int', 'long'] },
      alert_type: { enum: ['above', 'below'] },
      note: { bsonType: ['string', 'null'], maxLength: 500 },
      triggered_at: { bsonType: 'date' }
    }
  }
});

// Indexes equivalent to SQL UNIQUE/INDEX constraints.
db.users.createIndex({ username: 1 }, { unique: true });
db.users.createIndex({ email: 1 }, { unique: true });

db.wallets.createIndex({ user_id: 1 });

db.transactions.createIndex({ user_id: 1, wallet_id: 1, timestamp: -1 });
db.transactions.createIndex({ buy_transaction_id: 1 });

db.watchlist.createIndex({ user_id: 1, coin_id: 1 }, { unique: true });

db.price_alerts.createIndex({ user_id: 1, created_at: -1 });
db.price_alerts.createIndex({ user_id: 1, coin_id: 1, alert_type: 1, target_price: 1 });

db.notifications.createIndex({ user_id: 1, created_at: -1 });

db.trading_pairs.createIndex({ base_currency: 1, quote_currency: 1 }, { unique: true });
db.trading_pairs.createIndex({ symbol: 1 }, { unique: true });
db.trading_pairs.createIndex({ is_active: 1 });

db.orders.createIndex({ user_id: 1, status: 1 });
db.orders.createIndex({ pair_id: 1, status: 1 });
db.orders.createIndex({ order_type: 1, status: 1 });
db.orders.createIndex({ status: 1, order_type: 1, base_currency: 1 });

db.order_fills.createIndex({ order_id: 1, filled_at: -1 });
db.order_fills.createIndex({ user_id: 1, filled_at: -1 });

db.risk_assessments.createIndex({ user_id: 1, completed_at: -1 });

db.learning_profiles.createIndex({ user_id: 1 }, { unique: true });

db.knowledge_documents.createIndex({ doc_id: 1 }, { unique: true });
db.knowledge_documents.createIndex({ category: 1 });
db.knowledge_documents.createIndex({ difficulty: 1 });

db.ai_conversations.createIndex({ user_id: 1, session_id: 1, created_at: -1 });
db.ai_conversations.createIndex({ created_at: -1 });

db.learning_progress.createIndex({ user_id: 1, status: 1 });
db.learning_progress.createIndex({ user_id: 1, content_type: 1, content_id: 1 }, { unique: true });

db.trade_mistakes.createIndex({ user_id: 1, learned: 1, created_at: -1 });

db.daily_challenges.createIndex({ user_id: 1, completed: 1, expires_at: 1 });
db.daily_challenges.createIndex({ user_id: 1, challenge_date: 1, challenge_type: 1 }, { unique: true });

db.watchlist_scenarios.createIndex({ user_id: 1, coin_id: 1, created_at: -1 });

db.price_alert_history.createIndex({ user_id: 1, triggered_at: -1 });

const viewName = 'user_risk_profiles_view';
const viewExists = db.getCollectionInfos({ name: viewName }).length > 0;
if (viewExists) {
  db[viewName].drop();
}

db.createView(
  viewName,
  'users',
  [
    {
      $lookup: {
        from: 'risk_assessments',
        let: { userId: '$_id' },
        pipeline: [
          { $match: { $expr: { $eq: ['$user_id', '$$userId'] } } },
          { $sort: { completed_at: -1 } },
          { $limit: 1 }
        ],
        as: 'latest_assessment'
      }
    },
    {
      $unwind: {
        path: '$latest_assessment',
        preserveNullAndEmptyArrays: true
      }
    },
    {
      $project: {
        user_id: '$_id',
        username: 1,
        email: 1,
        risk_tolerance: 1,
        risk_score: 1,
        assessment_id: '$latest_assessment._id',
        financial_score: '$latest_assessment.financial_score',
        knowledge_score: '$latest_assessment.knowledge_score',
        psychological_score: '$latest_assessment.psychological_score',
        goals_score: '$latest_assessment.goals_score',
        detailed_score: '$latest_assessment.total_score',
        risk_category: '$latest_assessment.risk_category',
        assessment_date: '$latest_assessment.completed_at'
      }
    }
  ]
);

print('MongoDB schema setup complete.');
