#!/bin/sh
set -e

# Path to the homeserver.yaml
CONFIG_FILE=/data/homeserver.yaml

# Check if the database password secret exists
if [ -f /run/secrets/matrix_db_password ]; then
  DB_PASSWORD=$(cat /run/secrets/matrix_db_password)
  sed -i "s/password: \"REPLACE_WITH_DB_SECRET\"/password: \"$DB_PASSWORD\"/" $CONFIG_FILE
else
  echo "ERROR: Matrix DB password secret not found"
  exit 1
fi

# Check if the Redis password secret exists
if [ -f /run/secrets/redis_password ]; then
  REDIS_PASSWORD=$(cat /run/secrets/redis_password)
  sed -i "s/password: \"REPLACE_WITH_REDIS_SECRET\"/password: \"$REDIS_PASSWORD\"/" $CONFIG_FILE
else
  echo "ERROR: Redis password secret not found"
  exit 1
fi

# Execute the original Synapse entrypoint
exec /start.py start
