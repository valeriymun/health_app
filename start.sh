#!/bin/bash
# Start both backend and frontend

echo "Starting Health Dashboard..."

# Start backend in background
cd /workspace/backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!

# Start frontend
cd /workspace/frontend
npm run dev &
FRONTEND_PID=$!

echo ""
echo "Backend running on port 8000"
echo "Frontend running on port 3000"
echo ""
echo "Press Ctrl+C to stop both"

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null" EXIT
wait
