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

# Run Jarvis
python main.py
