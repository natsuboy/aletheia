import { useState, useMemo, useCallback, useEffect, useRef } from 'react';
import {
  ChevronRight, ChevronDown, Folder, FolderOpen, FileCode,
  Search, Filter, PanelLeftClose, PanelLeft, Box, Braces,
  Variable, Hash, Target,
} from 'lucide-react';
import { useGraphStore } from '@/stores/graphStore';
import { useUIStore } from '@/stores/uiStore';
import { FILTERABLE_LABELS, NODE_COLORS, ALL_EDGE_TYPES, EDGE_INFO } from '@/lib/constants';
import { formatNodeLabel } from '@/lib/nodeLabel';
import type { GraphNode, NodeLabel } from '@/types/graph';
import type { EdgeType } from '@/lib/constants';

interface TreeNode {
  id: string;
  name: string;
  type: 'folder' | 'file';
  path: string;
  children: TreeNode[];
  graphNode?: GraphNode;
}

const buildFileTree = (nodes: GraphNode[]): TreeNode[] => {
  const root: TreeNode[] = [];
  const pathMap = new Map<string, TreeNode>();
  const fileNodes = nodes.filter((n) => n.properties.filePath && n.properties.filePath.length > 0);
  fileNodes.sort((a, b) => a.properties.filePath.localeCompare(b.properties.filePath));

  fileNodes.forEach((node) => {
    const parts = node.properties.filePath.split('/').filter(Boolean);
    let currentPath = '';
    let currentLevel = root;

    parts.forEach((part, index) => {
      currentPath = currentPath ? `${currentPath}/${part}` : part;
      let existing = pathMap.get(currentPath);
      if (!existing) {
        const isLastPart = index === parts.length - 1;
        const isFile = isLastPart && node.label === 'File';
        existing = {
          id: isLastPart ? node.id : currentPath,
          name: part,
          type: isFile ? 'file' : 'folder',
          path: currentPath,
          children: [],
          graphNode: isLastPart ? node : undefined,
        };
        pathMap.set(currentPath, existing);
        currentLevel.push(existing);
      }
      currentLevel = existing.children;
    });
  });
  return root;
};

const getNodeTypeIcon = (label: NodeLabel) => {
  switch (label) {
    case 'Folder': return Folder;
    case 'File': return FileCode;
    case 'Class': return Box;
    case 'Function': case 'Method': return Braces;
    case 'Interface': return Hash;
    default: return Variable;
  }
};

interface TreeItemProps {
  node: TreeNode;
  depth: number;
  searchQuery: string;
  onNodeClick: (node: TreeNode) => void;
  expandedPaths: Set<string>;
  toggleExpanded: (path: string) => void;
  selectedPath: string | null;
}

const TreeItem = ({
  node, depth, searchQuery, onNodeClick, expandedPaths, toggleExpanded, selectedPath,
}: TreeItemProps) => {
  const isExpanded = expandedPaths.has(node.path);
  const isSelected = selectedPath === node.path;
  const hasChildren = node.children.length > 0;

  const filteredChildren = useMemo(() => {
    if (!searchQuery) return node.children;
    return node.children.filter(child =>
      child.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      child.children.some(c => c.name.toLowerCase().includes(searchQuery.toLowerCase()))
    );
  }, [node.children, searchQuery]);

  const matchesSearch = searchQuery && node.name.toLowerCase().includes(searchQuery.toLowerCase());

  const handleClick = () => {
    if (hasChildren) toggleExpanded(node.path);
    onNodeClick(node);
  };

  return (
    <div>
      <button
        onClick={handleClick}
        className={`
          w-full flex items-center gap-1.5 px-2 py-1 text-left text-sm
          hover:bg-hover transition-colors rounded relative cursor-pointer
          ${isSelected ? 'bg-accent/15 text-text-primary border-l-2 border-accent/70' : 'text-text-secondary hover:text-text-primary border-l-2 border-transparent'}
          ${matchesSearch ? 'bg-accent/10' : ''}
        `}
        style={{ paddingLeft: `${depth * 12 + 8}px` }}
      >
        {hasChildren ? (
          isExpanded ? <ChevronDown className="w-3.5 h-3.5 shrink-0 text-text-muted" /> : <ChevronRight className="w-3.5 h-3.5 shrink-0 text-text-muted" />
        ) : (
          <span className="w-3.5" />
        )}
        {node.type === 'folder' ? (
          isExpanded ? <FolderOpen className="w-4 h-4 shrink-0" style={{ color: NODE_COLORS.Folder }} /> : <Folder className="w-4 h-4 shrink-0" style={{ color: NODE_COLORS.Folder }} />
        ) : (
          <FileCode className="w-4 h-4 shrink-0" style={{ color: NODE_COLORS.File }} />
        )}
        <span className="truncate font-mono text-xs">{node.name}</span>
      </button>
      {isExpanded && filteredChildren.length > 0 && (
        <div>
          {filteredChildren.map(child => (
            <TreeItem
              key={child.id} node={child} depth={depth + 1} searchQuery={searchQuery}
              onNodeClick={onNodeClick} expandedPaths={expandedPaths}
              toggleExpanded={toggleExpanded} selectedPath={selectedPath}
            />
          ))}
        </div>
      )}
    </div>
  );
};

