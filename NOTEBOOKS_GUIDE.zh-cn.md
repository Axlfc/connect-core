# 用于测试 connect-core 的 Jupyter Notebooks
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](https://github.com/Axlfc/connect-core/blob/master/NOTEBOOKS_GUIDE.zh-cn.md)
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/Axlfc/connect-core/blob/master/NOTEBOOKS_GUIDE.en.md)
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](https://github.com/Axlfc/connect-core/blob/master/NOTEBOOKS_GUIDE.md)
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](https://github.com/Axlfc/connect-core/blob/master/NOTEBOOKS_GUIDE.ca.md)


本目录包含用于测试 connect-core 智能体架构和编排功能的 Jupyter Notebooks。

## 可用 Notebooks

### 1. `test_agent_router.ipynb` 🔀
**目的：** 测试智能体路由器和多智能体编排功能

**内容：**
- ✓ 任务路由测试
- ✓ 多智能体编排
- ✓ 任务拆解
- ✓ 智能体间通信

**要求：**
- 模块：`AgentRouter`, `MultiAgentOrchestrator`, `TaskDecomposer`

---

### 2. `test_communication.ipynb` 📡
**目的：** 测试 n8n 与各项服务（Ollama, Qdrant）之间的通信

**内容：**
- ✓ 服务健康检查
- ✓ Ollama 集成（本地 LLM）
- ✓ 文本生成
- ✓ Qdrant 向量数据库
- ✓ 完整的通信流水线

**要求：**
- Docker 服务：n8n, Ollama, Qdrant
- 库：`requests`

**服务 URLs：**
- n8n: `http://localhost:5678`
- Ollama: `http://localhost:11434`
- Qdrant: `http://localhost:6333`

---

### 3. `test_task_decomposition.ipynb` 🔧
**目的：** 测试任务拆解和并行执行功能

**内容：**
- ✓ 复杂任务拆解
- ✓ 子任务并行执行
- ✓ 依赖关系解析
- ✓ 结果综合
- ✓ 性能分析

**要求：**
- 模块：`TaskDecomposer`, `ParallelTaskExecutor`, `ResultSynthesizer`
- 库：`concurrent.futures`, `time`

---

### 4. `test_end_to_end.ipynb` 🚀
**目的：** 结合 Ollama + Qdrant 集成的完整工作流测试

**内容：**
- **工作流 1：** 使用 RAG（检索增强生成）进行文档分析
  - 任务路由
  - 任务拆解
  - Ollama 集成
  - Qdrant 存储
  - 结果综合
  - 输出验证

- **工作流 2：** 多智能体协作
  - 模拟智能体间的对话
  - 消息流
  - 信息交换

**要求：**
- 所有智能体模块
- 服务：n8n, Ollama, Qdrant
- 库：`requests`, `json`

---

## 如何运行 Notebooks

### 前提条件

1. **启动 Docker 堆栈：**
```bash
./start.sh
```

2. **安装 Jupyter（如果尚未安装）：**
```bash
pip install jupyter notebook
```

3. **导航至项目目录：**
```bash
cd /workspaces/connect-core
```

### 运行特定 Notebook

```bash
jupyter notebook test_agent_router.ipynb
```

### 按顺序运行所有 Notebooks

```bash
jupyter notebook
# 然后打开每个 notebook 并运行所有单元格
```

### 从 VS Code 中运行

1. 在项目目录中打开 VS Code
2. 选择一个 `.ipynb` 文件
3. VS Code 将自动检测 Notebooks
4. 点击 "全部运行 (Run All)" 以执行所有单元格

---

## Notebook 结构

每个 Notebook 都遵循标准结构：

```
1. Setup/Imports (设置与导入)
   └─ 导入必要的模块
   └─ 配置环境变量

2. Test 1: Component 1 (测试 1：组件 1)
   └─ 验证组件功能
   └─ 显示结果

3. Test 2: Component 2 (测试 2：组件 2)
   └─ 验证组件功能
   └─ 显示结果

... (更多测试)

N. Summary (总结)
   └─ 所有测试的总结
   └─ 最终指标
```

---

## 环境变量

Notebooks 使用以下环境变量（带有默认值）：

```bash
# .env 或系统变量中
N8N_BASE_URL=http://localhost:5678
OLLAMA_BASE_URL=http://localhost:11434
QDRANT_BASE_URL=http://localhost:6333
```

---

## 每个 Notebook 中的验证项

### `test_agent_router.ipynb`
- ✓ 智能体被正确检测
- ✓ 任务被路由到合适的智能体
- ✓ 多智能体编排功能正常
- ✓ 智能体间通信已建立

### `test_communication.ipynb`
- ✓ n8n 响应健康检查
- ✓ Ollama 可访问且模型可用
- ✓ Qdrant 已连接且功能正常
- ✓ 完整通信流水线畅通

### `test_task_decomposition.ipynb`
- ✓ 复杂任务被正确拆解
- ✓ 并行执行效率高
- ✓ 依赖关系被正确解析
- ✓ 结果综合准确

### `test_end_to_end.ipynb`
- ✓ 路由 → 拆解 → 执行流程顺畅
- ✓ Ollama 生成有效响应
- ✓ Qdrant 存储结果
- ✓ 结果综合正确
- ✓ 输出验证成功
- ✓ 多智能体协作正常

---

## 故障排除 (Troubleshooting)

### 错误："Cannot connect to Docker services" (无法连接到 Docker 服务)
**解决方案：**
```bash
# 确认服务正在运行
docker compose ps

# 如果未运行，请启动：
./start.sh
```

### 错误："ModuleNotFoundError: No module named 'agents'"
**解决方案：**
```bash
# 确保您位于正确的目录中
cd /workspaces/connect-core

# 验证路径是否在 sys.path 中
# Notebook 中应包含：sys.path.insert(0, os.path.abspath('.'))
```

### Ollama："No models available" (无可用模型)
**解决方案：**
```bash
# 手动下载模型
docker exec ollama ollama pull llama3.2

# 或等待其自动下载
```

### 请求超时 (Timeout in requests)
**解决方案：**
```bash
# 增加请求超时时间
# 在 notebook 中，将 timeout=5 更改为 timeout=30
```

---

## 后续步骤

1. **按顺序运行所有 Notebooks：**
   - `test_agent_router.ipynb`（验证路由）
   - `test_communication.ipynb`（验证通信）
   - `test_task_decomposition.ipynb`（验证并行化）
   - `test_end_to_end.ipynb`（验证完整流程）

2. **监控指标：**
   - 执行时间
   - 资源使用情况（CPU, 内存）
   - 错误和警告

3. **记录结果：**
   - 保存 notebook 输出
   - 创建测试报告

4. **根据结果进行优化：**
   - 必要时调整超时时间
   - 优化任务拆解逻辑
   - 改进结果综合算法

---

## 有用链接

- [Jupyter 文档](https://jupyter.readthedocs.io/)
- [n8n 文档](https://docs.n8n.io/)
- [Ollama GitHub](https://github.com/ollama/ollama)
- [Qdrant 文档](https://qdrant.tech/documentation/)

---

**最后更新日期：** 2025-12-20
**connect-core 版本：** 最新版
