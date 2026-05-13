#!/usr/bin/env bash
set -euo pipefail

PROXY=${1:-http://localhost:9200}

# Simple test: fetch models
echo "Fetching tags/models..."
curl -sS "$PROXY/api/tags" | jq '.' || true

# Send a sample generate request (may fail depending on Ollama models available)
cat <<'JSON' > /tmp/sample.json
{
  "model": "llama3:8b",
  "prompt": "Say hello",
  "max_tokens": 16
}
JSON

echo "Sending sample /api/generate (may fail if model not present)"
curl -sS -X POST "$PROXY/api/generate" -H "Content-Type: application/json" -d @/tmp/sample.json | jq '.' || true

echo "Done. Check Prometheus at http://localhost:9090 for 'ollama_request' metrics and Grafana for dashboards." 
