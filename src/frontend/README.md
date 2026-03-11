# Aletheia Frontend

Aletheia 代码智能平台的前端应用。

## 技术栈

- React 19.2.4
- TypeScript 5.9.3
- Vite 7.3.1
- Zustand 5.0.11 (状态管理)
- Tailwind CSS 4.x + shadcn/ui (UI)
- Sigma.js 3.0.2 (图谱可视化)
- Axios 1.13.5 (HTTP 客户端)

## 开发

### 安装依赖

```bash
npm install
```

### 启动开发服务器

```bash
npm run dev
```

访问 http://localhost:5173

### 构建

```bash
npm run build
```

### 预览生产构建

```bash
npm run preview
```

### 运行测试

```bash
npm run test:e2e
```

## 环境变量

创建 `.env` 文件：

```env
VITE_API_BASE_URL=http://localhost:8000
VITE_WS_BASE_URL=ws://localhost:8000
VITE_DEFAULT_LANGUAGE=go
VITE_MAX_GRAPH_NODES=1000
```

## 项目结构

```
src/
├── api/              # API 客户端
├── components/       # React 组件
│   ├── ui/          # shadcn/ui 组件
│   ├── layout/      # 布局组件
│   ├── project/     # 项目管理组件
│   ├── graph/       # 图谱可视化组件
│   └── chat/        # 聊天组件
├── stores/          # Zustand stores
├── pages/           # 页面组件
├── lib/             # 工具函数
└── types/           # TypeScript 类型
```

## 功能

- **项目管理**: 提交仓库、查看索引进度、管理项目
- **图谱可视化**: 交互式代码关系图谱、节点搜索、多跳查询
- **RAG 聊天**: AI 辅助代码理解、流式响应、引用展示
- **功能集成**: 聊天↔图谱双向导航

## 部署

### Docker 部署

```bash
docker build -t aletheia-frontend .
docker run -p 80:80 aletheia-frontend
```

### Nginx 配置

参考 `nginx.conf` 文件。
