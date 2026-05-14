# Contributing to connect-core 🤝
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/Axlfc/connect-core/blob/master/CONTRIBUTING.en.md)
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](https://github.com/Axlfc/connect-core/blob/master/CONTRIBUTING.md)
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](https://github.com/Axlfc/connect-core/blob/master/CONTRIBUTING.ca.md)
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](https://github.com/Axlfc/connect-core/blob/master/CONTRIBUTING.zh-cn.md)


Thank you for your interest in contributing to connect-core! This document provides the guidelines for contributing to the project.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [How to contribute?](#how-to-contribute)
- [Report bugs](#report-bugs)
- [Suggest improvements](#suggest-improvements)
- [Pull Requests](#pull-requests)
- [Code standards](#code-standards)
- [Local validation](#local-validation)
- [Commit conventions](#commit-conventions)

---

## Code of Conduct

### Our promise

We are committed to providing an open and welcoming environment for everyone, regardless of:
- Age, body size, disability
- Ethnicity, gender identity and expression
- Level of experience, education
- Socioeconomic status

### Our standards

Behaviors that contribute to creating a positive environment:
- ✅ Use inclusive and welcoming language
- ✅ Be respectful of different viewpoints
- ✅ Accept constructive criticism
- ✅ Focus on what is best for the community
- ✅ Show empathy towards other members

Unacceptable behaviors:
- ❌ Sexual language or imagery
- ❌ Trolling, insulting comments, or personal attacks
- ❌ Public or private harassment
- ❌ Publishing private information without consent
- ❌ Other inappropriate conduct

---

## How to contribute?

### Prerequisites

- Git installed (`git --version`)
- Docker & Docker Compose (`docker --version`, `docker compose version`)
- Bash 4.0+ (`bash --version`)
- GitHub account

### Contribution Workflow

1. **Fork the repository**
   ```bash
   # On GitHub, click "Fork"
   # Then clone your fork
   git clone https://github.com/[YOUR_USER]/connect-core.git
   cd connect-core
   ```

2. **Create a branch for your feature**
   ```bash
   git checkout -b feature/clear-description
   # or for bugs:
   git checkout -b fix/bug-description
   ```

3. **Make changes**
   - Edit necessary files
   - Keep commits atomic and with clear messages
   - Validate locally (see [Local validation](#local-validation))

4. **Push to your fork**
   ```bash
   git push origin feature/clear-description
   ```

5. **Open a Pull Request**
   - Click "New Pull Request" on GitHub
   - Complete the PR template
   - Wait for review

---

## Report bugs

### Before reporting

- ✅ Verify that a similar issue does not exist
- ✅ Update to the latest code (`git pull origin master`)
- ✅ Reproduce the bug with the current code
- ✅ Gather debugging information

### How to report

**Open an issue** with the following details:

```markdown
## Description
Brief description of the bug

## Steps to reproduce
1. ...
2. ...
3. ...

## Current behavior
What happened?

## Expected behavior
What should happen?

## System information
- OS: [e.g.: Ubuntu 22.04]
- Docker version: [e.g.: 24.0.0]
- Profile: [cpu/gpu-nvidia/gpu-amd]

## Logs
```
<relevant logs here>
```

## Additional information
Any additional context
```

---

## Suggest improvements

### Before suggesting

- ✅ Read the documentation
- ✅ Search for similar suggestions
- ✅ Consider the scope of the project

### Suggestion template

```markdown
## Brief description
One line describing the improvement

## Problem it solves
What user problem does this solve?

## Proposed solution
Description of the improvement

## Benefits
- Benefit 1
- Benefit 2

## Implementation examples
Pseudocode or examples if applicable

## Alternatives considered
Other evaluated solutions
```

---

## Pull Requests

### Checklist before opening PR

- [ ] My code follows the project's code standards
- [ ] I have updated the documentation
- [ ] My commits have clear and descriptive messages
- [ ] I have validated locally with `scripts/validate.sh`
- [ ] I have tested with `scripts/smoke-test.sh`
- [ ] It does not contain "under construction" or temporary code
- [ ] It does not add unnecessary dependencies

### Review process

1. **Automatic validation** (GitHub Actions)
   - YAML validation
   - Shell linting
   - Dockerfile linting
   - Docker Compose validation
   - Security checks

2. **Manual review**
   - Code review
   - Evaluation of changes
   - Request for changes if necessary

3. **Merge**
   - Maintainer approval
   - Squash & merge to master
   - CI/CD deploys changes

### PR Template

```markdown
## Description
Brief description of the changes

## Related to
- Closes #123
- Fixes #456

## Type of change
- [ ] Bug fix
- [ ] New feature
- [ ] Documentation change
- [ ] Refactoring

## Changes made
- Change 1
- Change 2
- Change 3

## Testing performed
Describe how you tested the changes

## Screenshots (if applicable)
Add screenshots if there are visual changes

## Additional notes
Any additional information for the reviewers
```

---

## Code standards

### Shell Scripts (.sh)

```bash
#!/bin/bash
set -e  # Exit on error

# Use descriptive comments
# Variables in UPPERCASE
CONFIG_FILE="/path/to/file"

# Functions with descriptive names
print_info() {
    echo "ℹ️ $1"
}

# Input validation
if [ -z "$1" ]; then
    echo "Error: Missing parameter"
    exit 1
fi

# Use quotes for variables
echo "Message: $CONFIG_FILE"
```

**Tool:** `shellcheck`
```bash
shellcheck script.sh
```

### Dockerfiles

```dockerfile
FROM base-image:version

LABEL maintainer="maintainer@example.com"
LABEL description="Clear description"

# Use comments for sections
USER root

# Combine RUN when possible
RUN apt-get update && \
    apt-get install -y \
    package1 \
    package2 && \
    rm -rf /var/lib/apt/lists/*

# Explicitly expose ports
EXPOSE 5678

# Define volumes
VOLUME ["/data"]

# Non-root user
USER appuser

ENTRYPOINT ["./entrypoint.sh"]
CMD ["start"]
```

**Tool:** `hadolint`
```bash
hadolint Dockerfile
```

### YAML (docker-compose.yml)

```yaml
# 2-space indentation
version: "3.8"

services:
  service-name:
    image: image:version

    # Logical organization
    container_name: service-name
    restart: unless-stopped

    # Environment variables first
    environment:
      - VAR_NAME=value

    # Ports
    ports:
      - "5678:5678"

    # Volumes
    volumes:
      - volume-name:/path

    # Healthcheck
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

**Validate with:** `python -m json.tool n8n-task-runners.json`

### Documentation (Markdown)

- ✅ Clear hierarchical titles
- ✅ Code examples in blocks
- ✅ Internal links to files
- ✅ Table of Contents for long documents
- ✅ Highlighted notes with blockquotes
- ✅ Structured lists

```markdown
# Main Title

## Subtitle

### Subsubtitle

**Bold text** and *italicized*

> Important note or quote

### Code example
\`\`\`bash
# Bash code
echo "Hello"
\`\`\`

- Point 1
- Point 2
  - Subpoint 2a
```

---

## Local validation

### 1. General validation script

```bash
# Run all checks
./scripts/validate.sh

# Expected output:
# ✓ Validations passed
# ⚠ Warnings (does not block)
# ✗ Errors (blocks)
```

### 2. Smoke test

```bash
# Quick stack test (requires Docker)
./scripts/smoke-test.sh          # Uses CPU profile
./scripts/smoke-test.sh gpu-nvidia  # Uses NVIDIA GPU
./scripts/smoke-test.sh gpu-amd     # Uses AMD GPU

# Checks:
# - Service start
# - Health checks
# - API availability
```

### 3. Manual linting

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

### 4. Docker Compose Validation

```bash
# Verify syntax
docker compose config --quiet

# List services
docker compose config | grep "^  [a-z]"

# Simulate start (without pull)
docker compose --profile cpu config --quiet
```

---

## Commit conventions

### Message format

```
<type>(<scope>): <subject>

<description>

<footer>
```

### Commit types

- `feat:` New functionality
- `fix:` Bug fix
- `docs:` Documentation changes
- `style:` Formatting changes (no logic)
- `refactor:` Refactoring without functional change
- `test:` Changes in tests/validation
- `ci:` Changes in CI/CD
- `chore:` Changes to build, dependencies, etc.

### Examples

```bash
# Feature
git commit -m "feat(n8n): add support for parallel runners"

# Bug fix
git commit -m "fix(docker-compose): correct Ollama port"

# Documentation
git commit -m "docs: update installation guide"

# With description
git commit -m "feat(comfyui): add support for custom nodes

- Install git during build
- Clone custom nodes repository
- Configure correct paths

Closes #42"
```

---

## FAQ

### What is the release process?

1. Changes in master go to production
2. GitHub Actions validates and builds images
3. Images are published to GHCR
4. Semantic tags for releases

### How do I report a vulnerability?

**DO NOT** open a public issue. Contact us privately:
- Email: [MAINTAINER_EMAIL]
- GitHub Security Advisory: Use the "Report a vulnerability" option

### How long does the review take?

- Critical bugs: 24-48 hours
- Features: 3-7 days
- Documentation: 1-3 days
- Depends on complexity and availability

### Can I suggest new dependencies?

Yes, but:
- Justify why it is necessary
- Consider lightweight alternatives
- Update corresponding Dockerfiles
- Add to documentation

---

## Useful resources

- [GitHub Flow Guide](https://guides.github.com/introduction/flow/)
- [Conventional Commits](https://www.conventionalcommits.org/)
- [Markdown Guide](https://www.markdownguide.org/)
- [ShellCheck Wiki](https://www.shellcheck.net/wiki/)
- [Dockerfile Best Practices](https://docs.docker.com/develop/dev-best-practices/)

---

## Acknowledgment

Thank you for contributing to connect-core! Every contribution, regardless of size, helps improve the project.

If you have questions, feel free to open a discussion issue or contact the maintainers.

---

<div align="center">

**We look forward to your contribution! ❤️**

</div>
