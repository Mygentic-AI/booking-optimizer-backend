#!/bin/bash

# Kill any existing agents
echo "Stopping existing agents..."
pkill -f "python.*app.py" || true
pkill -f "python.*basic_agent" || true
pkill -f "multiprocessing.*spawn" || true
sleep 2

# Start new agent
echo "Starting agent..."
source venv/bin/activate
nohup python app.py dev > logs/agent.log 2>&1 &

# Wait and check if started
sleep 3
if pgrep -f "python.*app.py" > /dev/null; then
    echo "Agent started successfully!"
    echo "Logs: tail -f logs/agent.log"
else
    echo "Failed to start agent. Check logs/agent.log"
    tail -20 logs/agent.log
fi