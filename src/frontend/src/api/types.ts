// 项目相关类型
export interface Project {
  id: string;
  name: string;
  root: string;
  language?: string;
  file_count?: number;
  symbol_count?: number;
}

export interface IngestRequest {
  repo_url: string;
  language?: string;
  project_name?: string;
  branch?: string;
}

export interface JobStatus {
  job_id: string;
  project_name?: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  stage?: string | null;
  write_phase?: 'prepare' | 'clear' | 'insert_nodes' | 'snapshot' | 'bulk_load' | 'verify' | 'vectorizing' | 'completed' | 'failed' | string;
  items_total?: number | null;
  items_done?: number | null;
  progress?: number;
  message?: string;
  error?: string;
  trace_id?: string;
  retry_count?: number;
  failure_class?: string | null;
  created_at?: string;
  updated_at?: string;
  completed_at?: string | null;
}

// 图谱相关类型
export interface Node {
  id: string;
  label: string;
  type: string;
  properties: Record<string, unknown>;
  metadata?: Record<string, unknown>;
}

export interface Edge {
  id: string;
  from_id: string;
  to_id: string;
  source: string;
  target: string;
  type: string;
  properties: Record<string, unknown>;
}

export interface GraphData {
  nodes: Node[];
  edges: Edge[];
  stats: Record<string, number>;
}

export interface ViewNode {
  id: string;
  label: string;
  name: string;
  project_id: string;
  file_path: string;
  start_line: number | null;
  end_line: number | null;
  language: string;
  kind: string;
  properties: Record<string, unknown>;
}

export interface ViewEdge {
  id: string;
  sourceId: string;
  targetId: string;
  type: string;
  confidence: number;
  evidence_count: number;
  provenance: string;
  properties: Record<string, unknown>;
}

export interface ViewCoverage {
  node_coverage: number;
  edge_coverage: number;
  truncated: boolean;
  budgets: { node_budget: number; edge_budget: number };
  totals: {
    total_nodes: number;
    total_edges: number;
    returned_nodes: number;
    returned_edges: number;
  };
}

export interface GraphViewResponse {
  snapshot_version: string;
  task: 'overview' | 'impact' | 'path' | 'entry_flow';
  nodes: ViewNode[];
  edges: ViewEdge[];
  focus: { primary_node_ids: string[]; suggested_actions: string[] };
  coverage: ViewCoverage;
  metadata?: {
    cache_hit: boolean;
    partial: boolean;
    timeout_hit: boolean;
    coverage_mode: 'estimated' | 'exact' | string;
    freshness?: 'fresh' | 'stale' | 'rebuilding' | 'partial' | string;
    source?: 'snapshot' | 'realtime' | 'fallback' | string;
    snapshot_updated_at?: string | null;
    snapshot_version?: string;
    stale_reason?: string | null;
  };
  explanations: string[];
  warnings: string[];
  impact?: {
    target_id: string;
    total_affected: number;
    direct_affected?: number;
    upstream_direct?: number;
    downstream_direct?: number;
    avg_confidence?: number;
    risk_score?: number;
    risk: 'low' | 'medium' | 'high' | 'critical';
  };
  paths?: Array<{ rank: number; length: number; node_ids: string[]; avg_confidence?: number; score?: number }>;
}

export interface AnalysisStatusResponse {
  snapshot_version: string;
  project: string;
  stages: Record<string, string>;
  progress: number;
  ready_features: string[];
  stats: {
    total_nodes: number;
    communities: number;
    processes: number;
  };
  metadata?: {
    freshness?: 'fresh' | 'stale' | 'rebuilding' | 'partial' | string;
    source?: 'snapshot' | 'realtime' | 'fallback' | string;
    snapshot_updated_at?: string | null;
    snapshot_version?: string;
    stale_reason?: string | null;
  };
}

export interface GraphStats {
  project: string;
  total_nodes: number;
  total_edges: number;
  label_distribution: Record<string, number>;
  metadata?: {
    freshness?: 'fresh' | 'stale' | 'rebuilding' | 'partial' | string;
    source?: 'snapshot' | 'realtime' | 'fallback' | string;
    snapshot_updated_at?: string | null;
    snapshot_version?: string;
    stale_reason?: string | null;
  };
}

// 节点详情类型
export interface CodeSnippet {
  content: string;
  language: string;
  start_line: number;
  end_line: number;
  highlight_lines: number[];
}

export interface NeighborNode {
  id: string;
  name: string;
  type: string;
  direction: 'outgoing' | 'incoming';
}

export interface NodeDetail {
  node: { id: string; label: string; properties: Record<string, unknown> };
  neighbors: Record<string, NeighborNode[]>;
  code_snippet: CodeSnippet | null;
}

// Impact Analysis 类型
export interface ImpactNode {
  id: string;
  name: string;
  type: string;
  rel_type: string;
}

export interface ImpactAnalysis {
  upstream: Record<string, ImpactNode[]>;
  downstream: Record<string, ImpactNode[]>;
  summary: { total_affected: number; direct: number; indirect: number };
}

export interface GinEndpointHit {
  method: string;
  route: string;
  handler_symbol: string;
  file_path: string;
  start_line?: number;
  node_id?: string;
  score: number;
}

export interface GinEndpointSearchResponse {
  project: string;
  query: string;
  total: number;
  hits: GinEndpointHit[];
}

export interface NavReferenceNode {
  id: string;
  name: string;
  label: string;
  file_path?: string;
  start_line?: number;
  end_line?: number;
}

export interface NavReferenceEdge {
  source_id: string;
  target_id: string;
  rel_type: string;
  direction: 'outgoing' | 'incoming';
}

export interface ReferenceSubgraphResponse {
  project: string;
  symbol: string;
  center_node_id: string;
  depth: number;
  direction: 'in' | 'out' | 'both';
  truncated: boolean;
  stats: Record<string, number>;
  nodes: NavReferenceNode[];
  edges: NavReferenceEdge[];
}

export interface EntrypointReverseLookupResponse {
  project: string;
  node_id: string;
  hits: GinEndpointHit[];
}

// 聊天相关类型
export interface ChatRequest {
  query: string;
  project_id: string;
  stream?: boolean;
  session_id?: string;
}

export interface ChatResponse {
  answer: string;
  sources: Array<Record<string, unknown>>;
  evidence: Array<Record<string, unknown>>;
  intent: string;
  quality_score: number;
  retrieval_trace_id: string;
  metadata: Record<string, unknown>;
}

// API 响应通用类型
export interface APIResponse<T> {
  data: T;
  message?: string;
}

export interface APIError {
  detail: string;
  status_code: number;
}
