# 计划：Aletheia 项目

## 摘要 (TL;DR)

> **快速总结**: 将 `code-graph-rag` (核心逻辑)、`deepwiki-open` (文档生成)、`GitNexus` (前端展示) 和 `scip_parser` (代码解析) 整合为一个名为 "Aletheia" 的统一代码智能平台。
>
> **交付物**:
> - **统一后端**: 基于 Python FastAPI 的服务器，处理数据摄取、图查询和 RAG。
> - **摄取管道**: 基于 SCIP 的解析流程（替代原有的 Tree-sitter 直接解析）-> 存入 Memgraph。
> - **图谱 RAG**: 结合 Memgraph 图谱上下文增强的 DeepWiki 文档生成。
> - **前端**: 经过改造的 GitNexus，从纯客户端模式转变为消费后端 API 的客户端-服务器模式。
>
> **预估工作量**: 大型（数周）
> **并行执行**: 是 - 3 个并行波次
> **关键路径**: 摄取 API → 图谱构建 → 前端集成

---

## 背景 (Context)

### 原始需求
整合 4 个现有项目到 "Aletheia"：
1. `code-graph-rag`: 核心图谱逻辑 & Memgraph 交互。
2. `deepwiki-open`: 文档生成。
3. `GitNexus`: 前端可视化（从客户端模式迁移）。
4. `scip_parser`: 代码解析（替代 Tree-sitter）。

### 架构决策
- **代码组织**: 现有的仓库 (`code-graph-rag`, `deepwiki-open`, `GitNexus`, `scip_parser`) 仅作 **只读参考 (READ-ONLY REFERENCE)**。
- **源码位置**: **所有** 新的实现代码必须位于 `src/` 目录下。
- **数据库**: Memgraph (`code-graph-rag` 原生支持)。
- **解析**: 外部 SCIP 索引器 (CLI) -> `scip_parser` -> Memgraph。
- **前端**: GitNexus (React) 转换为客户端-服务器 (Client-Server) 模式。
- **文档**: 存储在仓库内 (`docs/` 目录)。
- **AI 提供商**: OpenAI (默认)。

### Metis 审查缺口 (已解决)
- **SCIP 索引器**: 增加了管理 CLI 依赖的任务 (`scip-python`, `scip-typescript`)。
- **映射**: 增加了严格的 SCIP->GraphNode 映射任务以防数据丢失。
- **GitNexus**: 增加了 API 客户端实现任务以替换 WASM 逻辑。
- **RAG**: 增加了 图+向量 混合检索器任务。

---

## 工作目标 (Work Objectives)

### 核心目标
构建一个平台，用户可以通过 API 摄取代码仓库，以图谱形式可视化（GitNexus），并生成感知图谱上下文的文档（DeepWiki）。所有业务逻辑重写在 `src/` 中。

### 具体交付物
- [ ] `docs/design/` - **设计文档集 (PRD, 架构, ER, 时序图)**。
- [ ] `src/backend/` - 统一的 FastAPI 服务器。
- [ ] `src/ingestion/` - 基于 SCIP 的摄取管道逻辑。
- [ ] `src/rag/` - 图谱增强的 RAG 模块。
- [ ] `src/frontend/` - 移植并改造的 GitNexus 前端代码。

### 完成定义 (Definition of Done)
- [ ] **所有设计文档 (PRD, 架构, 详细设计) 经用户审核通过。**
- [ ] 用户可以通过 API 摄取 Python/TS 仓库。
- [ ] 图谱在 GitNexus (运行自 `src/frontend`) 中正确显示。
- [ ] 用户可以提问 "解释类 X"，并获得利用图谱上下文生成的答案。

### 必须包含 (Must Have)
- **文档优先**: 每一步实施前必须先输出设计文档并获得批准。
- **Mermaid 图表**: 包含原型图、架构图、时序图、ER 图。
- SCIP 解析（构建图谱时不直接使用 Tree-sitter）。
- Memgraph 存储。
- 混合 RAG（向量 + 图谱）。
- **零侵入**: 不修改参考项目的任何文件。