interface FiltersTabProps {
  visibleLabels: NodeLabel[];
  toggleLabelVisibility: (label: NodeLabel) => void;
  visibleEdgeTypes: EdgeType[];
  toggleEdgeVisibility: (type: EdgeType) => void;
  depthFilter: number | null;
  setDepthFilter: (depth: number | null) => void;
  selectedNode: GraphNode | null;
}

const FiltersTab = ({
  visibleLabels, toggleLabelVisibility, visibleEdgeTypes, toggleEdgeVisibility,
  depthFilter, setDepthFilter, selectedNode,
}: FiltersTabProps) => (
  <div className="flex-1 overflow-y-auto scrollbar-thin p-3">
    {/* Node Types */}
    <div className="mb-3">
      <h3 className="section-title mb-2">节点类型</h3>
      <p className="text-xs text-text-muted mb-3">控制图中节点类型的可见性</p>
    </div>
    <div className="flex flex-col gap-1">
      {FILTERABLE_LABELS.map((label) => {
        const Icon = getNodeTypeIcon(label);
        const isVisible = visibleLabels.includes(label);
        return (
          <button key={label} onClick={() => toggleLabelVisibility(label)}
            className={`flex items-center gap-2.5 px-2 py-1.5 rounded text-left transition-colors cursor-pointer ${isVisible ? 'bg-elevated text-text-primary' : 'text-text-muted hover:bg-hover hover:text-text-secondary'}`}>
            <div className={`w-5 h-5 rounded flex items-center justify-center ${isVisible ? '' : 'opacity-40'}`} style={{ backgroundColor: `${NODE_COLORS[label]}20` }}>
              <Icon className="w-3 h-3" style={{ color: NODE_COLORS[label] }} />
            </div>
            <span className="text-xs flex-1">{formatNodeLabel(label)}</span>
            <div className={`w-2 h-2 rounded-full transition-colors ${isVisible ? 'bg-accent' : 'bg-border-subtle'}`} />
          </button>
        );
      })}
    </div>

    {/* Edge Types */}
    <div className="mt-6 pt-4 border-t border-border-subtle">
      <h3 className="section-title mb-2">关系类型</h3>
      <p className="text-xs text-text-muted mb-3">控制关系类型的可见性</p>
      <div className="flex flex-col gap-1">
        {ALL_EDGE_TYPES.map((edgeType) => {
          const info = EDGE_INFO[edgeType];
          const isVisible = visibleEdgeTypes.includes(edgeType);
          return (
            <button key={edgeType} onClick={() => toggleEdgeVisibility(edgeType)}
              className={`flex items-center gap-2.5 px-2 py-1.5 rounded text-left transition-colors cursor-pointer ${isVisible ? 'bg-elevated text-text-primary' : 'text-text-muted hover:bg-hover hover:text-text-secondary'}`}>
              <div className={`w-6 h-1.5 rounded-full ${isVisible ? '' : 'opacity-40'}`} style={{ backgroundColor: info.color }} />
              <span className="text-xs flex-1">{info.label}</span>
              <div className={`w-2 h-2 rounded-full transition-colors ${isVisible ? 'bg-accent' : 'bg-border-subtle'}`} />
            </button>
          );
        })}
      </div>
    </div>

    {/* Depth Filter */}
    <div className="mt-6 pt-4 border-t border-border-subtle">
      <h3 className="section-title mb-2">
        <Target className="w-3 h-3 inline mr-1.5" />焦点深度
      </h3>
      <p className="text-xs text-text-muted mb-3">仅显示与当前选中节点 N 跳以内的节点</p>
      <div className="flex flex-wrap gap-1.5">
        {([
          { value: null, label: '全部' },
          { value: 1, label: '1 跳' },
          { value: 2, label: '2 跳' },
          { value: 3, label: '3 跳' },
          { value: 5, label: '5 跳' },
        ] as const).map(({ value, label }) => (
          <button key={label} onClick={() => setDepthFilter(value)}
            className={`px-2 py-1 text-xs rounded transition-colors cursor-pointer ${depthFilter === value ? 'bg-accent text-white' : 'bg-elevated text-text-secondary hover:bg-hover hover:text-text-primary'}`}>
            {label}
          </button>
        ))}
      </div>
      {depthFilter !== null && !selectedNode && (
        <p className="mt-2 text-xs text-text-secondary">请先选中一个节点以应用深度过滤</p>
      )}
    </div>

    {/* 颜色图例 */}
    <div className="mt-6 pt-4 border-t border-border-subtle">
      <h3 className="section-title mb-3">颜色图例</h3>
      <div className="grid grid-cols-2 gap-2">
        {(['Folder', 'File', 'Class', 'Function', 'Interface', 'Method'] as NodeLabel[]).map(label => (
          <div key={label} className="flex items-center gap-1.5">
            <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: NODE_COLORS[label] }} />
            <span className="text-xs text-text-muted">{formatNodeLabel(label)}</span>
          </div>
        ))}
      </div>
    </div>
  </div>
);

