# 最大并行度执行计划

**生成时间**: 2026-02-13
**目标**: 最大化并行执行效率，减少总交付时间

---

## 📊 依赖关系矩阵

```
任务组1 (阻塞修复)
├── 任务组2 (后端测试) ████████ (依赖组1完成)
├── 任务组3 (文档编写) ████████ (独立，可并行)
├── 任务组4 (RAG核心)  ████████ (独立，可并行)
├── 任务组5 (前端基础) ████████ (依赖组1完成)
└── 任务组6 (RAG高级) ████████ (依赖组4)
```

---

## 🔴 阶段0：阻塞修复 (必须先完成，估计1小时)

### 任务0.1: 修复类型转换错误
**文件**: `src/backend/api/ingest.py`
**问题**: API端点传递字符串，service期望Path对象
**解决方案**: 在第519、574等处添加类型转换

```python
# 修改前
scip_file_path = Path(scip_path)

# 修改后
if isinstance(scip_path, str):
    scip_file_path = Path(scip_path).resolve()
elif not isinstance(scip_path, Path):
    scip_file_path = Path(scip_path)
```

**验证**:
```bash
python3 -m py_compile src/backend/api/ingest.py
```

### 任务0.2: Docker重建
**原因**: 应用代码修改后需要重新构建

```bash
# 停止服务
docker compose down

# 重建镜像（仅重建需要修改的服务）
docker compose build api worker

# 启动服务
docker compose up -d

# 验证
docker compose ps
curl http://localhost:8000/api/health
```

**预计时间**: 15分钟

---

## 🟢 阶段1：立即并行任务 (4个独立小组)

### 组1A: 后端测试 (可完全并行)

#### 任务1.1: 测试SCIP摄取端点
**文件**: `tests/integration/test_scip_ingest.py`
**时间**: 30分钟
**执行**: 立即开始

```python
"""SCIP摄取端点集成测试"""
import pytest
from fastapi.testclient import TestClient
from pathlib import Path

def test_scip_upload_local_path():
    """测试本地路径摄取"""
    client = TestClient(app)

    # 准备测试SCIP文件
    scip_path = Path("tests/fixtures/index.scip")

    response = client.post("/api/ingest/scip-only", json={
        "scip_path": str(scip_path),
        "project_name": "test-project"
    })

    assert response.status_code == 200
    data = response.json()
    assert "job_id" in data
```

#### 任务1.2: 补充mapper.py单元测试
**文件**: `tests/unit/test_mapper.py`
**时间**: 45分钟
**执行**: 立即开始

```python
"""mapper单元测试补充"""
def test_mapper_empty_file():
    """测试空文件处理"""
    mapper = SCIPToGraphMapper("test-project")
    index = Index()  # 空索引
    result = mapper.map_index(index)
    assert len(result.nodes) == 1  # 仅Project节点
    assert len(result.edges) == 0

def test_mapper_large_file():
    """测试大文件处理（10000+符号）"""
    # 创建测试数据...
```

#### 任务1.3: 补充retriever.py单元测试
**文件**: `tests/unit/test_retriever.py`
**时间**: 45分钟
**执行**: 立即开始

#### 任务1.4: 编写API集成测试
**文件**: `tests/integration/test_api.py`
**时间**: 30分钟
**执行**: 立即开始

### 组1B: 文档编写 (可完全并行)

#### 任务2.1: 编写API使用示例
**文件**: `docs/api/examples.md`
**时间**: 30分钟
**执行**: 立即开始

```markdown
# API使用示例

## 1. 健康检查
\`\`\`bash
curl http://localhost:8000/api/health
\`\`\`

## 2. 提交摄取任务
\`\`\`bash
curl -X POST http://localhost:8000/api/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "repo_url": "https://github.com/golang/example",
    "language": "go",
    "project_name": "golang-example"
  }'
\`\`\`
```

#### 任务2.2: 编写Docker部署指南
**文件**: `docs/deployment/docker.md`
**时间**: 30分钟
**执行**: 立即开始

#### 任务2.3: 编写生产配置文档
**文件**: `docs/deployment/production.md`
**时间**: 30分钟
**执行**: 立即开始

#### 任务2.4: 更新项目README
**文件**: `README.md`
**时间**: 20分钟
**执行**: 立即开始

---

## 🟢 阶段2：核心功能实现 (3个独立小组)

### 组2A: RAG核心模块 (可完全并行)

#### 任务3.1: 实现向量存储
**文件**: `src/rag/vector_store.py`
**依赖**: OpenAI API Key
**时间**: 2小时

