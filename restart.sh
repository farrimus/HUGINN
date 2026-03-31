#!/bin/bash
# Restart the uvicorn server in the background and tail the log.
# Usage: ./restart.sh

cd /opt/eve-frontier

pkill -f "uvicorn main:app" 2>/dev/null && echo "Stopped existing server." || echo "No server running."
sleep 1

# Build and deploy frontend
echo "Building frontend..."
cd frontend && npm run build --silent && rm -rf ../static/companion/assets && cp -r dist/* ../static/companion/ && echo "Frontend deployed." || echo "Frontend build failed."
cd /opt/eve-frontier

source .venv/bin/activate
nohup uvicorn main:app --host 0.0.0.0 --port 8745 >> uvicorn.log 2>&1 &
SERVER_PID=$!
echo "Server started (pid $SERVER_PID)."
sleep 2
tail -20 uvicorn.log
echo ""
echo "To watch live: tail -f /opt/eve-frontier/uvicorn.log"
