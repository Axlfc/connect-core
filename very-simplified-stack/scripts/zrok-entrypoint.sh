#!/bin/sh
# Improved zrok entrypoint with automatic environment reset
# This script handles zrok initialization and share creation automatically

set -e

echo "=================================================="
echo "🚀 Zrok Tunnel Initialization"
echo "=================================================="

# Configuration from environment variables
ZROK_ENV_DIR="${HOME}/.zrok"
ZROK_ENV_FILE="${ZROK_ENV_DIR}/environment.json"
ZROK_API_ENDPOINT="${ZROK_API_ENDPOINT:-https://api.zrok.io}"
ZROK_TARGET_URL="${ZROK_TARGET_URL:-http://nginx-proxy:80}"
ZROK_RESERVED_SHARE="${ZROK_RESERVED_SHARE:-}"

# Function to check if zrok environment exists and is valid
check_zrok_env() {
    if [ -f "${ZROK_ENV_FILE}" ]; then
        if zrok status >/dev/null 2>&1; then
            return 0
        fi
    fi
    return 1
}

# Function to disable and cleanup zrok environment
reset_zrok_env() {
    echo "🧹 Resetting zrok environment..."

    # Try to disable gracefully
    zrok disable 2>/dev/null || true

    # Force cleanup of environment directory
    rm -rf "${ZROK_ENV_DIR}"
    mkdir -p "${ZROK_ENV_DIR}"

    echo "✅ Environment reset complete"
}

# Function to enable zrok with token
enable_zrok() {
    echo "🔐 Enabling zrok with authentication token..."

    if [ -z "${ZROK_AUTH_TOKEN}" ]; then
        echo "❌ ERROR: ZROK_AUTH_TOKEN is not set!"
        echo "   Please set the ZROK_AUTH_TOKEN environment variable"
        exit 1
    fi

    # Enable zrok with the API endpoint
    if ! zrok enable "${ZROK_AUTH_TOKEN}" --headless; then
        echo "❌ Failed to enable zrok"
        return 1
    fi

    echo "✅ Zrok enabled successfully"
    return 0
}

# Function to create zrok share
create_zrok_share() {
    echo "🌐 Creating zrok share for ${ZROK_TARGET_URL}..."

    # Check if we should use a reserved share
    if [ -n "${ZROK_RESERVED_SHARE}" ]; then
        echo "ℹ️  Attempting to use reserved share: ${ZROK_RESERVED_SHARE}"

        # Try to start reserved share
        if ! zrok share reserved "${ZROK_RESERVED_SHARE}" --headless; then
            echo "⚠️  Reserved share failed (it may not exist or be invalid)"
            echo "ℹ️  Falling back to public share..."
            ZROK_RESERVED_SHARE=""
        else
            echo "✅ Reserved share started successfully"
            return 0
        fi
    fi

    # If no reserved share or it failed, create public share
    echo "🌍 Creating public share..."
    exec zrok share public "${ZROK_TARGET_URL}" --headless
}

# Main initialization flow
main() {
    echo ""
    echo "📋 Configuration:"
    echo "   API Endpoint:    ${ZROK_API_ENDPOINT}"
    echo "   Target URL:      ${ZROK_TARGET_URL}"
    echo "   Reserved Share:  ${ZROK_RESERVED_SHARE:-<none>}"
    echo ""

    # Step 1: Check if environment exists and is valid
    if check_zrok_env; then
        echo "✅ Zrok environment is already configured"
    else
        echo "⚠️  Zrok environment not found or invalid"

        # Reset and re-enable
        reset_zrok_env

        if ! enable_zrok; then
            echo "❌ Failed to enable zrok environment"
            exit 1
        fi
    fi

    # Step 2: Verify zrok status
    echo ""
    echo "🔍 Verifying zrok status..."
    if ! zrok status; then
        echo "❌ Zrok environment verification failed"
        echo "ℹ️  Attempting to reset and re-enable..."

        reset_zrok_env

        if ! enable_zrok; then
            echo "❌ Failed to enable zrok after reset"
            exit 1
        fi
    fi

    # Step 3: Show environment info
    echo ""
    echo "📊 Environment Information:"
    zrok status

    # Step 4: Create the share
    echo ""
    create_zrok_share
}

# Run main function
main
