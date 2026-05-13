#!/bin/bash
# Fix n8n file permissions issue
# This resolves "Attempt to read execution was blocked due to insufficient permissions"

set -e

echo "========================================="
echo "n8n Permissions Fix Script"
echo "========================================="
echo ""

# Get PUID and PGID from .env or use defaults
PUID=$(grep -E "^PUID=" .env 2>/dev/null | cut -d'=' -f2 || echo "1000")
PGID=$(grep -E "^PGID=" .env 2>/dev/null | cut -d'=' -f2 || echo "1000")

echo "Using PUID: $PUID"
echo "Using PGID: $PGID"
echo ""

# Stop n8n to fix permissions safely
echo "1. Stopping n8n container..."
docker compose stop n8n

echo ""
echo "2. Checking current permissions..."
docker run --rm -v n8n_storage:/data alpine ls -la /data | head -10

echo ""
echo "3. Fixing ownership of n8n storage volume..."
# Fix ownership of the entire volume
docker run --rm \
  -v n8n_storage:/data \
  alpine chown -R ${PUID}:${PGID} /data

echo ""
echo "4. Fixing config file permissions (was 0777, setting to 0600)..."
# The log shows: "Permissions 0777 for n8n settings file /home/node/.n8n/config are too wide"
docker run --rm \
  -v n8n_storage:/data \
  alpine sh -c "
    if [ -f /data/config ]; then
      chmod 600 /data/config
      echo 'Fixed /data/config permissions'
    fi
    if [ -d /data ]; then
      chmod 700 /data
      echo 'Fixed /data directory permissions'
    fi
  "

echo ""
echo "5. Verifying new permissions..."
docker run --rm -v n8n_storage:/data alpine ls -la /data | head -10

echo ""
echo "6. Restarting n8n..."
docker compose start n8n

echo ""
echo "========================================="
echo "Permissions fixed!"
echo "========================================="
echo ""
echo "Monitor the logs to verify:"
echo "  docker logs n8n -f"
echo ""
echo "You should no longer see:"
echo "  - 'Permissions 0777 for n8n settings file...'"
echo "  - 'Attempt to read execution was blocked...'"
echo ""
