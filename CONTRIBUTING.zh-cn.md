# 贡献于 connect-core 🤝
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](https://github.com/[ORGANIZATION]/connect-core/blob/master/CONTRIBUTING.zh-cn.md)
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/[ORGANIZATION]/connect-core/blob/master/CONTRIBUTING.en.md)
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](https://github.com/[ORGANIZATION]/connect-core/blob/master/CONTRIBUTING.md)
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](https://github.com/[ORGANIZATION]/connect-core/blob/master/CONTRIBUTING.ca.md)


感谢您对贡献 connect-core 的兴趣！本文档提供了参与项目的指南。

## 目录

- [行为准则](#行为准则)
- [如何贡献？](#如何贡献)
- [报告错误](#报告错误)
- [建议改进](#建议改进)
- [Pull Requests](#pull-requests)
- [代码标准](#代码标准)
- [本地验证](#本地验证)
- [Commit 约定](#commit-约定)

---

## 行为准则

### 我们的承诺

我们致力于为每个人提供一个开放和友好的环境，无论其：
- 年龄、体型、残疾情况
- 种族、性别认同和表达
- 经验水平、教育程度
- 社会经济地位

### 我们的标准

有助于创造积极环境的行为：
- ✅ 使用包容和友好的语言
- ✅ 尊重不同的观点
- ✅ 接受建设性的批评
- ✅ 专注于对社区最有利的事情
- ✅ 对其他成员表现出共情

不可接受的行为：
- ❌ 性暗示语言或图像
- ❌ 恶意挑衅、侮辱性评论或人身攻击
- ❌ 公开或私下骚扰
- ❌ 未经许可发布私人信息
- ❌ 其他不当行为

---

## 如何贡献？

### 先决条件

- 已安装 Git (`git --version`)
- Docker & Docker Compose (`docker --version`, `docker compose version`)
- Bash 4.0+ (`bash --version`)
- GitHub 账号

### 贡献工作流程

1. **Fork 仓库**
   ```bash
   # 在 GitHub 上点击 "Fork"
   # 然后克隆你的 fork
   git clone https://github.com/[YOUR_USER]/connect-core.git
   cd connect-core
   ```

2. **为你的特性创建分支**
   ```bash
   git checkout -b feature/clear-description
   # 或针对错误修复：
   git checkout -b fix/bug-description
   ```

3. **进行更改**
   - 编辑必要的文件
   - 保持 commit 的原子性，并带有清晰的消息
   - 进行本地验证（参见 [本地验证](#本地验证)）

4. **推送到你的 fork**
   ```bash
   git push origin feature/clear-description
   ```

5. **开启 Pull Request**
   - 在 GitHub 上点击 "New Pull Request"
   - 填写 PR 模板
   - 等待审核

---

## 报告错误

### 报告之前

- ✅ 确认不存在类似的 issue
- ✅ 更新到最新代码 (`git pull origin master`)
- ✅ 在当前代码中复现错误
- ✅ 收集调试信息

### 如何报告

**开启一个 issue** 并包含以下详细信息：

```markdown
## 描述
错误的简要描述

## 复现步骤
1. ...
2. ...
3. ...

## 当前行为
发生了什么？

## 预期行为
应该发生什么？

## 系统信息
- 操作系统: [例如: Ubuntu 22.04]
- Docker 版本: [例如: 24.0.0]
- 配置文件 (Profile): [cpu/gpu-nvidia/gpu-amd]

## 日志
```
<此处填入相关日志>
```

## 附加信息
任何其他背景信息
```

---

## 建议改进

### 建议之前

- ✅ 阅读文档
- ✅ 搜索类似的建议
- ✅ 考虑项目的范围

### 建议模板

```markdown
## 简要描述
描述改进的一行文字

## 解决的问题
这解决了用户的什么问题？

## 提议的解决方案
改进的描述

## 益处
- 益处 1
- 益处 2

## 实现示例
伪代码或示例（如果适用）

## 已考虑的替代方案
其他评估过的解决方案
```

---

## Pull Requests

### 开启 PR 之前的检查清单

- [ ] 我的代码遵循项目的代码标准
- [ ] 我已经更新了文档
- [ ] 我的 commit 具有清晰且具描述性的消息
- [ ] 我已经使用 `scripts/validate.sh` 进行了本地验证
- [ ] 我已经通过 `scripts/smoke-test.sh` 进行了测试
- [ ] 不包含“施工中”或临时代码
- [ ] 不添加不必要的依赖项

### 审核过程

1. **自动验证** (GitHub Actions)
   - YAML 验证
   - Shell lint 检查
   - Dockerfile lint 检查
   - Docker Compose 验证
   - 安全检查

2. **人工审核**
   - 代码审查
   - 评估更改
   - 如果有必要，要求进行更改

3. **合并**
   - 维护者批准
   - Squash & merge 到 master 分支
   - CI/CD 部署更改

### PR 模板

```markdown
## 描述
更改的简要描述

## 相关内容
- Closes #123
- Fixes #456

## 更改类型
- [ ] 错误修复 (Bug fix)
- [ ] 新特性 (New feature)
- [ ] 文档更改
- [ ] 重构

## 所做的更改
- 更改 1
- 更改 2
- 更改 3

## 已执行的测试
描述你如何测试这些更改

## 截图（如果适用）
如果有视觉上的更改，请添加截图

## 附加说明
给审核者的任何其他信息
```

---

## 代码标准

### Shell 脚本 (.sh)

```bash
#!/bin/bash
set -e  # 出错时退出

# 使用具描述性的注释
# 变量使用大写字母
CONFIG_FILE="/path/to/file"

# 函数名具描述性
print_info() {
    echo "ℹ️ $1"
}

# 输入验证
if [ -z "$1" ]; then
    echo "错误：缺失参数"
    exit 1
fi

# 变量使用引号
echo "消息：$CONFIG_FILE"
```

**工具：** `shellcheck`
```bash
shellcheck script.sh
```

### Dockerfiles

```dockerfile
FROM base-image:version

LABEL maintainer="maintainer@example.com"
LABEL description="清晰的描述"

# 为各部分使用注释
USER root

# 尽可能合并 RUN 指令
RUN apt-get update && \
    apt-get install -y \
    package1 \
    package2 && \
    rm -rf /var/lib/apt/lists/*

# 显式暴露端口
EXPOSE 5678

# 定义卷
VOLUME ["/data"]

# 非 root 用户
USER appuser

ENTRYPOINT ["./entrypoint.sh"]
CMD ["start"]
```

**工具：** `hadolint`
```bash
hadolint Dockerfile
```

### YAML (docker-compose.yml)

```yaml
# 2 空格缩进
version: "3.8"

services:
  service-name:
    image: image:version

    # 逻辑组织
    container_name: service-name
    restart: unless-stopped

    # 环境变量优先
    environment:
      - VAR_NAME=value

    # 端口
    ports:
      - "5678:5678"

    # 卷
    volumes:
      - volume-name:/path

    # 健康检查
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5678"]
      interval: 30s
      timeout: 10s
      retries: 3

networks:
  network-name:
    driver: bridge
```

### JSON (n8n-task-runners.json)

```json
{
  "task-runners": [
    {
      "runner-type": "python",
      "command": "/usr/bin/python3",
      "args": ["--flag", "value"],
      "health-check-server-port": "5682"
    }
  ]
}
```

**验证方法：** `python -m json.tool n8n-task-runners.json`

### 文档 (Markdown)

- ✅ 清晰的层级标题
- ✅ 代码块中的代码示例
- ✅ 到文件的内部链接
- ✅ 长文档的目录
- ✅ 使用 blockquotes 的突出注释
- ✅ 结构化列表

```markdown
# 主标题

## 副标题

### 子标题

**加粗文本** 和 *斜体文本*

> 重要注释或引用

### 代码示例
\`\`\`bash
# Bash 代码
echo "Hello"
\`\`\`

- 点 1
- 点 2
  - 子点 2a
```

---

## 本地验证

### 1. 通用验证脚本

```bash
# 运行所有检查
./scripts/validate.sh

# 预期输出：
# ✓ 验证通过
# ⚠ 警告（不阻塞）
# ✗ 错误（阻塞）
```

### 2. 冒烟测试 (Smoke test)

```bash
# 快速堆栈测试（需要 Docker）
./scripts/smoke-test.sh          # 使用 CPU 配置文件
./scripts/smoke-test.sh gpu-nvidia  # 使用 NVIDIA GPU
./scripts/smoke-test.sh gpu-amd     # 使用 AMD GPU

# 检查项：
# - 服务启动
# - 健康检查
# - API 可用性
```

### 3. 手动 Lint

```bash
# Shell
shellcheck *.sh

# Dockerfiles
hadolint Dockerfile*

# YAML
python3 -c "import yaml; yaml.safe_load(open('docker-compose.yml'))"

# JSON
python3 -m json.tool n8n-task-runners.json

# Markdown
markdownlint *.md
```

### 4. Docker Compose 验证

```bash
# 验证语法
docker compose config --quiet

# 列出服务
docker compose config | grep "^  [a-z]"

# 模拟启动（不拉取镜像）
docker compose --profile cpu config --quiet
```

---

## Commit 约定

### 消息格式

```
<类型>(<范围>): <主题>

<描述>

<footer>
```

### Commit 类型

- `feat:` 新功能
- `fix:` 错误修复
- `docs:` 文档更改
- `style:` 格式更改（不涉及逻辑）
- `refactor:` 重构，不涉及功能更改
- `test:` 测试/验证方面的更改
- `ci:` CI/CD 方面的更改
- `chore:` 构建、依赖项等方面的更改

### 示例

```bash
# 特性
git commit -m "feat(n8n): 添加对并行运行器的支持"

# 错误修复
git commit -m "fix(docker-compose): 修复 Ollama 端口"

# 文档
git commit -m "docs: 更新安装指南"

# 带有描述
git commit -m "feat(comfyui): 添加对自定义节点的支持

- 构建期间安装 git
- 克隆自定义节点仓库
- 配置正确路径

Closes #42"
```

---

## 常见问题 (FAQ)

### 发布流程是怎样的？

1. master 分支的更改进入生产环境
2. GitHub Actions 验证并构建镜像
3. 镜像发布到 GHCR
4. 使用语义化标签进行发布

### 如何报告漏洞？

**不要**开启公开 issue。请私下联系我们：
- 电子邮件：[MAINTAINER_EMAIL]
- GitHub 安全公告：使用 "Report a vulnerability" 选项

### 审核需要多长时间？

- 关键错误：24-48 小时
- 新特性：3-7 天
- 文档：1-3 天
- 取决于复杂性和可用性

### 我可以建议新的依赖项吗？

可以，但请：
- 说明为什么是必要的
- 考虑轻量级替代方案
- 更新相应的 Dockerfile
- 添加到文档中

---

## 有用资源

- [GitHub Flow 指南](https://guides.github.com/introduction/flow/)
- [约定式提交 (Conventional Commits)](https://www.conventionalcommits.org/)
- [Markdown 指南](https://www.markdownguide.org/)
- [ShellCheck Wiki](https://www.shellcheck.net/wiki/)
- [Dockerfile 最佳实践](https://docs.docker.com/develop/dev-best-practices/)

---

## 致谢

感谢您为 connect-core 做出贡献！每一次贡献，无论大小，都有助于改进项目。

如果您有任何疑问，请随时开启讨论 issue 或联系维护者。

---

<div align="center">

**我们期待您的贡献！ ❤️**

</div>
