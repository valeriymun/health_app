#!/bin/bash
set -e

# Backend setup
cd /workspace/backend
pip install -r requirements.txt

# Create .env if it doesn't exist
if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created backend/.env — edit it with your API tokens"
fi

# Frontend setup
cd /workspace/frontend
npm install

echo ""
echo "============================================"
echo "  Setup complete!"
echo "  "
echo "  1. Edit backend/.env with your API tokens"
echo "  2. Run: bash start.sh"
echo "============================================"
