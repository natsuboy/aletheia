import { NodeLabel } from '../types/graph';

export const NODE_COLORS: Record<NodeLabel, string> = {
  Project: '#a855f7',
  Package: '#8b5cf6',
  Module: '#7c3aed',
  Folder: '#6366f1',
  File: '#3b82f6',
  Class: '#f59e0b',
  Function: '#10b981',
  Method: '#14b8a6',
  Variable: '#64748b',
  Interface: '#ec4899',
  Enum: '#f97316',
  Decorator: '#eab308',
  Import: '#475569',
  Type: '#a78bfa',
  CodeElement: '#64748b',
  Community: '#818cf8',
  Process: '#f43f5e',
};

export const NODE_SIZES: Record<NodeLabel, number> = {
  Project: 20,
  Package: 16,
  Module: 13,
  Folder: 10,
  File: 6,
  Class: 8,
  Function: 4,
  Method: 3,
  Variable: 2,
  Interface: 7,
  Enum: 5,
  Decorator: 2,
  Import: 1.5,
  Type: 3,
  CodeElement: 2,
  Community: 0,
  Process: 0,
};

export const COMMUNITY_COLORS = [
  '#3b82f6', '#8b5cf6', '#ec4899', '#f59e0b',
  '#10b981', '#06b6d4', '#f43f5e', '#6366f1',
  '#84cc16', '#a855f7',
];

export const getCommunityColor = (communityIndex: number): string => {
  return COMMUNITY_COLORS[communityIndex % COMMUNITY_COLORS.length];
};

export const DEFAULT_VISIBLE_LABELS: NodeLabel[] = [
  'Project', 'Package', 'Module', 'Folder', 'File',
  'Class', 'Function', 'Method', 'Interface', 'Enum', 'Type',
];

export const FILTERABLE_LABELS: NodeLabel[] = [
  'Folder', 'File', 'Class', 'Function', 'Method',
  'Variable', 'Interface', 'Import',
];

export type EdgeType = 'CONTAINS' | 'DEFINES' | 'IMPORTS' | 'CALLS' | 'EXTENDS' | 'IMPLEMENTS';

export const ALL_EDGE_TYPES: EdgeType[] = [
  'CONTAINS', 'DEFINES', 'IMPORTS', 'CALLS', 'EXTENDS', 'IMPLEMENTS',
];

export const DEFAULT_VISIBLE_EDGES: EdgeType[] = [
  'CONTAINS', 'DEFINES', 'IMPORTS', 'EXTENDS', 'IMPLEMENTS', 'CALLS',
];

export const EDGE_INFO: Record<EdgeType, { color: string; label: string }> = {
  CONTAINS: { color: '#2d5a3d', label: 'Contains' },
  DEFINES: { color: '#0e7490', label: 'Defines' },
  IMPORTS: { color: '#1d4ed8', label: 'Imports' },
  CALLS: { color: '#7c3aed', label: 'Calls' },
  EXTENDS: { color: '#c2410c', label: 'Extends' },
  IMPLEMENTS: { color: '#be185d', label: 'Implements' },
};
