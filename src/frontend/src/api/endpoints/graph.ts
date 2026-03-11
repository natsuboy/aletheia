import { apiClient } from '../client';
import {
  GraphData,
  GraphStats,
  Node,
  NodeDetail,
  ImpactAnalysis,
  GraphViewResponse,
  AnalysisStatusResponse,
} from '../types';

interface SearchResponse {
  query: string;
  project: string;
  total: number;
  symbols: Node[];
}

interface FileContentResponse {
  path: string;
  content: string;
  language: string;
}

interface CypherQueryResponse {
  results: Record<string, unknown>[];
  count: number;
}

export const graphAPI = {
  async getOverviewView(
    projectId: string,
    body: {
      scope?: 'project' | 'module' | 'file';
      node_budget?: number;
      edge_budget?: number;
      include_communities?: boolean;
      include_processes?: boolean;
    } = {},
    opts?: { force_realtime?: boolean },
  ): Promise<GraphViewResponse> {
    const suffix = opts?.force_realtime ? '?force_realtime=true' : '';
    return apiClient.post<GraphViewResponse>(`/api/graph/${projectId}/view/overview${suffix}`, body);
  },

  async getImpactView(
    projectId: string,
    body: {
      target_id: string;
      direction?: 'upstream' | 'downstream' | 'both';
      max_depth?: number;
      relation_types?: string[];
      min_confidence?: number;
      include_tests?: boolean;
      node_budget?: number;
      edge_budget?: number;
    },
  ): Promise<GraphViewResponse> {
    return apiClient.post<GraphViewResponse>(`/api/graph/${projectId}/view/impact`, body);
  },

  async getPathView(
    projectId: string,
    body: {
      from_id: string;
      to_id: string;
      max_hops?: number;
      relation_types?: string[];
      k_paths?: number;
      node_budget?: number;
      edge_budget?: number;
    },
  ): Promise<GraphViewResponse> {
    return apiClient.post<GraphViewResponse>(`/api/graph/${projectId}/view/path`, body);
  },

  async getEntryFlowView(
    projectId: string,
    body: {
      entry_id?: string;
      max_steps?: number;
      node_budget?: number;
      edge_budget?: number;
    } = {},
  ): Promise<GraphViewResponse> {
    return apiClient.post<GraphViewResponse>(`/api/graph/${projectId}/view/entry-flow`, body);
  },

  async getAnalysisStatus(projectId: string, opts?: { force_realtime?: boolean }): Promise<AnalysisStatusResponse> {
    return apiClient.get<AnalysisStatusResponse>(`/api/graph/${projectId}/analysis/status`, {
      params: opts?.force_realtime ? { force_realtime: true } : undefined,
    });
  },

  async getGraphData(projectId: string, limit = 500, offset = 0): Promise<GraphData> {
    return apiClient.get<GraphData>(`/api/graph/${projectId}/data`, {
      params: { limit, offset },
    });
  },

  async searchNodes(projectId: string, query: string): Promise<Node[]> {
    const res = await apiClient.get<SearchResponse>(`/api/graph/${projectId}/search`, {
      params: { q: query },
    });
    return res.symbols;
  },

  async getStats(projectId: string, opts?: { force_realtime?: boolean }): Promise<GraphStats> {
    return apiClient.get<GraphStats>(`/api/graph/${projectId}/stats`, {
      params: opts?.force_realtime ? { force_realtime: true } : undefined,
    });
  },

  async getNodeNeighbors(projectId: string, nodeId: string): Promise<GraphData> {
    return apiClient.get<GraphData>(`/api/graph/${projectId}/subgraph`, {
      params: { center_node: nodeId, hops: 2, limit: 100 },
    });
  },

  async getNodeDetail(projectId: string, nodeId: string): Promise<NodeDetail> {
    return apiClient.get<NodeDetail>(`/api/graph/${projectId}/node/${nodeId}`);
  },

  async getImpactAnalysis(projectId: string, nodeId: string, depth = 3): Promise<ImpactAnalysis> {
    return apiClient.get<ImpactAnalysis>(`/api/graph/${projectId}/impact/${nodeId}`, {
      params: { depth },
    });
  },

  async getFileContent(projectId: string, path: string): Promise<FileContentResponse> {
    return apiClient.get<FileContentResponse>(`/api/graph/${projectId}/file`, {
      params: { path },
    });
  },

  async executeCypher(cypher: string, parameters?: Record<string, unknown>): Promise<CypherQueryResponse> {
    return apiClient.post<CypherQueryResponse>('/api/graph/query', { cypher, parameters });
  },

  async triggerCluster(projectId: string): Promise<{ project: string; num_communities: number; num_nodes: number }> {
    return apiClient.post(`/api/graph/${projectId}/cluster`);
  },
};