#### 任务3.2: 实现意图分类器
**文件**: `src/rag/intent_classifier.py`
**依赖**: 无
**时间**: 1.5小时

#### 任务3.3: 实现图谱检索器
**文件**: `src/rag/graph_retriever.py`
**依赖**: Memgraph连接
**时间**: 2小时

### 组2B: RAG辅助模块 (可完全并行)

#### 任务4.1: 实现LLM客户端
**文件**: `src/rag/llm_client.py`
**依赖**: OpenAI API Key
**时间**: 1.5小时

#### 任务4.2: 实现提示词构建器
**文件**: `src/rag/prompt_builder.py`
**依赖**: 无
**时间**: 1小时

---

## 🟢 阶段3：前端基础 (可并行开发)

#### 任务5.1: 初始化前端项目
**文件**: `src/frontend/`
**依赖**: 无（从GitNexus复制）
**时间**: 1小时

#### 任务5.2: 实现API客户端
**文件**: `src/frontend/src/api/client.ts`
**依赖**: 无
**时间**: 1.5小时

#### 任务5.3: 实现状态管理
**文件**: `src/frontend/src/stores/`
**依赖**: API客户端
**时间**: 2小时

#### 任务5.4: 集成shadcn/ui
**文件**: `src/frontend/`
**依赖**: 无（shadcn/ui已安装）
**时间**: 30分钟

---

## ⚡ 并行执行时间线

```
时间轴 →

0h  ████████████████████████████████ 阶段0: 静塞修复
     ├─ 类型转换修复
     └─ Docker重建

1h  🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢 阶段1: 立即并行任务
     ├─ 组1A: 后端测试 (4人并行)
     │   ├─ SCIP端点测试
     │   ├─ Mapper测试
     │   ├─ Retriever测试
     │   └─ API集成测试
     └─ 组1B: 文档编写 (4人并行)
         ├─ API示例
         ├─ Docker指南
         ├─ 生产配置
         └─ README更新

3h  🟢🟢🟢🟢 阶段2: RAG核心 (3人并行)
     ├─ 向量存储
     ├─ 意图检索器
     └─ 意图检索器

     🟢🟢 RAG辅助 (2人并行)
     ├─ LLM客户端
     └─ 提示词构建器

5h  🟢🟢🟢 阶段3: 前端基础 (4人并行)
     ├─ 前端初始化
     ├─ API客户端
     ├─ 状态管理
     └─ shadcn/ui集成
```

---

## 🎯 执行指令

### 立即开始（阶段1）
```bash
# 1. 创建测试文件
touch tests/integration/test_scip_ingest.py
touch tests/unit/test_mapper.py
touch tests/unit/test_retriever.py
touch tests/integration/test_api.py

# 2. 创建文档文件
touch docs/api/examples.md
touch docs/deployment/docker.md
touch docs/deployment/production.md

# 3. 开始编写（4个独立任务，可分配给4个人）
# 开发者A: 测试SCIP端点
# 开发者B: 补充Mapper测试
# 开发者C: 补充Retriever测试
# 开发者D: 编写API示例文档
# 开发者E: 编写Docker指南
# 开发者F: 编写生产配置
# 开发者G: 更新README
```

### 阶段0完成后（阻塞修复）
```bash
# 修复类型转换
# 重建Docker

# 然后启动阶段2
touch src/rag/__init__.py
touch src/rag/vector_store.py
touch src/rag/intent_classifier.py
touch src/rag/graph_retriever.py
touch src/rag/llm_client.py
touch src/rag/prompt_builder.py
```

---

## 📈 预期完成时间

- **阶段0**: 1小时 (阻塞修复)
- **阶段1**: 1小时 (4人并行 × 1小时 = 4人小时)
- **阶段2**: 2小时 (5人并行 × 2小时 = 10人小时)
- **阶段3**: 2小时 (4人并行 × 2小时 = 8人小时)

**总计**: 约23人小时（串行需要约40小时）
**节省**: 约42%时间

---

## 🚀 立即行动

**现在可以开始的4个并行任务**:

1. **测试SCIP摄取端点** → 打开 `tests/integration/test_scip_ingest.py`
2. **补充Mapper测试** → 打开 `tests/unit/test_mapper.py`
3. **编写API示例** → 打开 `docs/api/examples.md`
4. **编写部署指南** → 打开 `docs/deployment/docker.md`

**谁想开始？我可以帮你创建这些文件的模板！**
