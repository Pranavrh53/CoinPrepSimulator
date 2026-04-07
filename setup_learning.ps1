# AI Learning Assistant - Quick Start Script
# Run this after setting up your Claude API key

Write-Host "🚀 AI Learning Assistant Setup" -ForegroundColor Cyan
Write-Host "================================`n" -ForegroundColor Cyan

# Check if API key is set
$apiKey = $env:ANTHROPIC_API_KEY
if (-not $apiKey) {
    Write-Host "❌ ANTHROPIC_API_KEY not found!" -ForegroundColor Red
    Write-Host "`nPlease set your Claude API key first:" -ForegroundColor Yellow
    Write-Host '  $env:ANTHROPIC_API_KEY="sk-ant-your-key-here"' -ForegroundColor White
    Write-Host "`nOr add it permanently to System Environment Variables`n" -ForegroundColor Yellow
    exit 1
}

Write-Host "✅ API key found: $($apiKey.Substring(0,15))..." -ForegroundColor Green

# Check if MySQL is accessible
Write-Host "`n📊 Checking database connection..." -ForegroundColor Cyan
try {
    $mysqlCheck = mysql -u root -pPranavrh123$ -e "USE crypto_tracker; SELECT 1;" 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ Database connection successful" -ForegroundColor Green
    } else {
        Write-Host "⚠️  Database connection failed" -ForegroundColor Yellow
        Write-Host "   Make sure MySQL is running" -ForegroundColor Yellow
    }
} catch {
    Write-Host "⚠️  Could not verify database" -ForegroundColor Yellow
}

# Install dependencies
Write-Host "`n📦 Installing Python dependencies..." -ForegroundColor Cyan
Write-Host "   This may take a few minutes..." -ForegroundColor Gray
pip install -r requirements.txt --quiet
if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Dependencies installed" -ForegroundColor Green
} else {
    Write-Host "⚠️  Some dependencies may have failed" -ForegroundColor Yellow
}

# Create database tables
Write-Host "`n🗄️  Setting up database tables..." -ForegroundColor Cyan
try {
    mysql -u root -pPranavrh123$ crypto_tracker < learning_system_schema.sql 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ Database tables created" -ForegroundColor Green
    } else {
        Write-Host "⚠️  Database setup may have failed (tables might already exist)" -ForegroundColor Yellow
    }
} catch {
    Write-Host "⚠️  Could not create tables" -ForegroundColor Yellow
}

# Check knowledge base
Write-Host "`n📚 Checking knowledge base..." -ForegroundColor Cyan
$knowledgeFiles = Get-ChildItem -Path "knowledge" -Filter "*.md" -Recurse -ErrorAction SilentlyContinue
if ($knowledgeFiles) {
    Write-Host "✅ Found $($knowledgeFiles.Count) knowledge documents" -ForegroundColor Green
} else {
    Write-Host "⚠️  No knowledge documents found" -ForegroundColor Yellow
}

Write-Host "`n" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan
Write-Host "✨ Setup Complete!" -ForegroundColor Green
Write-Host "================================`n" -ForegroundColor Cyan

Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "1. Start the app:" -ForegroundColor White
Write-Host "   python app.py`n" -ForegroundColor Gray

Write-Host "2. Index knowledge base:" -ForegroundColor White
Write-Host '   Invoke-WebRequest -Method POST -Uri "http://localhost:5000/learning/api/index-knowledge"`n' -ForegroundColor Gray

Write-Host "3. Visit Learning Hub:" -ForegroundColor White
Write-Host "   http://localhost:5000/learning/hub`n" -ForegroundColor Gray

Write-Host "4. Chat with AI Tutor:" -ForegroundColor White
Write-Host "   http://localhost:5000/learning/ai-tutor`n" -ForegroundColor Gray

Write-Host "📖 Full documentation: AI_LEARNING_SETUP.md`n" -ForegroundColor Cyan
