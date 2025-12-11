# Production deployment script for Windows
# Designed for 13,000+ concurrent users

Write-Host "🚀 Starting Gemini Agent in production mode..." -ForegroundColor Green

# Check environment
if (-not (Test-Path ".env")) {
    Write-Host "❌ Error: .env file not found" -ForegroundColor Red
    exit 1
}

# Load environment variables
Get-Content .env | ForEach-Object {
    if ($_ -match '^([^#][^=]+)=(.*)$') {
        [Environment]::SetEnvironmentVariable($matches[1], $matches[2], "Process")
    }
}

# Configuration
$env:WORKERS = if ($env:WORKERS) { $env:WORKERS } else { "9" }
$env:DATABASE_POOL_MIN = if ($env:DATABASE_POOL_MIN) { $env:DATABASE_POOL_MIN } else { "20" }
$env:DATABASE_POOL_MAX = if ($env:DATABASE_POOL_MAX) { $env:DATABASE_POOL_MAX } else { "100" }

Write-Host "📊 Configuration:" -ForegroundColor Cyan
Write-Host "   Workers: $env:WORKERS"
Write-Host "   DB Pool: $env:DATABASE_POOL_MIN - $env:DATABASE_POOL_MAX"

# Start both services
Write-Host "🔄 Starting services..." -ForegroundColor Yellow

# Option 1: Run combined (Slack + HTTP)
python main.py all

# Option 2: Run separately (uncomment if needed)
# Start-Process -FilePath "python" -ArgumentList "main.py", "slack" -NoNewWindow
# python main.py server
