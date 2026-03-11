import { create } from 'zustand';
import { toast } from 'sonner';
import type {
  KnowledgeGraph,
  GraphNode,
  GraphRelationship,
  NodeLabel,
  NodeAnimation,
  QueryResult,
  RelationshipType,
} from '../types/graph';
import type { EdgeType } from '../lib/constants';
import { DEFAULT_VISIBLE_LABELS, DEFAULT_VISIBLE_EDGES } from '../lib/constants';
import { graphAPI } from '../api';
import type { AnalysisStatusResponse, GraphStats, GraphViewResponse, NodeDetail, GraphData } from '../api/types';
import { createKnowledgeGraph } from '../types/graph';

interface GraphState {
  // Core data
  knowledgeGraph: KnowledgeGraph | null;
  loading: boolean;
  error: string | null;

  // Task-view metadata
  currentTask: 'overview' | 'impact' | 'path' | 'entry_flow';
  snapshotVersion: string;
  coverage: GraphViewResponse['coverage'] | null;
  taskMetadata: NonNullable<GraphViewResponse['metadata']> | null;
  taskWarnings: string[];
  taskExplanations: string[];
  analysisStatus: AnalysisStatusResponse | null;
  impactSummary: GraphViewResponse['impact'] | null;
  pathCandidates: NonNullable<GraphViewResponse['paths']>;
  activePathRank: number | null;

  // Selection
  selectedNode: GraphNode | null;
  searchResults: GraphNode[];

  // File content cache (lazy-loaded)
  fileContents: Map<string, string>;
  fileContentsLoading: Set<string>;

  // Filters
  visibleLabels: NodeLabel[];
  visibleEdgeTypes: EdgeType[];
  depthFilter: number | null;

  // Highlights
  highlightedNodeIds: Set<string>;
  highlightedEdgePairs: Set<string>;
  aiCitationHighlightedNodeIds: Set<string>;
  aiToolHighlightedNodeIds: Set<string>;
  blastRadiusNodeIds: Set<string>;
  isAIHighlightsEnabled: boolean;

  // Animations
  animatedNodes: Map<string, NodeAnimation>;

  // Query
  queryResult: QueryResult | null;

  // Stats (from /stats endpoint)
  stats: GraphStats | null;

  // Cross-project graph cache (LRU, max 3)
  graphCache: Map<string, KnowledgeGraph>;
  graphCacheOrder: string[];

  // Node detail
  selectedNodeDetail: NodeDetail | null;
  nodeDetailLoading: boolean;

  // Focus node callback (registered by GraphCanvas)
  _focusNodeFn: ((nodeId: string) => void) | null;
  registerFocusNode: (fn: (nodeId: string) => void) => void;
  focusNode: (nodeId: string) => void;

  // Actions
  fetchGraphData: (projectId: string) => Promise<void>;
  fetchNodeDetail: (projectId: string, nodeId: string) => Promise<void>;
  fetchStats: (projectId: string) => Promise<void>;
  fetchAnalysisStatus: (projectId: string) => Promise<void>;
  fetchFileContent: (projectId: string, path: string) => Promise<string | null>;
  searchNodes: (projectId: string, query: string) => Promise<void>;
  selectNode: (node: GraphNode | null) => void;
  runCypherQuery: (cypher: string) => Promise<void>;
  fetchImpactAnalysis: (projectId: string, nodeId: string) => Promise<void>;
  runOverviewView: (projectId: string, opts?: { node_budget?: number; edge_budget?: number }) => Promise<void>;
  runImpactView: (projectId: string, opts: { target_id: string; direction?: 'upstream' | 'downstream' | 'both'; max_depth?: number }) => Promise<void>;
  runPathView: (projectId: string, opts: { from_id: string; to_id: string; max_hops?: number; k_paths?: number }) => Promise<void>;
  runEntryFlowView: (projectId: string, opts?: { entry_id?: string; max_steps?: number }) => Promise<void>;
  selectPathCandidate: (rank: number) => void;

