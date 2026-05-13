#!/bin/bash
set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}================================================"
echo "⚙️  Setup Environment for Simplified Stack"
echo -e "================================================${NC}"

if [ -f ".env" ]; then
    echo -e "${YELLOW}⚠️  .env file already exists. Skipping generation to avoid overwriting.${NC}"
    exit 0
fi

if [ ! -f ".env.example" ]; then
    echo "❌ .env.example not found!"
    exit 1
fi

echo "📝 Creating .env from .env.example..."
cp .env.example .env

generate_random() {
    openssl rand -hex 16
}

echo "🔐 Generating unique keys..."

# Replace placeholders with random values
N8N_KEY=$(generate_random)
N8N_TOKEN=$(generate_random)
REDIS_PASS=$(generate_random)

# Use sed to update values
# Note: Using a temporary file for compatibility with different sed versions
sed -i "s/your_encryption_key_here/$N8N_KEY/" .env
sed -i "s/your_runner_token_here/$N8N_TOKEN/" .env
sed -i "s/redis_password/$REDIS_PASS/" .env

echo -e "${GREEN}✅ .env file created with secure random keys.${NC}"
echo -e "${BLUE}ℹ️  You can now run ./scripts/start.sh${NC}"
