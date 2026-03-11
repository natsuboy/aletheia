export type NodeLabel =
  | 'Project'
  | 'Package'
  | 'Module'
  | 'Folder'
  | 'File'
  | 'Class'
  | 'Function'
  | 'Method'
  | 'Variable'
  | 'Interface'
  | 'Enum'
  | 'Decorator'
  | 'Import'
  | 'Type'
  | 'CodeElement'
  | 'Community'
  | 'Process';

export type NodeProperties = {
  name: string;
  filePath: string;
  startLine?: number;
  endLine?: number;
  language?: string;
  isExported?: boolean;
  heuristicLabel?: string;
  cohesion?: number;
  symbolCount?: number;
  keywords?: string[];
  description?: string;
  enrichedBy?: 'heuristic' | 'llm';
};

export type RelationshipType =
  | 'CONTAINS'
  | 'CALLS'
  | 'INHERITS'
  | 'OVERRIDES'
  | 'IMPORTS'
  | 'USES'
  | 'DEFINES'
  | 'DECORATES'
  | 'IMPLEMENTS'
  | 'EXTENDS'
  | 'MEMBER_OF';

export interface GraphNode {
  id: string;
  label: NodeLabel;
  properties: NodeProperties;
}

export interface GraphRelationship {
  id: string;
  sourceId: string;
  targetId: string;
  type: RelationshipType;
  confidence: number;
  reason: string;
}

export interface KnowledgeGraph {
  nodes: GraphNode[];
  relationships: GraphRelationship[];
  nodeCount: number;
  relationshipCount: number;
}

export function createKnowledgeGraph(
  nodes: GraphNode[] = [],
  relationships: GraphRelationship[] = [],
): KnowledgeGraph {
  return {
    nodes,
    relationships,
    nodeCount: nodes.length,
    relationshipCount: relationships.length,
  };
}

// UI types
export type ViewMode = 'onboarding' | 'loading' | 'exploring' | 'wiki';
export type RightPanelTab = 'code' | 'chat';

export interface QueryResult {
  results: Record<string, unknown>[];
  count: number;
  highlightedNodeIds?: string[];
}

export type NodeAnimationType = 'pulse' | 'ripple' | 'glow';

export interface NodeAnimation {
  type: NodeAnimationType;
  startTime: number;
  duration: number;
  color?: string;
}

export interface CodeReference {
  id: string;
  filePath: string;
  startLine?: number;
  endLine?: number;
  label: string;
  name?: string;
  nodeId?: string;
  source: 'ai' | 'user';
}

export interface CodeReferenceFocus {
  referenceId: string;
  filePath?: string;
  startLine?: number;
  endLine?: number;
  ts: number;
}