  // Filter actions
  toggleLabelVisibility: (label: NodeLabel) => void;
  toggleEdgeVisibility: (edgeType: EdgeType) => void;
  setAllLabelsVisible: (visible: boolean) => void;
  setAllEdgesVisible: (visible: boolean) => void;
  setDepthFilter: (depth: number | null) => void;

  // Highlight actions
  setHighlightedNodeIds: (ids: Set<string>) => void;
  setAICitationHighlights: (ids: Set<string>) => void;
  setAIToolHighlights: (ids: Set<string>) => void;
  setBlastRadiusNodeIds: (ids: Set<string>) => void;
  toggleAIHighlights: () => void;
  clearAllHighlights: () => void;

  // Animation actions
  triggerNodeAnimation: (nodeId: string, animation: NodeAnimation) => void;
  clearAnimations: () => void;

  // Pagination (legacy compatibility)
  loadedCount: number;
  totalCount: number;
  hasMore: boolean;
  loadingMore: boolean;
  fetchMoreNodes: (projectId: string) => Promise<void>;
  expandNodeNeighbors: (projectId: string, nodeId: string) => Promise<void>;

  // Reset
  clearError: () => void;
  reset: () => void;
}

const toNodeLabel = (raw: string): NodeLabel => {
  const cap = raw ? raw.charAt(0).toUpperCase() + raw.slice(1) : 'CodeElement';

  // 映射后端返回的标签到前端标签
  if (cap === 'Directory') return 'Folder';

  const valid = new Set([
    'Project', 'Package', 'Module', 'Folder', 'File', 'Class',
    'Function', 'Method', 'Variable', 'Interface', 'Enum',
    'Decorator', 'Import', 'Type', 'CodeElement', 'Community', 'Process',
  ]);
  return (valid.has(cap) ? cap : 'CodeElement') as NodeLabel;
};

const toRelType = (raw: string): RelationshipType => {
  const up = raw.toUpperCase();
  const valid = new Set([
    'CONTAINS', 'CALLS', 'INHERITS', 'OVERRIDES', 'IMPORTS', 'USES',
    'DEFINES', 'DECORATES', 'IMPLEMENTS', 'EXTENDS', 'MEMBER_OF',
  ]);
  return (valid.has(up) ? up : 'USES') as RelationshipType;
};

const viewToKnowledgeGraph = (view: GraphViewResponse): KnowledgeGraph => {
  const nodes: GraphNode[] = view.nodes.map((n) => ({
    id: n.id,
    label: toNodeLabel(n.label),
    properties: {
      name: String(n.name || n.properties?.name || n.id),
      filePath: String(n.file_path || n.properties?.file_path || n.properties?.path || ''),
      startLine: n.start_line ?? undefined,
      endLine: n.end_line ?? undefined,
      language: n.language || undefined,
      isExported: n.properties?.is_exported ? Boolean(n.properties.is_exported) : undefined,
    },
  }));

  const relationships: GraphRelationship[] = view.edges.map((e) => ({
    id: e.id || `${e.source_id}-${e.target_id}-${e.type}`,
    sourceId: e.source_id,
    targetId: e.target_id,
    type: toRelType(e.type),
    confidence: e.confidence ?? 1.0,
    reason: e.provenance ?? '',
  }));

  return createKnowledgeGraph(nodes, relationships);
};

const graphDataToKnowledgeGraph = (data: GraphData): KnowledgeGraph => {
  const nodes: GraphNode[] = data.nodes.map((n) => ({
    id: n.id,
    label: toNodeLabel(n.label || n.type),
    properties: {
      name: String(n.properties?.name || n.id),
      filePath: String(n.properties?.file_path || n.properties?.path || ''),
      startLine: n.properties?.start_line != null ? Number(n.properties.start_line) : undefined,
      endLine: n.properties?.end_line != null ? Number(n.properties.end_line) : undefined,
      language: typeof n.properties?.language === 'string' ? n.properties.language : undefined,
      isExported: n.properties?.is_exported ? Boolean(n.properties.is_exported) : undefined,
    },
  }));

  const relationships: GraphRelationship[] = data.edges.map((e) => ({
    id: e.id || `${e.from_id}-${e.to_id}-${e.type}`,
    sourceId: e.from_id,
    targetId: e.to_id,
    type: toRelType(e.type),
    confidence: typeof e.properties?.confidence === 'number' ? e.properties.confidence : 1.0,
    reason: typeof e.properties?.provenance === 'string' ? e.properties.provenance : '',
  }));

  return createKnowledgeGraph(nodes, relationships);
};

