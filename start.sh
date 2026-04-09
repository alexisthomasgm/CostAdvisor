#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "$0")" && pwd)"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

cleanup() {
    echo -e "\n${RED}Shutting down...${NC}"
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
    wait $BACKEND_PID $FRONTEND_PID 2>/dev/null
    echo "Done."
}
trap cleanup EXIT INT TERM

# Check services
if ! pg_isready -q 2>/dev/null; then
    echo -e "${RED}PostgreSQL is not running. Start it first.${NC}"
    exit 1
fi

if ! redis-cli ping &>/dev/null; then
    echo -e "${RED}Redis is not running. Start it first.${NC}"
    exit 1
fi

# Start backend
echo -e "${GREEN}Starting backend on http://localhost:8000${NC}"
cd "$DIR/backend"
source venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

# Start frontend
echo -e "${GREEN}Starting frontend on http://localhost:5173${NC}"
cd "$DIR/frontend"
npx vite --host &
FRONTEND_PID=$!

echo -e "\n${GREEN}CostAdvisor is running! Press Ctrl+C to stop.${NC}\n"
wait
