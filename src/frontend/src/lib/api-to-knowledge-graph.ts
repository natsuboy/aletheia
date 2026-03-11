import {
  GraphNode,
  GraphRelationship,
  KnowledgeGraph,
  NodeLabel,
  NodeProperties,
  RelationshipType,
  createKnowledgeGraph,
} from '../types/graph';

/**
 * Capitalize first letter to match GitNexus NodeLabel format.
 * Backend returns lowercase (e.g. "function") → we need "Function".
 */
function toNodeLabel(raw: string): NodeLabel {
  if (!raw) return 'CodeElement';
  const capitalized = raw.charAt(0).toUpperCase() + raw.slice(1);
  const valid: Set<string> = new Set([
    'Project', 'Package', 'Module', 'Folder', 'File', 'Class',
    'Function', 'Method', 'Variable', 'Interface', 'Enum',
    'Decorator', 'Import', 'Type', 'CodeElement', 'Community', 'Process',
  ]);
  return valid.has(capitalized) ? (capitalized as NodeLabel) : 'CodeElement';
}

/**
 * Map backend edge type string to RelationshipType.
 */
function toRelationshipType(raw: string): RelationshipType {
  const upper = raw.toUpperCase();
  const valid: Set<string> = new Set([
    'CONTAINS', 'CALLS', 'INHERITS', 'OVERRIDES', 'IMPORTS',
    'USES', 'DEFINES', 'DECORATES', 'IMPLEMENTS', 'EXTENDS', 'MEMBER_OF',
  ]);
  return valid.has(upper) ? (upper as RelationshipType) : 'USES';
}

interface APINode {
  id: string;
  label: string;
  properties: Record<string, unknown>;
}

interface APIEdge {
  id: string;
  from_id: string;
  to_id: string;
  type: string;
  properties: Record<string, unknown>;
}

interface APIGraphData {
  nodes: APINode[];
  edges: APIEdge[];
  stats: Record<string, number>;
}

/**
 * Convert backend API graph data to KnowledgeGraph format.
 * Handles snake_case → camelCase and type normalization.
 */
export function apiToKnowledgeGraph(data: APIGraphData): KnowledgeGraph {
  const nodes: GraphNode[] = data.nodes.map((n) => {
    const props = n.properties;
    const nodeProps: NodeProperties = {
      name: String(props.name ?? props.id ?? n.label ?? ''),
      filePath: String(props.file_path ?? props.filePath ?? ''),
      startLine: props.start_line != null ? Number(props.start_line) : undefined,
      endLine: props.end_line != null ? Number(props.end_line) : undefined,
      language: props.language != null ? String(props.language) : undefined,
      isExported: props.is_exported != null ? Boolean(props.is_exported) : undefined,
    };
    return {
      id: n.id,
      label: toNodeLabel(n.label),
      properties: nodeProps,
    };
  });

  const relationships: GraphRelationship[] = data.edges.map((e) => ({
    id: e.id || `${e.from_id}-${e.to_id}-${e.type}`,
    sourceId: e.from_id,
    targetId: e.to_id,
    type: toRelationshipType(e.type),
    confidence: 1.0,
    reason: '',
  }));

  return createKnowledgeGraph(nodes, relationships);
}