const pathNodeIdsToEdgePairs = (nodeIds: string[]): Set<string> => {
  const pairs = new Set<string>();
  for (let i = 0; i < nodeIds.length - 1; i += 1) {
    const from = nodeIds[i];
    const to = nodeIds[i + 1];
    if (from && to) pairs.add(`${from}->${to}`);
  }
  return pairs;
};

export const useGraphStore = create<GraphState>((set, get) => ({
  knowledgeGraph: null,
  loading: false,
  error: null,
  currentTask: 'overview',
  snapshotVersion: 'v0',
  coverage: null,
  taskMetadata: null,
  taskWarnings: [],
  taskExplanations: [],
  analysisStatus: null,
  impactSummary: null,
  pathCandidates: [],
  activePathRank: null,
  selectedNode: null,
  searchResults: [],
  fileContents: new Map(),
  fileContentsLoading: new Set(),
  visibleLabels: [...DEFAULT_VISIBLE_LABELS],
  visibleEdgeTypes: [...DEFAULT_VISIBLE_EDGES],
  depthFilter: null,
  highlightedNodeIds: new Set(),
  highlightedEdgePairs: new Set(),
  aiCitationHighlightedNodeIds: new Set(),
  aiToolHighlightedNodeIds: new Set(),
  blastRadiusNodeIds: new Set(),
  isAIHighlightsEnabled: true,
  animatedNodes: new Map(),
  queryResult: null,
  stats: null,
  graphCache: new Map(),
  graphCacheOrder: [],
  selectedNodeDetail: null,
  nodeDetailLoading: false,
  loadedCount: 0,
  totalCount: 0,
  hasMore: false,
  loadingMore: false,
  _focusNodeFn: null,

  registerFocusNode: (fn) => set({ _focusNodeFn: fn }),
  focusNode: (nodeId) => get()._focusNodeFn?.(nodeId),

  fetchGraphData: async (projectId) => {
    await get().runOverviewView(projectId);
  },

  runOverviewView: async (projectId, opts = {}) => {
    set({ loading: true, error: null, currentTask: 'overview' });
    try {
      const view = await graphAPI.getOverviewView(projectId, {
        scope: 'project',
        node_budget: opts.node_budget ?? 200,
        edge_budget: opts.edge_budget ?? 400,
        include_communities: true,
        include_processes: true,
      });
      const kg = viewToKnowledgeGraph(view);
      set({
        knowledgeGraph: kg,
        loading: false,
        loadedCount: kg.nodes.length,
        totalCount: view.coverage?.totals?.total_nodes ?? kg.nodes.length,
        hasMore: false,
        coverage: view.coverage,
        taskMetadata: view.metadata ?? null,
        taskWarnings: view.warnings,
        taskExplanations: view.explanations,
        snapshotVersion: view.snapshot_version,
        impactSummary: null,
        pathCandidates: [],
        activePathRank: null,
        highlightedNodeIds: new Set(),
        highlightedEdgePairs: new Set(),
        blastRadiusNodeIds: new Set(),
      });
      if (view.warnings.length > 0) {
        toast.warning(view.warnings[0]);
      }
    } catch (error) {
      const msg = error instanceof Error ? error.message : '获取总览视图失败';
      toast.error(msg);
      set({ error: msg, loading: false });
    }
  },

  runImpactView: async (projectId, opts) => {
    set({ loading: true, error: null, currentTask: 'impact' });
    try {
      const view = await graphAPI.getImpactView(projectId, {
        target_id: opts.target_id,
        direction: opts.direction ?? 'both',
        max_depth: opts.max_depth ?? 3,
      });
      const kg = viewToKnowledgeGraph(view);
      const blastIds = new Set<string>();
      if (view.impact?.target_id) blastIds.add(view.impact.target_id);
      kg.nodes.forEach((n) => blastIds.add(n.id));
      set({
        knowledgeGraph: kg,
        loading: false,
        loadedCount: kg.nodes.length,
        totalCount: view.coverage?.totals?.total_nodes ?? kg.nodes.length,
        hasMore: false,
        coverage: view.coverage,
        taskMetadata: view.metadata ?? null,
        taskWarnings: view.warnings,
        taskExplanations: view.explanations,
        snapshotVersion: view.snapshot_version,
        blastRadiusNodeIds: blastIds,
        impactSummary: view.impact ?? null,
        pathCandidates: [],
        activePathRank: null,
        highlightedNodeIds: new Set(),
        highlightedEdgePairs: new Set(),
      });
    } catch (error) {
      const msg = error instanceof Error ? error.message : 'Impact 分析失败';
      toast.error(msg);
      set({ error: msg, loading: false });
    }
  },

  runPathView: async (projectId, opts) => {
    set({ loading: true, error: null, currentTask: 'path' });
    try {
      const view = await graphAPI.getPathView(projectId, {
        from_id: opts.from_id,
        to_id: opts.to_id,
        max_hops: opts.max_hops ?? 6,
        k_paths: opts.k_paths ?? 3,
      });
      const kg = viewToKnowledgeGraph(view);
      const highlight = new Set<string>();
      view.paths?.[0]?.node_ids?.forEach((id) => highlight.add(id));
      const highlightedPairs = pathNodeIdsToEdgePairs(view.paths?.[0]?.node_ids ?? []);
      const candidates = view.paths ?? [];
      set({
        knowledgeGraph: kg,
        loading: false,
        loadedCount: kg.nodes.length,
        totalCount: view.coverage?.totals?.total_nodes ?? kg.nodes.length,
        hasMore: false,
        coverage: view.coverage,
        taskMetadata: view.metadata ?? null,
        taskWarnings: view.warnings,
        taskExplanations: view.explanations,
        snapshotVersion: view.snapshot_version,
        highlightedNodeIds: highlight,
        highlightedEdgePairs: highlightedPairs,
        pathCandidates: candidates,
        activePathRank: candidates.length > 0 ? candidates[0].rank : null,
        impactSummary: null,
        blastRadiusNodeIds: new Set(),
      });
    } catch (error) {
      const msg = error instanceof Error ? error.message : '路径分析失败';
      toast.error(msg);
      set({ error: msg, loading: false });
    }
  },

  runEntryFlowView: async (projectId, opts = {}) => {
    set({ loading: true, error: null, currentTask: 'entry_flow' });
    try {
      const view = await graphAPI.getEntryFlowView(projectId, {
        entry_id: opts.entry_id,
        max_steps: opts.max_steps ?? 12,
      });
      const kg = viewToKnowledgeGraph(view);
      set({
        knowledgeGraph: kg,
        loading: false,
        loadedCount: kg.nodes.length,
        totalCount: view.coverage?.totals?.total_nodes ?? kg.nodes.length,
        hasMore: false,
        coverage: view.coverage,
        taskMetadata: view.metadata ?? null,
        taskWarnings: view.warnings,
        taskExplanations: view.explanations,
        snapshotVersion: view.snapshot_version,
        impactSummary: null,
        pathCandidates: [],
        activePathRank: null,
        highlightedNodeIds: new Set(),
        highlightedEdgePairs: new Set(),
        blastRadiusNodeIds: new Set(),
      });
    } catch (error) {
      const msg = error instanceof Error ? error.message : '入口流程分析失败';
      toast.error(msg);
      set({ error: msg, loading: false });
    }
  },

  fetchMoreNodes: async () => {
    set({ hasMore: false, loadingMore: false });
  },

  expandNodeNeighbors: async (projectId: string, nodeId: string) => {
    try {
      const subgraph = await graphAPI.getNodeNeighbors(projectId, nodeId);
      const newKg = graphDataToKnowledgeGraph(subgraph);

      const currentKg = get().knowledgeGraph;
      if (!currentKg) return;

      const mergedNodes = new Map<string, GraphNode>();
      currentKg.nodes.forEach(n => mergedNodes.set(n.id, n));
      newKg.nodes.forEach(n => mergedNodes.set(n.id, n));

      const mergedEdges = new Map<string, GraphRelationship>();
      currentKg.relationships.forEach(e => mergedEdges.set(e.id, e));
      newKg.relationships.forEach(e => mergedEdges.set(e.id, e));

      const finalKg = createKnowledgeGraph(Array.from(mergedNodes.values()), Array.from(mergedEdges.values()));

      set({
        knowledgeGraph: finalKg,
        loadedCount: finalKg.nodes.length,
        totalCount: Math.max(get().totalCount, finalKg.nodes.length),
      });

      toast.success(`探索节点，发现了 ${newKg.nodes.length} 个相关节点 / ${newKg.relationships.length} 条连接`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '扩展节点失败');
    }
  },

  fetchNodeDetail: async (projectId, nodeId) => {
    set({ nodeDetailLoading: true, selectedNodeDetail: null });
    try {
      const detail = await graphAPI.getNodeDetail(projectId, nodeId);
      set({ selectedNodeDetail: detail, nodeDetailLoading: false });
    } catch {
      toast.error('获取节点详情失败');
      set({ nodeDetailLoading: false });
    }
  },

  fetchStats: async (projectId) => {
    try {
      const stats = await graphAPI.getStats(projectId);
      set({ stats });
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '获取统计信息失败');
    }
  },

  fetchAnalysisStatus: async (projectId) => {
    try {
      const status = await graphAPI.getAnalysisStatus(projectId);
      set({ analysisStatus: status, snapshotVersion: status.snapshot_version });
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '获取分析状态失败');
    }
  },

  fetchFileContent: async (projectId, path) => {
    const { fileContents, fileContentsLoading } = get();
    if (fileContents.has(path)) return fileContents.get(path)!;
    if (fileContentsLoading.has(path)) return null;

    const newLoading = new Set(fileContentsLoading);
    newLoading.add(path);
    set({ fileContentsLoading: newLoading });

    try {
      const res = await graphAPI.getFileContent(projectId, path);
      const updated = new Map(get().fileContents);
      updated.set(path, res.content);
      if (updated.size > 50) {
        const firstKey = updated.keys().next().value;
        if (firstKey) updated.delete(firstKey);
      }
      const doneLoading = new Set(get().fileContentsLoading);
      doneLoading.delete(path);
      set({ fileContents: updated, fileContentsLoading: doneLoading });
      return res.content;
    } catch {
      const doneLoading = new Set(get().fileContentsLoading);
      doneLoading.delete(path);
      set({ fileContentsLoading: doneLoading });
      return null;
    }
  },

  searchNodes: async (projectId, query) => {
    if (!query.trim()) {
      set({ searchResults: [] });
      return;
    }
    try {
      const apiNodes = await graphAPI.searchNodes(projectId, query);
      const results: GraphNode[] = apiNodes.map((n) => ({
        id: n.id,
        label: (n.type || n.label || 'CodeElement') as NodeLabel,
        properties: {
          name: String(n.properties?.name ?? n.label ?? ''),
          filePath: String(n.properties?.file_path ?? ''),
          startLine: n.properties?.start_line != null ? Number(n.properties.start_line) : undefined,
          endLine: n.properties?.end_line != null ? Number(n.properties.end_line) : undefined,
        },
      }));
      set({ searchResults: results });
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '搜索失败');
    }
  },

  selectNode: (node) => set({ selectedNode: node }),

  runCypherQuery: async (cypher) => {
    try {
      const res = await graphAPI.executeCypher(cypher);
      const nodeIds = new Set<string>();
      res.results.forEach((row) => {
        Object.values(row).forEach((val) => {
          if (typeof val === 'string' && val.length > 0) nodeIds.add(val);
          if (val && typeof val === 'object' && 'id' in (val as Record<string, unknown>)) {
            nodeIds.add(String((val as Record<string, unknown>).id));
          }
        });
      });
      set({
        queryResult: { results: res.results, count: res.count, highlightedNodeIds: [...nodeIds] },
        highlightedNodeIds: nodeIds,
        highlightedEdgePairs: new Set(),
        blastRadiusNodeIds: new Set(),
      });
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '查询失败');
    }
  },

  fetchImpactAnalysis: async (projectId, nodeId) => {
    await get().runImpactView(projectId, { target_id: nodeId, direction: 'both', max_depth: 3 });
  },

  selectPathCandidate: (rank) => {
    const { pathCandidates } = get();
    const candidate = pathCandidates.find((p) => p.rank === rank);
    if (!candidate) return;
    const ids = new Set<string>(candidate.node_ids);
    const pairs = pathNodeIdsToEdgePairs(candidate.node_ids);
    set({ highlightedNodeIds: ids, highlightedEdgePairs: pairs, activePathRank: rank });
  },

  toggleLabelVisibility: (label) => {
    const { visibleLabels } = get();
    const idx = visibleLabels.indexOf(label);
    if (idx >= 0) set({ visibleLabels: visibleLabels.filter((l) => l !== label) });
    else set({ visibleLabels: [...visibleLabels, label] });
  },

  toggleEdgeVisibility: (edgeType) => {
    const { visibleEdgeTypes } = get();
    const idx = visibleEdgeTypes.indexOf(edgeType);
    if (idx >= 0) set({ visibleEdgeTypes: visibleEdgeTypes.filter((e) => e !== edgeType) });
    else set({ visibleEdgeTypes: [...visibleEdgeTypes, edgeType] });
  },

  setAllLabelsVisible: (visible) => set({ visibleLabels: visible ? [...DEFAULT_VISIBLE_LABELS] : [] }),
  setAllEdgesVisible: (visible) => set({ visibleEdgeTypes: visible ? [...DEFAULT_VISIBLE_EDGES] : [] }),
  setDepthFilter: (depth) => set({ depthFilter: depth }),

  setHighlightedNodeIds: (ids) =>
    set({
      highlightedNodeIds: ids,
      highlightedEdgePairs: new Set(),
    }),
  setAICitationHighlights: (ids) => set({ aiCitationHighlightedNodeIds: ids }),
  setAIToolHighlights: (ids) => set({ aiToolHighlightedNodeIds: ids }),
  setBlastRadiusNodeIds: (ids) => set({ blastRadiusNodeIds: ids }),
  toggleAIHighlights: () => set((s) => ({ isAIHighlightsEnabled: !s.isAIHighlightsEnabled })),
  clearAllHighlights: () =>
    set({
      highlightedNodeIds: new Set(),
      highlightedEdgePairs: new Set(),
      aiCitationHighlightedNodeIds: new Set(),
      aiToolHighlightedNodeIds: new Set(),
      blastRadiusNodeIds: new Set(),
    }),

  triggerNodeAnimation: (nodeId, animation) => {
    const updated = new Map(get().animatedNodes);
    updated.set(nodeId, animation);
    set({ animatedNodes: updated });
  },
  clearAnimations: () => set({ animatedNodes: new Map() }),

  clearError: () => set({ error: null }),
  reset: () =>
    set({
      knowledgeGraph: null,
      loading: false,
      error: null,
      currentTask: 'overview',
      coverage: null,
      taskMetadata: null,
      taskWarnings: [],
      taskExplanations: [],
      analysisStatus: null,
      impactSummary: null,
      pathCandidates: [],
      activePathRank: null,
      selectedNode: null,
      searchResults: [],
      fileContents: new Map(),
      fileContentsLoading: new Set(),
      visibleLabels: [...DEFAULT_VISIBLE_LABELS],
      visibleEdgeTypes: [...DEFAULT_VISIBLE_EDGES],
      depthFilter: null,
      highlightedNodeIds: new Set(),
      highlightedEdgePairs: new Set(),
      aiCitationHighlightedNodeIds: new Set(),
      aiToolHighlightedNodeIds: new Set(),
      blastRadiusNodeIds: new Set(),
      isAIHighlightsEnabled: true,
      animatedNodes: new Map(),
      queryResult: null,
      stats: null,
      selectedNodeDetail: null,
      nodeDetailLoading: false,
      loadedCount: 0,
      totalCount: 0,
      hasMore: false,
      loadingMore: false,
    }),
}));
