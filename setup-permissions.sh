#!/bin/bash
set -e

# Colors for output
BLUE='\033[0;34m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}🚀 Setting up permissions for Docker volumes...${NC}"
echo -e "${BLUE}================================================${NC}"

# List of all log directories to be created
LOG_DIRS=(
    "n8n"
    "n8n-runner"
    "postgres"
    "qdrant"
    "ollama"
    "redis"
    "whisper-stt"
    "kokoro-tts"
    "voice-gateway"
    "forgejo"
    "forgejo-db"
    "matrix-synapse"
    "matrix-postgres"
    "nginx"
    "libretranslate"
    "languagetool"
)

# --- Load Environment Variables ---
# Source the .env file if it exists to get the correct UIDs and GIDs
if [ -f .env ]; then
    echo "📄 Sourcing variables from .env file..."
    set -a # automatically export all variables
    source .env
    set +a
else
    echo "⚠️  .env file not found. Using default UID/GID values (999)."
fi

# Set User and Group IDs, using defaults if not specified in .env
POSTGRES_UID=${POSTGRES_USER_ID:-999}
POSTGRES_GID=${POSTGRES_GROUP_ID:-999}
REDIS_UID=${REDIS_USER_ID:-999}
REDIS_GID=${REDIS_GROUP_ID:-999}
# Forgejo and Matrix DBs use the same postgres user IDs
FORGEJO_DB_UID=${POSTGRES_USER_ID:-999}
FORGEJO_DB_GID=${POSTGRES_GROUP_ID:-999}
MATRIX_DB_UID=${POSTGRES_USER_ID:-999}
MATRIX_DB_GID=${POSTGRES_GROUP_ID:-999}

echo ""

# Create log directories
echo "Creating log directories in ./logs ..."
for dir in "${LOG_DIRS[@]}"; do
    mkdir -p "./logs/$dir"
    echo "  - Created ./logs/$dir"
done
echo -e "${GREEN}✅ All log directories created.${NC}"
echo ""

# Set permissions for specific services
echo "Setting special permissions for bind-mounted log directories..."

# Change ownership for PostgreSQL directories
echo "  - Setting ownership for PostgreSQL logs to $POSTGRES_UID:$POSTGRES_GID"
sudo chown -R $POSTGRES_UID:$POSTGRES_GID ./logs/postgres
sudo chown -R $FORGEJO_DB_UID:$FORGEJO_DB_GID ./logs/forgejo-db
sudo chown -R $MATRIX_DB_UID:$MATRIX_DB_GID ./logs/matrix-postgres

# Change ownership for Redis directory
echo "  - Setting ownership for Redis logs to $REDIS_UID:$REDIS_GID"
sudo chown -R $REDIS_UID:$REDIS_GID ./logs/redis

echo -e "${GREEN}✅ Permissions set successfully!${NC}"
echo ""
echo "You can now start the stack with ./start.sh"
echo ""
