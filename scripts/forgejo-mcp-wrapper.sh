#!/bin/sh
set -e
export FORGEJOMCP_TOKEN=$(cat /run/secrets/forgejo_mcp_token)
exec /forgejo-mcp stdio
