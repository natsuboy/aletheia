# Aletheia

> "揭示真相的微光"

Aletheia 是一个基于 SCIP（Source Code Intelligence Protocol）的代码智能平台，通过图数据库和向量检索实现精准的代码问答和导航。

## ✨ 特性

- **🔍 智能代码搜索**: 结合结构化图遍历和语义向量搜索
- **📊 可视化代码图谱**: 交互式代码依赖和调用关系可视化
- **🤖 AI 驱动问答**: 基于 RAG（检索增强生成）的精准代码问答
- **🚀 高性能摄取**: 批量插入优化，支持大型代码库（10000+节点）
- **🔒 安全加固**: 输入验证、Cypher 注入防护、速率限制
- **📦 多语言支持**: 当前支持 Go，计划支持 Python、Java 等
- **📥 SCIP摄取**: 支持本地路径、ZIP文件、GitLab仓库三种方式

## 🚀 快速开始

### 使用 Docker Compose（推荐）

```bash
# 克隆仓库
git clone https://github.com/your-org/aletheia.git
cd aletheia

# 配置环境变量
cp .env.example .env
# 编辑 .env 文件，设置 OPENAI_API_KEY

# 启动所有服务
docker compose up -d

# 访问应用
open http://localhost:3000
```

### 手动安装

详细说明请参阅 [DEPLOYMENT.md](DEPLOYMENT.md)。

## 📁 项目结构

```
aletheia/
├── src/
│   ├── backend/           # FastAPI 后端服务
│   │   ├── api/         # API 端点（chat, ingest, graph）
│   │   ├── middleware/   # 中间件（日志、错误处理、速率限制）
│   │   ├── security.py  # 输入验证和 Cypher 注入防护
│   │   └── config.py    # 配置管理（支持环境变量）
│   ├── frontend/          # React + TypeScript 前端
│   ├── graph/            # Memgraph 客户端和异常处理
│   ├── rag/              # RAG 引擎
│   │   ├── llm_client.py        # LLM 客户端
│   │   ├── vector_store.py      # 向量存储（FAISS）
│   │   ├── graph_retriever.py   # 图检索器
│   │   ├── intent_classifier.py # 意图分类
│   │   └── hybrid_retriever.py  # 混合检索
│   ├── ingestion/        # 代码摄取管道
│   │   ├── indexer.py       # SCIP 索引器管理
│   │   ├── mapper.py        # SCIP 到图的映射器
│   │   ├── provider.py      # 源码提供者（本地/ZIP/GitLab）
│   │   └── service.py       # 摄取服务编排
│   └── scip_parser/      # SCIP 协议解析器
├── tests/
│   ├── unit/            # 单元测试
│   ├── integration/     # 集成测试
│   └── fixtures/        # 测试数据和 fixtures
├── docs/
│   ├── development/     # 开发文档
│   │   └── testing-guide.md
│   ├── deployment/      # 部署文档
│   └── api/            # API 文档
├── scripts/
│   └── clean-cache.sh   # 缓存清理脚本
├── docker-compose.yml
├── Dockerfile
└── README.md
```

## 🔧 核心组件

### 1. 摄取管道

将代码仓库转换为可查询的图数据库：

1. **Git Clone**: 克隆目标仓库
2. **SCIP 索引**: 运行 SCIP 索引器（如 scip-go）
3. **SCIP 解析**: 解析 .scip 文件提取结构信息
4. **图映射**: 转换为图节点和边
5. **批量插入**: 使用 UNWIND 优化批量插入 Memgraph

#### SCIP 摄取方式

支持三种 SCIP 摄取方式：

1. **仅 SCIP 文件** (`POST /api/ingest/scip-only`): 快速通道，直接使用 SCIP 文件
2. **SCIP + 本地路径** (`POST /api/ingest/scip-with-source`): SCIP 文件 + 本地源码路径
3. **SCIP + ZIP 文件**: SCIP 文件 + 源码压缩包
4. **SCIP + GitLab 仓库**: SCIP 文件 + GitLab 仓库克隆
5. **完整仓库摄取** (`POST /api/ingest`): 从仓库 URL 自动完成整个流程

支持的语言：
- ✅ **Go** (使用 scip-go)
- 🔄 Python/Java/JavaScript/TypeScript (计划中)

### 2. RAG 引擎

混合检索系统：

- **意图分类**: 判断查询是结构化还是语义化
- **向量搜索**: 使用 FAISS 进行语义搜索
- **图遍历**: 使用 Cypher 进行结构化遍历
- **结果融合**: 组合和重排序两种检索结果
- **LLM 生成**: 使用 OpenAI 兼容 API 生成答案

### 3. 前端界面

- **图谱可视化**: 使用 Sigma.js 渲染交互式图
- **代码浏览**: 侧边栏显示节点详情
- **聊天界面**: 流式 AI 问答
- **项目导航**: 列出和切换已摄取项目

## ⚡ 性能

### 基准测试结果

- **批量插入**:
  - 1000 节点: 0.138s (~7200 节点/秒)
  - 1000 边: 0.122s (~8200 边/秒)
  - 10000 节点 + 10000 边: 15.6s

