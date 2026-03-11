// Research TypeScript 类型

export interface ResearchIteration {
  iteration: number;
  query: string;
  findings: string;
  graph_entities_explored: string[];
  sources: Array<Record<string, unknown>>;
}

export interface ResearchSession {
  id: string;
  project_id: string;
  original_query: string;
  iterations: ResearchIteration[];
  status: 'active' | 'concluded';
  max_iterations: number;
  created_at: string;
}

export interface ResearchStartRequest {
  query: string;
  project_id: string;
}

export interface ResearchContinueRequest {
  project_id: string;
}
