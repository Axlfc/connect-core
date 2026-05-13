#!/bin/sh
# Improved zrok entrypoint with automatic environment reset
set -e

echo "=================================================="
echo "🚀 Zrok Tunnel Initialization"
echo "=================================================="

ZROK_ENV_DIR="${HOME}/.zrok"
ZROK_ENV_FILE="${ZROK_ENV_DIR}/environment.json"
ZROK_API_ENDPOINT="${ZROK_API_ENDPOINT:-https://api.zrok.io}"
ZROK_TARGET_URL="${ZROK_TARGET_URL:-http://nginx-proxy:80}"
ZROK_RESERVED_SHARE="${ZROK_RESERVED_SHARE:-}"

check_zrok_env() {
    if [ -f "${ZROK_ENV_FILE}" ]; then
        if zrok status >/dev/null 2>&1; then
            return 0
        fi
    fi
    return 1
}

reset_zrok_env() {
    echo "🧹 Resetting zrok environment..."
    zrok disable 2>/dev/null || true
    rm -rf "${ZROK_ENV_DIR}"
    mkdir -p "${ZROK_ENV_DIR}"
    echo "✅ Environment reset complete"
}

enable_zrok() {
    echo "🔐 Enabling zrok with authentication token..."
    
    if [ -z "${ZROK_AUTH_TOKEN}" ]; then
        echo "❌ ERROR: ZROK_AUTH_TOKEN is not set!"
        exit 1
    fi
    
    if ! zrok enable "${ZROK_AUTH_TOKEN}" --headless; then
        echo "❌ Failed to enable zrok"
        return 1
    fi
    
    echo "✅ Zrok enabled successfully"
    return 0
}

create_zrok_share() {
    echo "🌐 Creating zrok share for ${ZROK_TARGET_URL}..."
    
    if [ -n "${ZROK_RESERVED_SHARE}" ]; then
        echo "ℹ️  Attempting reserved share: ${ZROK_RESERVED_SHARE}"
        
        if ! zrok share reserved "${ZROK_RESERVED_SHARE}" --headless; then
            echo "⚠️  Reserved share failed, falling back to public..."
            ZROK_RESERVED_SHARE=""
        else
            echo "✅ Reserved share started"
            return 0
        fi
    fi
    
    echo "🌍 Creating public share..."
    exec zrok share public "${ZROK_TARGET_URL}" --headless
}

main() {
    echo ""
    echo "📋 Configuration:"
    echo "   API Endpoint:    ${ZROK_API_ENDPOINT}"
    echo "   Target URL:      ${ZROK_TARGET_URL}"
    echo "   Reserved Share:  ${ZROK_RESERVED_SHARE:-<none - will create public>}"
    echo ""
    
    if check_zrok_env; then
        echo "✅ Zrok environment is valid"
    else
        echo "⚠️  Zrok environment invalid or missing"
        reset_zrok_env
        
        if ! enable_zrok; then
            echo "❌ Failed to enable zrok"
            exit 1
        fi
    fi
    
    echo ""
    echo "🔍 Verifying zrok status..."
    if ! zrok status; then
        echo "⚠️  Status check failed, resetting..."
        reset_zrok_env
        
        if ! enable_zrok; then
            echo "❌ Failed after reset"
            exit 1
        fi
    fi
    
    echo ""
    echo "📊 Environment Information:"
    zrok status
    
    echo ""
    create_zrok_share
}

main