- **图查询**:
  - 简单查询（按 ID）: 1.70ms
  - 遍历查询（1-3 跳）: 1.89ms
  - 聚合查询: 6.47ms

- **向量搜索**:
  - k=10 搜索（n=10000）: 0.72ms

## 🔒 安全

### 实施的安全措施

- **输入验证**: 所有 API 端点验证输入（长度、格式、模式）
  - Pydantic 模型验证
  - XSS 注入防护
  - SQL/Cypher 注入检测
  - 路径遍历防护

- **Cypher 注入防护**:
  - 标识符清理和验证
  - 危险模式检测
  - 参数化查询

- **速率限制**:
  - API 默认: 60 请求/分钟
  - 聊天端点: 30 请求/分钟
  - 摄取端点: 10 请求/分钟

- **配置安全**:
  - 生产环境强制 JWT_SECRET
  - 敏感信息必须来自环境变量
  - CORS 源白名单

### 测试覆盖率

- **单元测试**: 50+ 测试
  - Config 测试: 验证、环境覆盖、JWT 验证
  - Mapper 测试: 符号映射、关系提取
  - Middleware 测试: 速率限制、CORS
  - Security 测试: 输入验证、注入防护

- **集成测试**: 20+ 测试
  - SCIP 摄取端点测试
  - 图谱 API 测试
  - 聊天 API 测试
  - RAG 流程测试

- **性能测试**: 12+ 基准测试

## ⚙️ 配置

### 环境变量

主要配置项（见 `.env.example`）：

```bash
# 应用配置
APP_ENV=production
DEBUG=false
LOG_LEVEL=INFO

# LLM API
OPENAI_API_KEY=sk-xxx
OPENAI_BASE_URL=https://api.openai.com/v1
DEFAULT_LLM_MODEL=gpt-4

# 嵌入模型（可选，独立配置）
EMBEDDING_API_KEY=sk-xxx
EMBEDDING_BASE_URL=https://api.siliconflow.cn/v1
EMBEDDING_MODEL=BAAI/bge-m3

# 数据库
MEMGRAPH_HOST=localhost
MEMGRAPH_PORT=7687
MEMGRAPH_USERNAME=
MEMGRAPH_PASSWORD=

REDIS_HOST=localhost
REDIS_PORT=6379

# 性能
BATCH_SIZE=1000

# 安全（生产环境必须设置）
JWT_SECRET=your-production-secret-key-at-least-32-characters-long
RATE_LIMIT_PER_MINUTE=60
CORS_ORIGINS=http://localhost:3000,http://localhost:5173
```

### 模型配置

#### LLM 模型

**支持的模型**:
- gpt-4
- gpt-4-turbo
- gpt-3.5-turbo
- 其他 OpenAI 兼容模型

#### 嵌入模型

**支持的嵌入模型**:
- `text-embedding-3-small` (OpenAI)
- `BAAI/bge-m3` (SiliconFlow)

## 📚 文档

### 部署文档
- **[docs/deployment/docker.md](docs/deployment/docker.md)**: Docker 部署指南
- **[docs/deployment/production.md](docs/deployment/production.md)**: 生产环境配置指南

### API 文档
- **[docs/api/examples.md](docs/api/examples.md)**: API 使用示例

### 开发文档
- **[docs/development/testing-guide.md](docs/development/testing-guide.md)**: 测试指南
- **[DEVELOPMENT.md](DEVELOPMENT.md)**: 开发者指南
- **[TODO.md](TODO.md)**: 功能路线图

### 在线文档
访问运行中的服务：
- **API 文档**: http://localhost:8000/docs
- **Memgraph Lab**: http://localhost:7444

## 🛠️ 开发

### 设置开发环境

```bash
# 安装依赖
pip install uv
uv sync

# 运行测试
uv run pytest -v

# 启动开发服务器
uv run uvicorn src.backend.main:app --reload
```

### 代码规范

- **Python**: PEP 8，使用 Ruff 格式化
- **TypeScript**: ESLint + Prettier
- **Git 提交**: 约定式提交

### 运行测试

```bash
# 所有单元测试
uv run pytest tests/unit/ -v

# 集成测试（需要服务运行）
docker compose up -d redis memgraph
uv run pytest tests/integration/ -v

# 性能基准测试
uv run pytest tests/benchmark/ -v -s

# 带覆盖率报告
uv run pytest --cov=src --cov-report=html
```

### 清理缓存

```bash
# 使用清理脚本
bash scripts/clean-cache.sh
```

## 🤝 贡献

欢迎贡献！请查看 [DEVELOPMENT.md](DEVELOPMENT.md) 了解如何：

1. 添加新的编程语言支持
2. 自定义嵌入或 LLM 模型
3. 扩展 RAG 检索策略
4. 修复 bug 和添加功能

## 📜 许可证

[Specify your license here]

## 🙏 致谢

- **SCIP**: Sourcegraph 的 Source Code Intelligence Protocol
- **Memgraph**: 图数据库平台
- **FAISS**: Facebook AI 相似性搜索
- **FastAPI**: 现代 Web 框架
