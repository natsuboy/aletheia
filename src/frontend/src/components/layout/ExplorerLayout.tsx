import { useEffect, useRef, useCallback, lazy, Suspense, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useProjectStore } from '@/stores/projectStore';
import { useGraphStore } from '@/stores/graphStore';
import { useUIStore } from '@/stores/uiStore';
import { useChatStore } from '@/stores/chatStore';
import { Header } from './Header';
import { FileTreePanel } from '@/components/FileTreePanel';
import { GraphCanvas, GraphCanvasHandle } from '@/components/graph/GraphCanvas';
import { AnalysisPanel } from '@/components/graph/AnalysisPanel';
import { StatusBar } from '@/components/StatusBar';
import { QueryFAB } from '@/components/QueryFAB';
import { WorkflowRail } from './WorkflowRail';
import { CommandPalette } from './CommandPalette';

const CodeReferencesPanel = lazy(async () => {
  const mod = await import('@/components/CodeReferencesPanel');
  return { default: mod.CodeReferencesPanel };
});
const RightPanel = lazy(async () => {
  const mod = await import('@/components/RightPanel');
  return { default: mod.RightPanel };
});
const WikiBrowser = lazy(async () => {
  const mod = await import('@/components/wiki/WikiBrowser');
  return { default: mod.WikiBrowser };
});

export function ExplorerLayout() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const graphCanvasRef = useRef<GraphCanvasHandle>(null);

  const { fetchProjects, setCurrentProject } = useProjectStore();
  const { fetchGraphData, fetchStats, fetchAnalysisStatus, selectNode, selectedNode } = useGraphStore();
  const { setViewMode, viewMode, isCodePanelOpen, isFileTreeOpen, isRightPanelOpen, setCodePanelOpen, toggleRightPanel } = useUIStore();
  const { loadHistory } = useChatStore();
  const [railCollapsed, setRailCollapsed] = useState(false);

  // Load project data on mount
  useEffect(() => {
    if (!projectId) return;
    setViewMode('exploring');

    const init = async () => {
      await fetchProjects();
      const proj = useProjectStore.getState().projects.find(
        (p) => p.id === projectId || p.name === projectId,
      );
      if (proj) {
        setCurrentProject(proj);
        loadHistory(projectId);
        await fetchGraphData(projectId);
        await Promise.all([
          fetchStats(projectId),
          fetchAnalysisStatus(projectId),
        ]);
      } else {
        navigate('/');
      }
    };
    init();
  }, [projectId]);

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        // Priority: selectedNode → codePanel → rightPanel
        if (selectedNode) {
          selectNode(null);
        } else if (isCodePanelOpen) {
          setCodePanelOpen(false);
        } else if (isRightPanelOpen) {
          toggleRightPanel();
        }
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [selectedNode, selectNode, isCodePanelOpen, setCodePanelOpen, isRightPanelOpen, toggleRightPanel]);

  // When switching back to graph view, refresh Sigma so it recalculates size
  useEffect(() => {
    if (viewMode === 'exploring') {
      requestAnimationFrame(() => requestAnimationFrame(() => graphCanvasRef.current?.refresh?.()));
    }
  }, [viewMode]);

  const handleFocusNode = useCallback((nodeId: string) => {
    graphCanvasRef.current?.focusNode(nodeId);
  }, []);

  return (
    <div className="h-screen flex flex-col app-shell">
      <Header onFocusNode={handleFocusNode} />

      <div className="flex-1 flex overflow-hidden">
        <WorkflowRail collapsed={railCollapsed} onToggleCollapse={() => setRailCollapsed((v) => !v)} />

        {/* Left sidebar: FileTree in graph mode, hidden in wiki mode */}
        {viewMode !== 'wiki' && isFileTreeOpen && (
          <FileTreePanel onFocusNode={handleFocusNode} />
        )}

        {/* Code References Panel (push layout, graph mode only) */}
        {viewMode !== 'wiki' && isCodePanelOpen && (
          <Suspense fallback={<div className="w-[420px] bg-surface border-r border-border-subtle" />}>
            <CodeReferencesPanel onFocusNode={handleFocusNode} />
          </Suspense>
        )}

        {/* Central area: Graph Canvas + Wiki Browser (both mounted, CSS controls visibility) */}
        <div className={viewMode === 'wiki' ? 'hidden' : 'flex flex-1 relative min-w-0'}>
          <GraphCanvas ref={graphCanvasRef} />
          <AnalysisPanel />
          <QueryFAB />
        </div>
        {viewMode === 'wiki' && (
          <Suspense fallback={<div className="flex-1 bg-surface" />}>
            <WikiBrowser />
          </Suspense>
        )}

        {/* Right Panel (Chat) — always available */}
        {isRightPanelOpen && (
          <Suspense fallback={<div className="w-[420px] bg-surface border-l border-border-subtle" />}>
            <RightPanel />
          </Suspense>
        )}
      </div>

      <CommandPalette onFocusNode={handleFocusNode} />
      <StatusBar />
    </div>
  );
}
