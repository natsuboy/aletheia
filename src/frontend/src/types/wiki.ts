// Wiki TypeScript 类型

export interface WikiPage {
  id: string;
  title: string;
  content: string;
  file_paths: string[];
  importance: number;
  related_pages: string[];
  graph_entity_ids: string[];
  mermaid_diagrams: string[];
}

export interface WikiSection {
  id: string;
  title: string;
  pages: string[];
  subsections: string[];
  community_id: number | null;
}

export interface WikiStructure {
  id: string;
  title: string;
  description: string;
  pages: Record<string, WikiPage>;
  sections: Record<string, WikiSection>;
  root_sections: string[];
  generated_at: string;
  project_id: string;
}

export interface WikiGenerateResponse {
  job_id: string;
  project_id: string;
  status: string;
  message: string;
}

export interface WikiExportResponse {
  format: string;
  content: string;
}

export interface WikiDiagnosticResponse {
  graph: {
    node_count: number;
    edge_count: number;
    has_community_ids: boolean;
    error?: string;
  };
  clustering: {
    community_count: number;
    community_sizes: Record<number, number>;
    error?: string;
  };
  cache: {
    redis_exists: boolean;
    file_exists: boolean;
    file_size_bytes: number;
    error?: string;
  };
  job: {
    last_job_id: string | null;
    last_status?: string | null;
    last_message?: string | null;
  };
  wiki_quality?: {
    page_count: number;
    sections_count: number;
    empty_pages: number;
    failed_pages: number;
    avg_content_length: number;
    mermaid_count: number;
  };
}
