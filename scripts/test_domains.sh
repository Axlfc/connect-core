#!/bin/bash

echo "Testing all Cognito domains..."
echo ""

DOMAINS=(
  "n8n.cognito.local"
  "comfyui.cognito.local"
  "forgejo.cognito.local"
  "git.cognito.local"
  "auth.cognito.local"
  "status.cognito.local"
)

for domain in "${DOMAINS[@]}"; do
  echo -n "Testing http://$domain ... "
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" "http://$domain")
  if [ "$STATUS" -eq 200 ]; then
    echo "✅ OK ($STATUS)"
  elif [ "$STATUS" -eq 301 ] || [ "$STATUS" -eq 302 ]; then
    LOCATION=$(curl -s -I "http://$domain" | grep -i "^location:" | cut -d' ' -f2 | tr -d '\r')
    echo "🔄 Redirect ($STATUS) → $LOCATION"
  else
    echo "❌ FAILED ($STATUS)"
  fi
done
