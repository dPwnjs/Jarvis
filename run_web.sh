#!/bin/bash
# Move to script directory
cd "$(dirname "$0")"

# Activate virtual environment
if [ -d "venv" ]; then
    source venv/bin/activate
else
    echo "❌ 가상환경(venv)을 찾을 수 없습니다."
    exit 1
fi

# Clean up any previously running server on port 8000 or 8001
OLD_PID=$(lsof -ti :8000,8001 2>/dev/null)
if [ -n "$OLD_PID" ]; then
    echo "🔄 기존에 실행 중이던 웹 서버(PID: $OLD_PID)를 정리하고 새로 시작합니다..."
    kill -9 $OLD_PID 2>/dev/null
    sleep 0.8
fi
killall cloudflared 2>/dev/null || true

echo "🚀 J.A.R.V.I.S. 웹 서버를 실행합니다..."
echo "🌐 브라우저에서 http://localhost:8000 로 자동 접속합니다."

# Open browser after 1 second in background
(sleep 1.2 && open "http://localhost:8000") &

# Start Web Server
python web_jarvis.py