interface FileTreePanelProps {
  onFocusNode: (nodeId: string) => void;
}

export function FileTreePanel({ onFocusNode }: FileTreePanelProps) {
  const { knowledgeGraph, visibleLabels, toggleLabelVisibility, visibleEdgeTypes, toggleEdgeVisibility, selectedNode, selectNode, depthFilter, setDepthFilter } = useGraphStore();
  const { setCodePanelOpen } = useUIStore();

  const [isCollapsed, setIsCollapsed] = useState(false);
  const [panelWidth, setPanelWidth] = useState(256);
  const [searchQuery, setSearchQuery] = useState('');
  const [expandedPaths, setExpandedPaths] = useState<Set<string>>(new Set());
  const [activeTab, setActiveTab] = useState<'files' | 'filters'>('files');
  const resizeRef = useRef<{ startX: number; startWidth: number } | null>(null);

  const startResize = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    resizeRef.current = { startX: e.clientX, startWidth: panelWidth };
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
    const onMove = (ev: MouseEvent) => {
      if (!resizeRef.current) return;
      const next = Math.max(180, Math.min(resizeRef.current.startWidth + (ev.clientX - resizeRef.current.startX), 400));
      setPanelWidth(next);
    };
    const onUp = () => {
      resizeRef.current = null;
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
    };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
  }, [panelWidth]);

  const fileTree = useMemo(() => {
    if (!knowledgeGraph) return [];
    return buildFileTree(knowledgeGraph.nodes);
  }, [knowledgeGraph]);

  // Auto-expand first level on initial load
  useEffect(() => {
    if (fileTree.length > 0 && expandedPaths.size === 0) {
      setExpandedPaths(new Set(fileTree.map(n => n.path)));
    }
  }, [fileTree.length]);

  // Auto-expand to selected file
  useEffect(() => {
    const path = selectedNode?.properties?.filePath;
    if (!path) return;
    const parts = path.split('/').filter(Boolean);
    const pathsToExpand: string[] = [];
    let currentPath = '';
    for (let i = 0; i < parts.length - 1; i++) {
      currentPath = currentPath ? `${currentPath}/${parts[i]}` : parts[i];
      pathsToExpand.push(currentPath);
    }
    if (pathsToExpand.length > 0) {
      setExpandedPaths(prev => {
        const next = new Set(prev);
        pathsToExpand.forEach(p => next.add(p));
        return next;
      });
    }
  }, [selectedNode?.id]);

  const toggleExpanded = useCallback((path: string) => {
    setExpandedPaths(prev => {
      const next = new Set(prev);
      if (next.has(path)) next.delete(path); else next.add(path);
      return next;
    });
  }, []);

  const handleNodeClick = useCallback((treeNode: TreeNode) => {
    if (treeNode.graphNode) {
      const isSameNode = selectedNode?.id === treeNode.graphNode.id;
      selectNode(treeNode.graphNode);
      setCodePanelOpen(true);
      if (!isSameNode) onFocusNode(treeNode.graphNode.id);
    }
  }, [selectNode, setCodePanelOpen, onFocusNode, selectedNode]);

  const selectedPath = selectedNode?.properties.filePath || null;

  if (isCollapsed) {
    return (
      <div className="h-full w-14 glass-panel rounded-2xl border border-border-default flex flex-col items-center py-4 gap-3 shadow-2xl animate-slide-in">
        <button onClick={() => setIsCollapsed(false)} className="icon-button cursor-pointer" title="展开面板">
          <PanelLeft className="w-5 h-5" />
        </button>
        <div className="w-6 h-px bg-border-subtle my-1" />
        <button onClick={() => { setIsCollapsed(false); setActiveTab('files'); }} className={`p-2 rounded-lg transition-colors cursor-pointer ${activeTab === 'files' ? 'text-accent bg-accent/12 border border-accent/30' : 'text-text-secondary hover:text-text-primary hover:bg-hover border border-transparent'}`} title="文件浏览">
          <Folder className="w-5 h-5" />
        </button>
        <button onClick={() => { setIsCollapsed(false); setActiveTab('filters'); }} className={`p-2 rounded-lg transition-colors cursor-pointer ${activeTab === 'filters' ? 'text-accent bg-accent/12 border border-accent/30' : 'text-text-secondary hover:text-text-primary hover:bg-hover border border-transparent'}`} title="过滤器">
          <Filter className="w-5 h-5" />
        </button>
      </div>
    );
  }

  return (
    <div className="h-full glass-panel rounded-2xl border border-border-default flex flex-col animate-slide-in relative flex-shrink-0 shadow-2xl overflow-hidden" style={{ width: panelWidth }}>
      {/* Resize handle */}
      <div onMouseDown={startResize} className="absolute top-0 right-0 h-full w-2 cursor-col-resize bg-transparent hover:bg-accent/20 transition-colors z-10" title="拖拽调整宽度" />

      {/* Header */}
      <div className="panel-header">
        <div className="flex items-center gap-1">
          <button onClick={() => setActiveTab('files')} className={`chip cursor-pointer ${activeTab === 'files' ? 'chip-accent' : 'chip-muted hover:border-accent/30 hover:text-text-primary'}`}>
            文件
          </button>
          <button onClick={() => setActiveTab('filters')} className={`chip cursor-pointer ${activeTab === 'filters' ? 'chip-accent' : 'chip-muted hover:border-accent/30 hover:text-text-primary'}`}>
            过滤
          </button>
        </div>
        <button onClick={() => setIsCollapsed(true)} className="icon-button cursor-pointer" title="收起面板">
          <PanelLeftClose className="w-4 h-4" />
        </button>
      </div>

      {activeTab === 'files' && (
        <>
          {/* Search */}
          <div className="px-3 py-2 border-b border-border-subtle">
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-text-muted" />
              <input type="text" placeholder="搜索文件..." value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-8 pr-3 py-1.5 bg-elevated border border-border-subtle rounded text-xs text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent" />
            </div>
          </div>
          {/* File tree */}
          <div className="flex-1 overflow-y-auto scrollbar-thin py-2">
            {fileTree.length === 0 ? (
              <div className="empty-state py-8">
                <div className="empty-state-icon">
                  <Folder className="w-5 h-5" />
                </div>
                <div className="empty-state-title">暂无文件数据</div>
                <div className="empty-state-desc">索引完成后将在这里显示项目文件树。</div>
              </div>
            ) : (
              fileTree.map(node => (
                <TreeItem key={node.id} node={node} depth={0} searchQuery={searchQuery}
                  onNodeClick={handleNodeClick} expandedPaths={expandedPaths}
                  toggleExpanded={toggleExpanded} selectedPath={selectedPath} />
              ))
            )}
          </div>
        </>
      )}

      {activeTab === 'filters' && (
        <FiltersTab
          visibleLabels={visibleLabels} toggleLabelVisibility={toggleLabelVisibility}
          visibleEdgeTypes={visibleEdgeTypes} toggleEdgeVisibility={toggleEdgeVisibility}
          depthFilter={depthFilter} setDepthFilter={setDepthFilter}
          selectedNode={selectedNode}
        />
      )}

      {/* Stats footer */}
      {knowledgeGraph && (
        <div className="px-3 py-2 border-t border-border-subtle bg-elevated/50">
          <div className="flex items-center justify-between">
            <span className="chip chip-muted">{knowledgeGraph.nodes.length} 节点</span>
            <span className="chip chip-muted">{knowledgeGraph.relationships.length} 边</span>
          </div>
        </div>
      )}
    </div>
  );
}
