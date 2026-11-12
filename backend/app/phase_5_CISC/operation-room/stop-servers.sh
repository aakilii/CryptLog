#!/bin/bash

# Operation Room - Server Shutdown Script
# Stops both backend and frontend servers

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║         Stopping Operation Room Application Servers         ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Stop Backend
echo "🛑 Stopping Backend..."
BACKEND_PIDS=$(pgrep -f "uvicorn app.main:app")
if [ -n "$BACKEND_PIDS" ]; then
    echo "$BACKEND_PIDS" | xargs kill -9 2>/dev/null
    echo "   ✅ Backend stopped"
else
    echo "   ℹ️  Backend not running"
fi

# Stop Frontend
echo ""
echo "🛑 Stopping Frontend..."
FRONTEND_PIDS=$(pgrep -f "next dev")
if [ -n "$FRONTEND_PIDS" ]; then
    echo "$FRONTEND_PIDS" | xargs kill -9 2>/dev/null
    echo "   ✅ Frontend stopped"
else
    echo "   ℹ️  Frontend not running"
fi

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                   ✅ ALL SERVERS STOPPED                     ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
