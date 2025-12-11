#!/bin/bash
# Production deployment script for Gemini Agent
# Designed for 13,000+ concurrent users

set -e

echo "🚀 Starting Gemini Agent in production mode..."

# Check environment
if [ ! -f .env ]; then
    echo "❌ Error: .env file not found"
    exit 1
fi

# Export environment variables
export $(cat .env | grep -v '^#' | xargs)

# Configuration for high concurrency
export WORKERS=${WORKERS:-9}  # (2 x 4 cores) + 1
export DATABASE_POOL_MIN=${DATABASE_POOL_MIN:-20}
export DATABASE_POOL_MAX=${DATABASE_POOL_MAX:-100}
export RATE_LIMIT_REQUESTS=${RATE_LIMIT_REQUESTS:-100}

echo "📊 Configuration:"
echo "   Workers: $WORKERS"
echo "   DB Pool: $DATABASE_POOL_MIN - $DATABASE_POOL_MAX"
echo "   Rate Limit: $RATE_LIMIT_REQUESTS req/min"

# Start with Gunicorn for HTTP server
# Slack bot runs in a separate process
echo "🔄 Starting services..."

# Start Slack bot in background
python main.py slack &
SLACK_PID=$!
echo "   Slack bot PID: $SLACK_PID"

# Start HTTP server with Gunicorn
gunicorn main:api \
    --config gunicorn.conf.py \
    --bind 0.0.0.0:8000

# Cleanup on exit
trap "kill $SLACK_PID 2>/dev/null" EXIT
