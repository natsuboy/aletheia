import { useEffect, useCallback, useMemo, useState, useRef, forwardRef, useImperativeHandle } from 'react';
import { ZoomIn, ZoomOut, Maximize2, Focus, RotateCcw, Play, Pause, Lightbulb, LightbulbOff, AlertTriangle, Workflow, Layers } from 'lucide-react';
import { useParams } from 'react-router-dom';
import { useSigma } from '@/hooks/useSigma';
import { useGraphStore } from '@/stores/graphStore';
import { useUIStore } from '@/stores/uiStore';
import { knowledgeGraphToGraphology, filterGraphByDepth } from '@/lib/graph-adapter';
import { NODE_COLORS } from '@/lib/constants';
import { formatNodeLabel } from '@/lib/nodeLabel';
import { GraphFilterPanel } from './GraphFilterPanel';
import type { SigmaNodeAttributes, SigmaEdgeAttributes } from '@/lib/graph-adapter';
import type { NodeLabel } from '@/types/graph';
import Graph from 'graphology';

export interface GraphCanvasHandle {
  focusNode: (nodeId: string) => void;
  refresh: () => void;
}

interface GraphCanvasProps {
  onNodeSelect?: (nodeId: string | null) => void;
}

export const GraphCanvas = forwardRef<GraphCanvasHandle, GraphCanvasProps>(({ onNodeSelect }, ref) => {
  const { projectId } = useParams<{ projectId: string }>();
  const {
    knowledgeGraph,
    selectNode,
    selectedNode: appSelectedNode,
    visibleLabels,
    visibleEdgeTypes,
    depthFilter,
    highlightedNodeIds,
    highlightedEdgePairs,
    setHighlightedNodeIds,
    aiCitationHighlightedNodeIds,
    aiToolHighlightedNodeIds,
    blastRadiusNodeIds,
    isAIHighlightsEnabled,
    toggleAIHighlights,
    animatedNodes,
    loading,
    loadedCount,
    runImpactView,
    runEntryFlowView,
    runOverviewView,
  } = useGraphStore();
  const { setCodePanelOpen } = useUIStore();
  const [hoveredNodeName, setHoveredNodeName] = useState<string | null>(null);

  // Merge all highlight sets when AI highlights enabled
  const effectiveHighlightedNodeIds = useMemo(() => {
    if (!isAIHighlightsEnabled) return highlightedNodeIds;
    const next = new Set(highlightedNodeIds);
    for (const id of aiCitationHighlightedNodeIds) next.add(id);
    for (const id of aiToolHighlightedNodeIds) next.add(id);
    return next;
  }, [highlightedNodeIds, aiCitationHighlightedNodeIds, aiToolHighlightedNodeIds, isAIHighlightsEnabled]);

  const effectiveBlastRadiusNodeIds = useMemo(() => {
    if (!isAIHighlightsEnabled) return new Set<string>();
    return blastRadiusNodeIds;
  }, [blastRadiusNodeIds, isAIHighlightsEnabled]);

  const effectiveAnimatedNodes = useMemo(() => {
    if (!isAIHighlightsEnabled) return new Map();
    return animatedNodes;
  }, [animatedNodes, isAIHighlightsEnabled]);

  const handleNodeClick = useCallback((nodeId: string) => {
    if (!knowledgeGraph) return;
    const node = knowledgeGraph.nodes.find(n => n.id === nodeId);
    if (node) {
      selectNode(node);
      setCodePanelOpen(true);
      onNodeSelect?.(nodeId);
    }
  }, [knowledgeGraph, selectNode, setCodePanelOpen]);

  const handleNodeDoubleClick = useCallback((_nodeId: string) => {
    // 双击预留：可在此扩展相邻节点
  }, []);

  const handleNodeHover = useCallback((nodeId: string | null) => {
    if (!nodeId || !knowledgeGraph) { setHoveredNodeName(null); return; }
    const node = knowledgeGraph.nodes.find(n => n.id === nodeId);
    if (node) setHoveredNodeName(node.properties.name);
  }, [knowledgeGraph]);

  const handleStageClick = useCallback(() => {
    selectNode(null);
  }, [selectNode]);

  const {
    containerRef, sigmaRef,
    setGraph: setSigmaGraph,
    zoomIn, zoomOut, resetZoom, focusNode,
    isLayoutRunning, startLayout, stopLayout,
    selectedNode: sigmaSelectedNode,
    setSelectedNode: setSigmaSelectedNode,
  } = useSigma({
    onNodeClick: handleNodeClick,
    onNodeDoubleClick: handleNodeDoubleClick,
    onNodeHover: handleNodeHover,
    onStageClick: handleStageClick,
    highlightedNodeIds: effectiveHighlightedNodeIds,
    highlightedEdgePairs,
    blastRadiusNodeIds: effectiveBlastRadiusNodeIds,
    animatedNodes: effectiveAnimatedNodes,
    visibleEdgeTypes,
  });

  // Expose focusNode and refresh to parent via ref
  useImperativeHandle(ref, () => ({
    focusNode: (nodeId: string) => {
      if (knowledgeGraph) {
        const node = knowledgeGraph.nodes.find(n => n.id === nodeId);
        if (node) { selectNode(node); setCodePanelOpen(true); }
      }
      focusNode(nodeId);
    },
    refresh: () => sigmaRef.current?.refresh(),
  }), [focusNode, knowledgeGraph, selectNode, setCodePanelOpen, sigmaRef]);

  const prevLoadedCountRef = useRef(0);

  // Build Sigma graph when KnowledgeGraph changes
  useEffect(() => {
    if (!knowledgeGraph) return;
    const communityMemberships = new Map<string, number>();
    knowledgeGraph.relationships.forEach(rel => {
      if (rel.type === 'MEMBER_OF') {
        const communityNode = knowledgeGraph.nodes.find(n => n.id === rel.targetId && n.label === 'Community');
        if (communityNode) {
          const idx = parseInt(rel.targetId.replace('comm_', ''), 10) || 0;
          communityMemberships.set(rel.sourceId, idx);
        }
      }
    });

    const sigma = sigmaRef.current;
    if (sigma && prevLoadedCountRef.current > 0 && loadedCount > prevLoadedCountRef.current) {
      // Incremental append: only add new nodes/edges to existing Sigma graph
      const sigmaGraph = sigma.getGraph() as Graph<SigmaNodeAttributes, SigmaEdgeAttributes>;
      const appendGraph = knowledgeGraphToGraphology(knowledgeGraph, communityMemberships);
      appendGraph.forEachNode((id, attrs) => {
        if (!sigmaGraph.hasNode(id)) sigmaGraph.addNode(id, attrs);
      });
      appendGraph.forEachEdge((_id, attrs, src, tgt) => {
        if (sigmaGraph.hasNode(src) && sigmaGraph.hasNode(tgt) && !sigmaGraph.hasEdge(src, tgt)) {
          sigmaGraph.addEdge(src, tgt, attrs);
        }
      });
      sigma.refresh();
    } else {
      // Full rebuild
      const sigmaGraph = knowledgeGraphToGraphology(knowledgeGraph, communityMemberships);
      setSigmaGraph(sigmaGraph);
    }
    prevLoadedCountRef.current = loadedCount;
  }, [knowledgeGraph, setSigmaGraph, sigmaRef, loadedCount]);

  // Update node visibility when filters change
  useEffect(() => {
    const sigma = sigmaRef.current;
    if (!sigma) return;
    const sigmaGraph = sigma.getGraph() as Graph<SigmaNodeAttributes, SigmaEdgeAttributes>;
    if (sigmaGraph.order === 0) return;
    filterGraphByDepth(sigmaGraph, appSelectedNode?.id || null, depthFilter, visibleLabels);
    sigma.refresh();
  }, [visibleLabels, depthFilter, appSelectedNode, sigmaRef]);

  // Sync app selected node with sigma
  useEffect(() => {
    setSigmaSelectedNode(appSelectedNode ? appSelectedNode.id : null);
  }, [appSelectedNode, setSigmaSelectedNode]);

  const handleFocusSelected = useCallback(() => {
    if (appSelectedNode) focusNode(appSelectedNode.id);
  }, [appSelectedNode, focusNode]);

  const handleClearSelection = useCallback(() => {
    selectNode(null);
    setSigmaSelectedNode(null);
    resetZoom();
  }, [selectNode, setSigmaSelectedNode, resetZoom]);

  // Compute which node types are present in the current graph for the legend
  const presentNodeTypes = useMemo(() => {
    if (!knowledgeGraph) return [];
    const types = new Set<NodeLabel>();
    for (const node of knowledgeGraph.nodes) {
      if (node.label !== 'Project' && node.label !== 'Community' && node.label !== 'Process') {
        types.add(node.label);
      }
    }
    return Array.from(types).sort();
  }, [knowledgeGraph]);

  const hasGraph = knowledgeGraph && knowledgeGraph.nodes.length > 0;
  const btnBase = 'w-9 h-9 flex items-center justify-center rounded-md transition-colors cursor-pointer';
  const btnDefault = `${btnBase} bg-elevated border border-border-subtle text-text-secondary hover:bg-hover hover:text-text-primary`;

  const estimatedTime = useMemo(() => {
    if (!knowledgeGraph) return 20;
    const nodeCount = knowledgeGraph.nodes.length;
    if (nodeCount > 10000) return 45;
    if (nodeCount > 5000) return 35;
    if (nodeCount > 2000) return 30;
    if (nodeCount > 500) return 25;
    return 20;
  }, [knowledgeGraph]);

  return (
    <div className="relative w-full h-full bg-void">
      {/* Background gradient */}
      <div className="absolute inset-0 pointer-events-none" style={{
        background: 'radial-gradient(circle at center, rgba(59, 130, 246, 0.08) 0%, transparent 70%)',
      }} />

      {/* Sigma container */}
      <div ref={containerRef} className="sigma-container w-full h-full cursor-grab active:cursor-grabbing" />

      {/* Loading overlay */}
      {loading && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 z-10">
          <div className="h-8 w-8 border-2 border-accent border-t-transparent rounded-full animate-spin" />
          <span className="text-sm text-text-muted">图谱加载中...</span>
        </div>
      )}

      {/* Empty state */}
      {!loading && !hasGraph && (
        <div className="absolute inset-0 empty-state z-10">
          <div className="empty-state-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><circle cx="12" cy="12" r="3" /><circle cx="5" cy="6" r="2" /><circle cx="19" cy="6" r="2" /><circle cx="5" cy="18" r="2" /><circle cx="19" cy="18" r="2" /><path d="M7 7l3 3M14 7l-2 3M7 17l3-3M14 17l-2-3" /></svg>
          </div>
          <p className="empty-state-title">暂无图谱数据</p>
          <p className="empty-state-desc">请先完成索引或切换到包含图谱数据的项目。</p>
        </div>
      )}

      {hasGraph && (
        <>
          {/* Filter panel — top left */}
          <div className="absolute top-4 left-4 z-20">
            <GraphFilterPanel />
          </div>

          {/* Hover tooltip */}
          {hoveredNodeName && !sigmaSelectedNode && (
            <div className="absolute top-4 left-1/2 -translate-x-1/2 px-3 py-1.5 bg-elevated/95 border border-border-subtle rounded-lg backdrop-blur-sm z-20 pointer-events-none animate-fade-in">
              <span className="font-mono text-sm text-text-primary">{hoveredNodeName}</span>
            </div>
          )}

          {/* Selection info bar */}
          {sigmaSelectedNode && appSelectedNode && (
            <div className="absolute top-4 left-1/2 -translate-x-1/2 flex items-center gap-2 px-4 py-2 bg-accent/20 border border-accent/30 rounded-xl backdrop-blur-sm z-20 animate-slide-up">
              <div className="w-2 h-2 bg-accent rounded-full animate-pulse" />
              <span className="font-mono text-sm text-text-primary">{appSelectedNode.properties.name}</span>
              <span className="text-xs text-text-muted">({formatNodeLabel(appSelectedNode.label)})</span>
              <button onClick={handleClearSelection} className="ml-2 px-2 py-0.5 text-xs text-text-secondary hover:text-text-primary hover:bg-hover rounded transition-colors cursor-pointer">
                清除
              </button>
            </div>
          )}

          {/* Node type legend — bottom left */}
          {presentNodeTypes.length > 0 && (
            <div className="absolute bottom-4 left-4 flex flex-wrap gap-x-3 gap-y-1 z-10 max-w-[240px] bg-elevated/80 backdrop-blur-sm rounded-lg px-2 py-1">
              {presentNodeTypes.map(type => (
                <div key={type} className="flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ backgroundColor: NODE_COLORS[type] || '#6b7280' }} />
                  <span className="text-xs text-text-muted">{formatNodeLabel(type)}</span>
                </div>
              ))}
            </div>
          )}

          {/* Controls — bottom right */}
          <div className="absolute bottom-4 right-4 flex flex-col gap-1 z-10">
            <button onClick={zoomIn} className={btnDefault} title="放大"><ZoomIn className="w-4 h-4" /></button>
            <button onClick={zoomOut} className={btnDefault} title="缩小"><ZoomOut className="w-4 h-4" /></button>
            <button onClick={resetZoom} className={btnDefault} title="适配屏幕"><Maximize2 className="w-4 h-4" /></button>
            <div className="h-px bg-border-subtle my-1" />
            {appSelectedNode && (
              <button onClick={handleFocusSelected} className={`${btnBase} bg-accent/20 border border-accent/30 text-accent hover:bg-accent/30`} title="聚焦选中节点">
                <Focus className="w-4 h-4" />
              </button>
            )}
            {sigmaSelectedNode && (
              <button onClick={handleClearSelection} className={btnDefault} title="清除选中"><RotateCcw className="w-4 h-4" /></button>
            )}
            <div className="h-px bg-border-subtle my-1" />
            {/* 分析快捷按钮区域：选中节点后激活（用 sigmaSelectedNode 确保实时响应）*/}
            <button
              onClick={() => {
                const nodeId = sigmaSelectedNode;
                if (projectId && nodeId) runImpactView(projectId, { target_id: nodeId, direction: 'both', max_depth: 3 });
              }}
              disabled={!sigmaSelectedNode || !projectId || loading}
              className={sigmaSelectedNode && projectId ? `${btnBase} bg-red-500/15 border border-red-500/40 text-red-400 hover:bg-red-500/25` : `${btnDefault} opacity-40`}
              title={sigmaSelectedNode ? `爆炸半径分析：${sigmaSelectedNode}` : '请先在图谱中选中一个节点'}
            >
              <AlertTriangle className="w-4 h-4" />
            </button>
            <button
              onClick={() => { if (projectId) runEntryFlowView(projectId, { entry_id: sigmaSelectedNode ?? undefined, max_steps: 12 }); }}
              disabled={!projectId || loading}
              className={projectId ? `${btnBase} bg-purple-500/15 border border-purple-500/40 text-purple-400 hover:bg-purple-500/25` : `${btnDefault} opacity-40`}
              title={sigmaSelectedNode ? `执行链路追踪：${sigmaSelectedNode}` : '执行链路追踪（自动检测入口）'}
            >
              <Workflow className="w-4 h-4" />
            </button>
            <button
              onClick={() => { if (projectId) runOverviewView(projectId); }}
              disabled={!projectId || loading}
              className={projectId ? `${btnBase} bg-blue-500/15 border border-blue-500/40 text-blue-400 hover:bg-blue-500/25` : `${btnDefault} opacity-40`}
              title="重新加载全局总览"
            >
              <Layers className="w-4 h-4" />
            </button>
            <div className="h-px bg-border-subtle my-1" />
            <button onClick={isLayoutRunning ? stopLayout : startLayout}
              className={isLayoutRunning ? `${btnBase} bg-accent border-accent text-white shadow-glow animate-pulse` : btnDefault}
              title={isLayoutRunning ? '停止布局' : '执行布局'}>
              {isLayoutRunning ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
            </button>
          </div>

          {/* Layout running indicator */}
          {isLayoutRunning && (
            <div className="absolute bottom-4 left-1/2 -translate-x-1/2 flex items-center gap-2 px-3 py-1.5 bg-accent-secondary/15 border border-accent-secondary/30 rounded-full backdrop-blur-sm z-10 animate-fade-in">
              <div className="w-2 h-2 bg-accent-secondary rounded-full animate-ping" />
              <span className="text-xs text-accent-secondary font-medium">布局优化中...预计 {estimatedTime} 秒</span>
            </div>
          )}

          {/* AI Highlights toggle — top right */}
          <div className="absolute top-4 right-4 z-20">
            <button onClick={() => { if (isAIHighlightsEnabled) setHighlightedNodeIds(new Set()); toggleAIHighlights(); }}
              className={`${btnBase} ${isAIHighlightsEnabled
                ? 'bg-accent/15 border border-accent/40 text-accent hover:bg-accent/20'
                : 'bg-elevated border border-border-subtle text-text-muted hover:bg-hover hover:text-text-primary'
                }`}
              title={isAIHighlightsEnabled ? '关闭 AI 高亮' : '开启 AI 高亮'}>
              {isAIHighlightsEnabled ? <Lightbulb className="w-4 h-4" /> : <LightbulbOff className="w-4 h-4" />}
            </button>
          </div>
        </>
      )}
    </div>
  );
});

GraphCanvas.displayName = 'GraphCanvas';
