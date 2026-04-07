// MongoDB seed data for crypto_tracker
// Run after schema.js: mongosh mongodb/seed.js

use('crypto_tracker');

const now = new Date();

const admin = db.users.findOne({ username: 'admin' });
let adminId;

if (!admin) {
  const userInsert = db.users.insertOne({
    username: 'admin',
    email: 'admin@example.com',
    password: 'hashedpassword123',
    crypto_bucks: NumberDecimal('10000.00'),
    tether_balance: NumberDecimal('0'),
    risk_tolerance: 'Medium',
    risk_score: 0,
    verified: true,
    achievements: [],
    created_at: now
  });
  adminId = userInsert.insertedId;
  print('Inserted default admin user.');
} else {
  adminId = admin._id;
  print('Default admin user already exists.');
}

const walletNames = ['Default Wallet', 'Altcoin Wallet'];
for (const walletName of walletNames) {
  db.wallets.updateOne(
    { user_id: adminId, name: walletName },
    { $setOnInsert: { user_id: adminId, name: walletName, created_at: now } },
    { upsert: true }
  );
}
print('Wallets seeded.');

const tradingPairs = [
  { base_currency: 'tether', quote_currency: 'cryptobucks', symbol: 'USDT/CB' },
  { base_currency: 'bitcoin', quote_currency: 'tether', symbol: 'BTC/USDT' },
  { base_currency: 'ethereum', quote_currency: 'tether', symbol: 'ETH/USDT' },
  { base_currency: 'binancecoin', quote_currency: 'tether', symbol: 'BNB/USDT' },
  { base_currency: 'ripple', quote_currency: 'tether', symbol: 'XRP/USDT' },
  { base_currency: 'cardano', quote_currency: 'tether', symbol: 'ADA/USDT' },
  { base_currency: 'solana', quote_currency: 'tether', symbol: 'SOL/USDT' },
  { base_currency: 'polkadot', quote_currency: 'tether', symbol: 'DOT/USDT' },
  { base_currency: 'dogecoin', quote_currency: 'tether', symbol: 'DOGE/USDT' },
  { base_currency: 'avalanche-2', quote_currency: 'tether', symbol: 'AVAX/USDT' }
];

for (const pair of tradingPairs) {
  db.trading_pairs.updateOne(
    { base_currency: pair.base_currency, quote_currency: pair.quote_currency },
    {
      $setOnInsert: {
        ...pair,
        is_active: true,
        created_at: now
      }
    },
    { upsert: true }
  );
}
print('Trading pairs seeded.');

const knowledgeDocs = [
  {
    doc_id: 'crypto_basics_001',
    title: 'What is Cryptocurrency?',
    category: 'crypto_basics',
    difficulty: 'beginner',
    file_path: 'knowledge/lessons/crypto_basics_intro.md',
    content_preview: 'Cryptocurrency is a digital or virtual currency that uses cryptography for security...'
  },
  {
    doc_id: 'risk_mgmt_001',
    title: 'Stop Loss Orders Explained',
    category: 'risk_management',
    difficulty: 'beginner',
    file_path: 'knowledge/lessons/stop_loss_guide.md',
    content_preview: 'A stop loss is your safety net. It automatically sells your position when price drops...'
  },
  {
    doc_id: 'psychology_001',
    title: 'Emotional Trading and FOMO',
    category: 'psychology',
    difficulty: 'intermediate',
    file_path: 'knowledge/psychology/fomo_guide.md',
    content_preview: 'Fear Of Missing Out (FOMO) is the biggest killer of trading accounts...'
  }
];

for (const doc of knowledgeDocs) {
  db.knowledge_documents.updateOne(
    { doc_id: doc.doc_id },
    {
      $setOnInsert: {
        ...doc,
        word_count: 0,
        indexed_at: now,
        updated_at: now
      }
    },
    { upsert: true }
  );
}

print('Knowledge documents seeded.');
print('MongoDB seed completed.');
