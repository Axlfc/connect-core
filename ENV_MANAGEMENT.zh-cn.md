# 环境变量管理
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](https://github.com/[ORGANIZATION]/connect-core/blob/master/ENV_MANAGEMENT.zh-cn.md)
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/[ORGANIZATION]/connect-core/blob/master/ENV_MANAGEMENT.en.md)
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](https://github.com/[ORGANIZATION]/connect-core/blob/master/ENV_MANAGEMENT.md)
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](https://github.com/[ORGANIZATION]/connect-core/blob/master/ENV_MANAGEMENT.ca.md)


本项目包含多个脚本，用于智能且安全地管理环境变量。

## 📁 文件

- **`.env`** - 包含实际值的文件（切勿提交到 git）
- **`.env.example`** - 包含示例值的模板（务必提交）
- **`generate_env_example.sh`** - 从 .env 生成 .env.example
- **`init_env.sh`** - 从 .env.example 初始化 .env

## 🚀 快速入门

### 首次使用（项目新用户）

```bash
# 1. 初始化 .env 文件
./init_env.sh

# 2. 脚本将自动生成安全的值，并询问可选变量
# 按照交互式说明进行操作

# 3. 检查并在必要时进行调整
nano .env

# 4. 启动服务
./start.sh --voice
```

### 自动模式（CI/CD 或脚本调用）

```bash
# 生成包含安全值且无需交互的 .env
./init_env.sh --auto

# 然后手动配置可选变量
echo "TELEGRAM_BOT_TOKEN=您的_token" >> .env
echo "ZROK_AUTH_TOKEN=您的_token" >> .env
```

## 🔄 开发人员工作流

### 修改 .env 后更新 .env.example

```bash
# 在保留有用值的同时生成 .env.example
./generate_env_example.sh

# 查看更改
git diff .env.example

# 如果没问题则提交
git add .env.example
git commit -m "Update .env.example with new variables"
```

### 将您的 .env 与新变量同步

```bash
# 如果有人向项目添加了新变量
git pull

# 使用新变量更新您的 .env
./init_env.sh
# 选择 'n' 以不覆盖现有变量
# 或手动操作：
cat .env.example >> .env
nano .env  # 删除重复项并配置新变量
```

## 🎯 generate_env_example.sh 的行为

该脚本非常**智能**，会保留有用的值：

### ✅ 会保留的变量：

1. **预定义值**（技术配置）：
   ```bash
   WHISPER_MODEL=base.en
   REDIS_PORT=6379
   POSTGRES_USER_ID=999
   ```

2. **示例值**（来自现有的 .env.example）：
   ```bash
   WEBHOOK_URL=http://localhost:5678
   ZROK_API_ENDPOINT=https://api.zrok.io
   ```

3. **看起来像文档说明的值**：
   ```bash
   EXAMPLE_KEY=您的_key
   TEST_VALUE=请修改此处
   ```

### 🔒 会被清空的变量：

敏感变量（包含以下模式）：
- `*PASSWORD*`
- `*SECRET*`
- `*KEY*`（预定义变量除s外）
- `*TOKEN*`
- `*AUTH*`
- `*JWT*`

```bash
# .env 中的原始值
POSTGRES_PASSWORD=我的_超级_机密_123

# .env.example 中的结果
POSTGRES_PASSWORD=
```

## 📋 使用示例

### 示例 1：首次项目设置

```bash
# 克隆仓库
git clone https://github.com/[YOUR_USER]/connect-core.git
cd connect-core

# 赋予脚本执行权限
chmod +x *.sh

# 初始化环境
./init_env.sh

# 预期输出：
# ✅ 备份已创建：.env.backup.20250101_120000
# ℹ️  .env 文件已从 .env.example 创建
#
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 变量：N8N_ENCRYPTION_KEY
# 生成的值：8f4e3c2b1a9d8e7f...
# 是否使用此值？(Y/n/自定义): y
# ✅ N8N_ENCRYPTION_KEY 已配置
```

### 示例 2：向项目添加新变量

```bash
# 1. 编辑 .env 进行测试
echo "NEW_FEATURE_API_KEY=测试值_123" >> .env

# 2. 测试是否正常工作
./start.sh

# 3. 生成更新后的 .env.example
./generate_env_example.sh

# 输出：
# 🔒 POSTGRES_PASSWORD (敏感 - 已清空)
# ✓ WHISPER_MODEL (已保留)
# 🔒 NEW_FEATURE_API_KEY (敏感 - 已清空)

# 4. 验证结果
cat .env.example | grep NEW_FEATURE
# NEW_FEATURE_API_KEY=

# 5. 提交
git add .env.example
git commit -m "Add NEW_FEATURE_API_KEY configuration"
```

### 示例 3：添加新的预定义值

```bash
# 编辑 generate_env_example.sh
# 添加到 EXAMPLE_VALUES 数组：

declare -A EXAMPLE_VALUES=(
    ...
    ["NEW_SERVICE_PORT"]="8888"
    ["NEW_SERVICE_HOST"]="0.0.0.0"
)

# 重新生成
./generate_env_example.sh

# 现在这些值将始终被保留
```

## 🔐 安全值生成

`init_env.sh` 脚本使用以下方法（按优先级排序）：

1. **OpenSSL**（最常用）：
   ```bash
   openssl rand -hex 32
   ```

2. **Python**（如果 openssl 不可用）：
   ```python
   python3 -c "import secrets; print(secrets.token_hex(32))"
   ```

3. **Bash**（备选）：
   ```bash
   cat /dev/urandom | tr -dc 'a-zA-Z0-9' | fold -w 64 | head -n 1
   ```

### 手动生成

```bash
# 生成 64 位十六进制密钥
openssl rand -hex 32

# 生成 32 位字母数字密钥
cat /dev/urandom | tr -dc 'a-zA-Z0-9' | fold -w 32 | head -n 1
```

## 🛡️ 安全

### ✅ 最佳实践

1. **切勿**将 `.env` 提交到 git：
   ```bash
   # 确认其在 .gitignore 中
   cat .gitignore | grep ".env"
   # 应显示：.env
   ```

2. **务必**在生产环境中轮换机密信息：
   ```bash
   # 部署前
   ./init_env.sh --auto
   # 手动配置外部服务
   ```

3. **备份**（在重新生成前）：
   ```bash
   # 脚本会自动备份，但以防万一：
   cp .env .env.backup.manual
   ```

4. **审查**（在提交 .env.example 前）：
   ```bash
   git diff .env.example
   ```

### ⚠️ 不该做的

- ❌ 提交包含真实值的 `.env`
- ❌ 通过邮件/聊天工具分享 `.env`
- ❌ 在生产环境中使用示例值
- ❌ 在不同服务间重复使用密码
- ❌ 在代码中硬编码机密信息

## 🔍 故障排除

### 问题：“无法生成安全值”

```bash
# 确认已安装工具
which openssl
which python3

# 如果未安装，请安装
# Ubuntu/Debian
sudo apt install openssl python3

# macOS
brew install openssl python3
```

### 问题：“变量在 .env.example 中未被保留”

```bash
# 查看正在处理哪些变量
./generate_env_example.sh 2>&1 | grep "🔒\|✓\|∅"

# 如果变量本应保留却被清空：
# 1. 确认其不包含敏感模式（PASSWORD, SECRET 等）
# 2. 或在脚本中将其添加到 EXAMPLE_VALUES
```

### 问题：“.env 被误覆盖”

```bash
# 从自动备份中恢复
ls -la .env.backup.*
cp .env.backup.YYYYMMDD_HHMMSS .env

# 或者如果已提交（错误操作），从 git 恢复
git checkout .env  # 如果 .env 在 .gitignore 中，请勿执行此操作！
```

## 📚 快速参考

### 必填变量（必须有值）

```bash
# n8n 安全
N8N_ENCRYPTION_KEY=
N8N_USER_MANAGEMENT_JWT_SECRET=
N8N_AUTH_JWT_SECRET=
N8N_RUNNERS_AUTH_TOKEN=

# 数据库
POSTGRES_PASSWORD=
REDIS_PASSWORD=

# 针对 Forgejo
FORGEJO_DB_PASSWORD=
```

### 可选变量

```bash
# Telegram 机器人
TELEGRAM_BOT_TOKEN=

# 公共隧道
ZROK_AUTH_TOKEN=

# 网页搜索
MCP_BRAVE_API_KEY=
```

### 具有预定义值的变量（请勿更改）

```bash
WHISPER_MODEL=base.en
REDIS_PORT=6379
POSTGRES_PORT=5432
VOICE_GATEWAY_PORT=9000
```

## 🤝 贡献

添加新变量时：

1. 将其添加到 `.env.example`，包含：
   - 描述性注释
   - 示例值或视情况留空
   - 合适的章节

2. 如果是技术值（端口、版本等）：
   ```bash
   # 在 generate_env_example.sh 的 EXAMPLE_VALUES 中添加
   ["新变量"]="默认值"
   ```

3. 如果是敏感信息：
   ```bash
   # 无需额外操作，脚本会通过模式自动检测：
   # PASSWORD, SECRET, TOKEN, KEY, AUTH
   ```

4. 在主 README 中记录

## 📞 支持

如果遇到问题：

1. 查看脚本日志
2. 确认 `.env.example` 已更新
3. 运行 `./debug_whisper.sh` 进行诊断
4. 在 GitHub 上开启 issue

---

**最后更新时间**：2025-01-01
