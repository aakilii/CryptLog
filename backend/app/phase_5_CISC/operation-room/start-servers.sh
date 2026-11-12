#!/bin/bash

# Operation Room - Server Startup Script
# Starts both backend (FastAPI) and frontend (Next.js)

set -e

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║        Starting Operation Room Application Servers          ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
BACKEND_DIR="$SCRIPT_DIR/backend"
FRONTEND_DIR="$SCRIPT_DIR/frontend"

# Stop existing servers
echo "🛑 Stopping existing servers..."
pkill -f "uvicorn app.main:app" 2>/dev/null || true
# Note: Not killing frontend to avoid conflicts

# Start Backend
echo ""
echo "🚀 Starting Backend (FastAPI + Uvicorn)..."
cd "$BACKEND_DIR"
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found. Run setup first!"
    exit 1
fi

source venv/bin/activate
nohup uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 > /tmp/operation-room-backend.log 2>&1 &
BACKEND_PID=$!
echo "   ✅ Backend started (PID: $BACKEND_PID)"
echo "   📝 Logs: /tmp/operation-room-backend.log"

# Wait for backend to start
echo "   ⏳ Waiting for backend to be ready..."
for i in {1..10}; do
    if curl -s http://localhost:8000/docs > /dev/null 2>&1; then
        echo "   ✅ Backend is ready!"
        break
    fi
    sleep 1
done

# Start Frontend (if not already running)
echo ""
echo "🚀 Starting Frontend (Next.js)..."
if pgrep -f "next dev" > /dev/null; then
    echo "   ℹ️  Frontend already running"
else
    cd "$FRONTEND_DIR"
    
    # Load NVM if available
    export NVM_DIR="$HOME/.nvm"
    if [ -s "$NVM_DIR/nvm.sh" ]; then
        source "$NVM_DIR/nvm.sh"
        nvm use 18 2>/dev/null || echo "   ⚠️  Using system Node"
    fi
    
    nohup npm run dev > /tmp/operation-room-frontend.log 2>&1 &
    FRONTEND_PID=$!
    echo "   ✅ Frontend started (PID: $FRONTEND_PID)"
    echo "   📝 Logs: /tmp/operation-room-frontend.log"
    
    # Wait for frontend to start
    echo "   ⏳ Waiting for frontend to be ready..."
    for i in {1..15}; do
        if curl -s http://localhost:3000 > /dev/null 2>&1; then
            echo "   ✅ Frontend is ready!"
            break
        fi
        sleep 1
    done
fi

# Summary
echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                   🎉 SERVERS STARTED                         ║"
echo "╠══════════════════════════════════════════════════════════════╣"
echo "║                                                              ║"
echo "║  Backend (API):      http://localhost:8000                   ║"
echo "║  API Docs:           http://localhost:8000/docs              ║"
echo "║  Frontend (UI):      http://localhost:3000                   ║"
echo "║                                                              ║"
echo "║  Backend Logs:       /tmp/operation-room-backend.log        ║"
echo "║  Frontend Logs:      /tmp/operation-room-frontend.log       ║"
echo "║                                                              ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "📌 Quick Commands:"
echo "   • View backend logs:  tail -f /tmp/operation-room-backend.log"
echo "   • View frontend logs: tail -f /tmp/operation-room-frontend.log"
echo "   • Stop servers:       ./stop-servers.sh"
echo ""