### 绝不包含 (Must NOT Have / Guardrails)
- **未经审核直接编码**: 严禁跳过设计阶段直接写代码。
- **禁止修改参考仓库**: 严禁编辑 `code-graph-rag/`, `deepwiki-open/`, `GitNexus/`, `scip_parser/` 中的文件。
- **无客户端处理**: 所有解析/图谱逻辑必须在服务器端。
- **无复杂社区检测 (MVP)**: 坚持使用基础聚类或 Memgraph 内置算法。
- **无多语言 Monorepo 支持 (MVP)**: 第一阶段专注于单语言仓库。

---

## 验证策略 (Verification Strategy)

### 测试决策
- **设计审核**: 用户对 Markdown/Mermaid 文档的直接反馈。
- **基础设施**: 子项目中已存在 (`code-graph-rag` 用 `pytest`, `GitNexus` 用 `vitest`)。
- **自动化测试**: 后端逻辑 **必须 (YES)** 采用 TDD。
- **Agent 执行 QA**: 集成/UI 测试 **总是 (ALWAYS)** 需要。

### Agent 执行的 QA 场景

#### 场景 1: 端到端摄取
```
Scenario: Ingest a Python Repository
  Tool: Bash (curl)
  Preconditions: Memgraph running, scip-python installed
  Steps:
    1. POST /api/ingest { "url": "https://github.com/test/repo" }
    2. Wait for job completion (poll /api/jobs/{id})
    3. Assert status "completed"
    4. GET /api/graph/stats
    5. Assert nodes > 0
    6. Assert edges > 0
  Expected Result: Repo ingested, graph populated.
```

#### 场景 2: 前端可视化
```
Scenario: Visualize Graph in GitNexus
  Tool: Playwright
  Preconditions: Backend running with ingested data
  Steps:
    1. Navigate to http://localhost:3000
    2. Click "Load Project"
    3. Wait for canvas to render
    4. Assert node count > 0
    5. Click a node -> Assert details panel opens
  Expected Result: Graph renders and is interactive.
```

#### 场景 3: 图谱增强 RAG
```
Scenario: Ask Question with Graph Context
  Tool: Bash (curl)
  Preconditions: Repo ingested
  Steps:
    1. POST /api/chat { "query": "What does class X inherit from?" }
    2. Assert response contains "inherits from Y" (derived from graph)
  Expected Result: Answer reflects structural knowledge.
```

---

## 执行策略 (Execution Strategy)

### 流程规则: 设计-审核-实施 (Design-Review-Implement)

1. **设计**: 为即将进行的波次编写详细设计文档 (Markdown + Mermaid)。
2. **审核**: 暂停并等待用户明确批准。
3. **实施**: 仅在获得批准后编写代码。

### 并行执行波次

```
Phase 0: 全局设计与规划 (文档优先):
├── Task 1: 产品需求文档 (PRD) & 原型图 (Mermaid)
├── Task 2: 技术架构设计 & 架构图 (Mermaid)
├── Task 3: 数据库设计 & ER 图 (Mermaid)
└── Task 4: 详细实施方案 & 时序图 (Mermaid)
🛑 [暂停点: 等待所有设计文档审核通过]

Wave 1: 基础实施 (Foundation):
├── Task 5: 项目脚手架 & 依赖管理
├── Task 6: 后端 API 骨架 (基于设计)
└── Task 7: SCIP 索引器管理器

Wave 2: 核心逻辑 (Core Logic):
├── Task 8: SCIP 图谱映射器 (SCIP -> Memgraph)
├── Task 9: DeepWiki RAG 集成 (AdalFlow + Graph)
└── Task 10: GitNexus API 客户端 (前端移植)

Wave 3: 集成 & UI (Integration):
├── Task 11: 摄取编排器 (胶水逻辑)
├── Task 12: GitNexus UI 清理 (适配服务端数据)
└── Task 13: 端到端测试 & 最终文档
```

---

## 待办事项 (TODOs)

### Phase 0: 全局设计 (Design)

- [ ] 1. **产品需求文档 (PRD) & 原型**
  **做什么**:
  - 编写 `docs/design/PRD.md`。
  - 定义用户故事、核心功能列表、非功能需求。
  - **Mermaid**: 绘制用户流程图 (User Flow) 和 UI 原型线框图 (使用 Mermaid Mockup 或 Flowchart 模拟)。
  - 重点: 明确 GitNexus 前端如何与新的后端 API 交互。
  **QA**: 文档完整，包含所有要求的 Mermaid 图表。
  **分类**: `writing`.
  **并行**: Phase 0.

