#!/bin/bash

# Nextcloud Bot Startup Script
echo "🚀 Starting Nextcloud Bot Services..."

# Set timezone
export TZ=${TZ:-Asia/Ho_Chi_Minh}

# Create necessary directories
mkdir -p /app/logs /app/data /app/templates

# Function to handle shutdown
cleanup() {
    echo "🛑 Shutting down services..."
    kill $WEB_PID $BOT_PID 2>/dev/null
    wait
    exit 0
}

# Set up signal handlers
trap cleanup SIGTERM SIGINT

# Start web management interface in background
echo "🌐 Starting Web Management Interface on port 8080..."
python3 web_management.py &
WEB_PID=$!

# Wait a bit for web interface to start
sleep 5

# Check if web interface is running
if ! kill -0 $WEB_PID 2>/dev/null; then
    echo "❌ Web interface failed to start"
    exit 1
fi

echo "✅ Web Management Interface started (PID: $WEB_PID)"

# Start bot main process in background
echo "🤖 Starting Nextcloud Bot..."
python3 send_nextcloud_message.py &
BOT_PID=$!

# Wait a bit for bot to start
sleep 3

# Check if bot is running
if ! kill -0 $BOT_PID 2>/dev/null; then
    echo "⚠️ Bot failed to start, but web interface is still available"
    echo "📝 Check configuration in web interface"
else
    echo "✅ Nextcloud Bot started (PID: $BOT_PID)"
fi

echo "🎉 All services started successfully!"
echo "📊 Web Interface: http://localhost:8080"
echo "🔍 Health Check: http://localhost:8080/health"

# Keep the script running and monitor processes
while true; do
    # Check web interface
    if ! kill -0 $WEB_PID 2>/dev/null; then
        echo "❌ Web interface died, restarting..."
        python3 web_management.py &
        WEB_PID=$!
    fi
    
    # Check bot (optional, may not be running if not configured)
    if [ ! -z "$BOT_PID" ] && ! kill -0 $BOT_PID 2>/dev/null; then
        echo "⚠️ Bot process died"
        BOT_PID=""
    fi
    
    sleep 30
done
