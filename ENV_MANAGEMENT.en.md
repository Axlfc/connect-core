# Environment Variable Management
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/Axlfc/connect-core/blob/master/ENV_MANAGEMENT.en.md)
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](https://github.com/Axlfc/connect-core/blob/master/ENV_MANAGEMENT.md)
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](https://github.com/Axlfc/connect-core/blob/master/ENV_MANAGEMENT.ca.md)
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](https://github.com/Axlfc/connect-core/blob/master/ENV_MANAGEMENT.zh-cn.md)


This project includes several scripts to manage environment variables intelligently and securely.

## 📁 Files

- **`.env`** - Actual file with your values (DO NOT commit to git)
- **`.env.example`** - Template with example values (DO commit)
- **`generate_env_example.sh`** - Generates .env.example from .env
- **`init_env.sh`** - Initializes .env from .env.example

## 🚀 Quick Start

### First time (new project user)

```bash
# 1. Initialize .env file
./init_env.sh

# 2. The script will automatically generate secure values and ask you for optional ones
# Follow the interactive instructions

# 3. Review and adjust if necessary
nano .env

# 4. Start the services
./start.sh --voice
```

### Automatic mode (CI/CD or scripting)

```bash
# Generate .env with secure values without interaction
./init_env.sh --auto

# Then configure optional variables manually
echo "TELEGRAM_BOT_TOKEN=your_token" >> .env
echo "ZROK_AUTH_TOKEN=your_token" >> .env
```

## 🔄 Workflow for Developers

### Update .env.example after changing .env

```bash
# Generates .env.example while preserving useful values
./generate_env_example.sh

# Review changes
git diff .env.example

# Commit if it looks good
git add .env.example
git commit -m "Update .env.example with new variables"
```

### Sync your .env with new variables

```bash
# If someone added new variables to the project
git pull

# Update your .env with the new variables
./init_env.sh
# Select 'n' to not overwrite existing ones
# Or manually:
cat .env.example >> .env
nano .env  # Remove duplicates and configure new ones
```

## 🎯 Behavior of generate_env_example.sh

This script is **intelligent** and preserves useful values:

### ✅ Variables that ARE PRESERVED:

1. **Predefined values** (technical configuration):
   ```bash
   WHISPER_MODEL=base.en
   REDIS_PORT=6379
   POSTGRES_USER_ID=999
   ```

2. **Example values** from the existing .env.example:
   ```bash
   WEBHOOK_URL=http://localhost:5678
   ZROK_API_ENDPOINT=https://api.zrok.io
   ```

3. **Values that look like documentation**:
   ```bash
   EXAMPLE_KEY=your_key_here
   TEST_VALUE=change_this
   ```

### 🔒 Variables that ARE EMPTIED:

Sensitive variables (containing these patterns):
- `*PASSWORD*`
- `*SECRET*`
- `*KEY*` (except predefined)
- `*TOKEN*`
- `*AUTH*`
- `*JWT*`

```bash
# Before in .env
POSTGRES_PASSWORD=my_super_secret_123

# After in .env.example
POSTGRES_PASSWORD=
```

## 📋 Usage Examples

### Example 1: First project setup

```bash
# Clone repository
git clone https://github.com/[YOUR_USER]/connect-core.git
cd connect-core

# Make scripts executable
chmod +x *.sh

# Initialize environment
./init_env.sh

# Expected output:
# ✅ Backup created: .env.backup.20250101_120000
# ℹ️  .env file created from .env.example
#
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Variable: N8N_ENCRYPTION_KEY
# Generated value: 8f4e3c2b1a9d8e7f...
# Use this value? (Y/n/customize): y
# ✅ N8N_ENCRYPTION_KEY configured
```

### Example 2: Add new variable to the project

```bash
# 1. Edit .env for testing
echo "NEW_FEATURE_API_KEY=test_value_123" >> .env

# 2. Test that it works
./start.sh

# 3. Generate updated .env.example
./generate_env_example.sh

# Output:
# 🔒 POSTGRES_PASSWORD (sensitive - emptied)
# ✓ WHISPER_MODEL (preserved)
# 🔒 NEW_FEATURE_API_KEY (sensitive - emptied)

# 4. Verify result
cat .env.example | grep NEW_FEATURE
# NEW_FEATURE_API_KEY=

# 5. Commit
git add .env.example
git commit -m "Add NEW_FEATURE_API_KEY configuration"
```

### Example 3: Add new predefined value

```bash
# Edit generate_env_example.sh
# Add to EXAMPLE_VALUES:

declare -A EXAMPLE_VALUES=(
    ...
    ["NEW_SERVICE_PORT"]="8888"
    ["NEW_SERVICE_HOST"]="0.0.0.0"
)

# Regenerate
./generate_env_example.sh

# Now these values will always be preserved
```

## 🔐 Generation of Secure Values

The `init_env.sh` script uses these methods (in order of preference):

1. **OpenSSL** (most common):
   ```bash
   openssl rand -hex 32
   ```

2. **Python** (if openssl is not available):
   ```python
   python3 -c "import secrets; print(secrets.token_hex(32))"
   ```

3. **Bash** (fallback):
   ```bash
   cat /dev/urandom | tr -dc 'a-zA-Z0-9' | fold -w 64 | head -n 1
   ```

### Generate manually

```bash
# Generate 64-character hex key
openssl rand -hex 32

# Generate 32-character alphanumeric key
cat /dev/urandom | tr -dc 'a-zA-Z0-9' | fold -w 32 | head -n 1
```

## 🛡️ Security

### ✅ Best Practices

1. **NEVER** commit `.env` to git:
   ```bash
   # Verify it's in .gitignore
   cat .gitignore | grep ".env"
   # Should show: .env
   ```

2. **ALWAYS** rotate secrets in production:
   ```bash
   # Before deploy
   ./init_env.sh --auto
   # Manually configure external services
   ```

3. **Backup** before regenerating:
   ```bash
   # Scripts make automatic backups, but just in case:
   cp .env .env.backup.manual
   ```

4. **Review** changes before committing .env.example:
   ```bash
   git diff .env.example
   ```

### ⚠️ What NOT to do

- ❌ Commit `.env` with real values
- ❌ Share `.env` via email/slack
- ❌ Use example values in production
- ❌ Reuse passwords between services
- ❌ Hardcode secrets in code

## 🔍 Troubleshooting

### Problem: "Secure values are not generated"

```bash
# Verify you have the tools
which openssl
which python3

# If not, install
# Ubuntu/Debian
sudo apt install openssl python3

# macOS
brew install openssl python3
```

### Problem: "Variables are not preserved in .env.example"

```bash
# See which variables are being processed
./generate_env_example.sh 2>&1 | grep "🔒\|✓\|∅"

# If a variable should be preserved but is emptied:
# 1. Verify it does not contain sensitive patterns (PASSWORD, SECRET, etc.)
# 2. Or add it to EXAMPLE_VALUES in the script
```

### Problem: ".env accidentally overwritten"

```bash
# Restore from automatic backup
ls -la .env.backup.*
cp .env.backup.YYYYMMDD_HHMMSS .env

# Or from git if it was committed (bad)
git checkout .env  # Don't do this if .env is in .gitignore!
```

## 📚 Quick Reference

### Required Variables (must have a value)

```bash
# n8n Security
N8N_ENCRYPTION_KEY=
N8N_USER_MANAGEMENT_JWT_SECRET=
N8N_AUTH_JWT_SECRET=
N8N_RUNNERS_AUTH_TOKEN=

# Databases
POSTGRES_PASSWORD=
REDIS_PASSWORD=

# For Forgejo
FORGEJO_DB_PASSWORD=
```

### Optional Variables

```bash
# Telegram Bot
TELEGRAM_BOT_TOKEN=

# Public Tunnel
ZROK_AUTH_TOKEN=

# Web Search
MCP_BRAVE_API_KEY=
```

### Variables with Predefined Values (do not change)

```bash
WHISPER_MODEL=base.en
REDIS_PORT=6379
POSTGRES_PORT=5432
VOICE_GATEWAY_PORT=9000
```

## 🤝 Contributing

When adding new variables:

1. Add them to `.env.example` with:
   - Descriptive comment
   - Example or empty value as appropriate
   - Appropriate section

2. If it's a technical value (port, version, etc.):
   ```bash
   # Add to EXAMPLE_VALUES in generate_env_example.sh
   ["NEW_VARIABLE"]="default_value"
   ```

3. If it's sensitive:
   ```bash
   # Nothing needed, automatically detected
   # by patterns: PASSWORD, SECRET, TOKEN, KEY, AUTH
   ```

4. Document in the main README

## 📞 Support

If you have problems:

1. Review script logs
2. Verify that `.env.example` is up to date
3. Run `./debug_whisper.sh` for diagnostics
4. Open an issue on GitHub

---

**Last update**: 2025-01-01