- [ ] 2. **技术架构设计**
  **做什么**:
  - 编写 `docs/design/ARCHITECTURE.md`。
  - 定义系统边界、组件交互、技术栈决策。
  - **Mermaid**: 绘制 C4 架构图 (System Context, Container, Component)。
  - **Mermaid**: 绘制关键路径的时序图 (Sequence Diagram)，如 "摄取流程" 和 "RAG 问答流程"。
  **QA**: 架构图清晰，涵盖所有组件交互。
  **分类**: `senior-architect`.
  **并行**: Phase 0.

- [ ] 3. **数据库与数据模型设计**
  **做什么**:
  - 编写 `docs/design/SCHEMA.md`。
  - 定义 Memgraph 的节点标签 (Labels) 和关系类型 (Edge Types)。
  - 定义 SCIP 到 Graph 的映射规则表。
  - **Mermaid**: 绘制 ER 图 (Entity Relationship Diagram) 展示图谱模式。
  **QA**: ER 图准确反映业务实体关系。
  **分类**: `senior-architect`.
  **并行**: Phase 0.

- [ ] 4. **详细实施方案**
  **做什么**:
  - 编写 `docs/design/IMPLEMENTATION_PLAN.md`。
  - 细化 API 接口定义 (OpenAPI 规范草案)。
  - 定义目录结构规范、错误处理策略、日志规范。
  - **Mermaid**: 绘制类图 (Class Diagram) 用于核心模块 (如 Mapper, Retriever)。
  **QA**: 实施细节足以指导编码。
  **分类**: `senior-architect`.
  **并行**: Phase 0.

### Wave 1: 基础实施 (Foundation)

- [ ] 5. **项目脚手架 & 依赖管理**
  **做什么**:
  - 创建 `src/` 目录结构 (`backend`, `frontend`, `ingestion`, `rag`)。
  - 配置 `src/` 的依赖管理 (Poetry/UV)。
  - 设置共享的 `docker-compose.yml` (Memgraph, Redis, App)。
  - 创建顶层 `Makefile`。
  - **注意**: 保持 `code-graph-rag/` 等目录为只读参考，不移动它们。
  **参考**: `code-graph-rag/docker-compose.yaml`, `deepwiki-open/docker-compose.yml`.
  **QA**: `docker-compose up` 成功启动所有服务。
  **分类**: `quick` (DevOps).
  **并行**: Wave 1 (需 Phase 0 批准).

- [ ] 6. **后端 API 骨架**
  **做什么**:
  - 创建 `src/backend/main.py` (FastAPI)。
  - 设置路由: `/api/ingest`, `/api/graph`, `/api/doc`.
  - 在 `src/backend/` 中重新实现 DB 连接池 (参考: `code-graph-rag/.../graph_service.py`).
  **参考**: `deepwiki-open/api/main.py`.
  **QA**: `curl localhost:8000/health` 返回 200 & DB 连接状态。
  **分类**: `unspecified-high` (Backend).
  **并行**: Wave 1 (需 Phase 0 批准).

- [ ] 7. **SCIP 索引器管理器**
  **做什么**:
  - 创建 `src/ingestion/indexer.py`.
  - 实现 `check_indexer_availability(lang)` (例如检查 `scip-python --version`).
  - 实现 `run_indexer(repo_path, lang)` -> 返回 `index.scip` 路径。
  **QA**: 模拟 subprocess 调用的单元测试。对虚拟文件运行 `scip-python` 的集成测试。
  **分类**: `unspecified-high` (System).
  **并行**: Wave 1 (需 Phase 0 批准).

### Wave 2: 核心逻辑 (Core Logic)

- [ ] 8. **SCIP 到 Memgraph 映射器 (核心)**
  **做什么**:
  - 创建 `src/ingestion/mapper.py`.
  - 使用 `scip_parser` 读取 `index.scip`。
  - 映射 SCIP `SymbolInformation` -> `GraphNode` (标签: Class/Func, 属性: name, file).
  - 映射 SCIP `Relationship` -> `GraphRelationship` (类型: IMPORTS, INHERITS).
  - **严格模式**: 如果映射模棱两可则抛出错误 (Metis 要求).
  **参考**: `scip_parser/src/scip_parser/core/parser.py`, `code-graph-rag/codebase_rag/models.py`.
  **QA**: 输入样本 SCIP -> 验证 Graph 对象符合预期结构。
  **分类**: `ultrabrain` (Core Logic).
  **并行**: Wave 2 (依赖 Task 5, 7).

- [ ] 9. **图谱增强检索器**
  **做什么**:
  - 创建 `src/rag/graph_retriever.py`.
  - 扩展 AdalFlow 检索器 (参考 `deepwiki-open/api/rag.py` 并在 `src/` 中重写)。
  - 实现 `retrieve(query)`:
    1. 向量搜索 (标准)。
    2. 图谱搜索: 从查询中提取实体 -> 在 Memgraph 中查找邻居。
    3. 合并上下文。
  **参考**: `deepwiki-open/api/rag.py`.
  **QA**: `retrieve("class User")` 返回向量块 **以及** "继承自 BaseModel" (图谱事实)。
  **分类**: `ultrabrain` (AI/RAG).
  **并行**: Wave 2 (依赖 Task 6).

- [ ] 10. **GitNexus API 客户端 (前端移植)**
  **做什么**:
  - 将 `GitNexus/` 代码复制到 `src/frontend/`。
  - 创建 `src/frontend/src/api/client.ts`.
  - 实现 `fetchGraphData(projectId)`.
  - 修改 `src/frontend/src/hooks/useAppState.tsx` 以使用 API 替代本地管道。
  **参考**: `GitNexus/gitnexus/src/core/ingestion/pipeline.ts`.
  **QA**: Mock API 返回 JSON -> `src/frontend` 渲染图谱节点。
  **分类**: `visual-engineering` (Frontend).
  **并行**: Wave 2 (依赖 Task 6).

### Wave 3: 集成 (Integration)

- [ ] 11. **摄取编排器**
  **做什么**:
  - 创建 `src/ingestion/service.py`.
  - 串联流程: `git clone` -> `indexer.run()` -> `mapper.map()` -> `memgraph.insert()`.
  - 处理错误/日志。
  **QA**: 对小型真实仓库 (如 `requests`) 进行端到端摄取。
  **分类**: `unspecified-high` (Integration).
  **并行**: Wave 3.

- [ ] 12. **GitNexus 清理**
  **做什么**:
  - 在 `src/frontend/` 中移除 `src/kuzu`, `src/core/ingestion` (客户端逻辑).
  - 从 `src/frontend/public/` 移除 WASM 二进制文件。
  - 确保 UI 处理来自 API 的 "加载中" 状态。
  **QA**: 构建体积减小，控制台无 WASM 错误。
  **分类**: `quick` (Cleanup).
  **并行**: Wave 3.

- [ ] 13. **最终打磨 & 文档**
  **做什么**:
  - 编写 `docs/architecture.md` (Mermaid).
  - 编写 `docs/api.md` (OpenAPI).
  - 创建 `README.md` 包含设置说明 (Docker vs Local).
  **QA**: 构建清晰，文档存在。
  **分类**: `writing`.
  **并行**: Wave 3.

- [ ] 8. **GitNexus 清理**
  **做什么**:
  - 在 `src/frontend/` 中移除 `src/kuzu`, `src/core/ingestion` (客户端逻辑).
  - 从 `src/frontend/public/` 移除 WASM 二进制文件。
  - 确保 UI 处理来自 API 的 "加载中" 状态。
  **QA**: 构建体积减小，控制台无 WASM 错误。
  **分类**: `quick` (Cleanup).
  **并行**: Wave 3.

- [ ] 9. **最终打磨 & 文档**
  **做什么**:
  - 编写 `docs/architecture.md` (Mermaid).
  - 编写 `docs/api.md` (OpenAPI).
  - 创建 `README.md` 包含设置说明 (Docker vs Local).
  **QA**: 构建清晰，文档存在。
  **分类**: `writing`.
  **并行**: Wave 3.

---

## 提交策略 (Commit Strategy)
- `feat(backend): init skeleton`
- `feat(ingestion): scip indexer manager`
- `feat(ingestion): scip mapper`
- `feat(rag): graph retriever`
- `feat(frontend): api client`
- `refactor(frontend): remove client-side logic`
- `docs: architecture and setup`

## 成功标准 (Success Criteria)
- [ ] `docker-compose up` 启动 Aletheia。
- [ ] 摄取仓库后 Memgraph 中有数据。
- [ ] GitNexus 显示图谱。
- [ ] DeepWiki 使用图谱上下文回答问题。
