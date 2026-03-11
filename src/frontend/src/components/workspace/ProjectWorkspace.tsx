import { useEffect, useRef, Suspense, lazy } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { useProjectStore } from '../../stores/projectStore';
import { useGraphStore } from '../../stores/graphStore';
import { useUIStore } from '../../stores/uiStore';
import { useChatStore } from '../../stores/chatStore';
import { TopBar } from './TopBar';
import { FileTreePanel } from '@/components/FileTreePanel';
import { InspectorPanel } from './InspectorPanel';
import { GraphCanvas, GraphCanvasHandle } from '../graph/GraphCanvas';
import { CommandPalette } from '../layout/CommandPalette';
import { AnalysisPanel } from '../graph/AnalysisPanel';

const WikiBrowser = lazy(async () => {
  const mod = await import('../wiki/WikiBrowser');
  return { default: mod.WikiBrowser };
});

export function ProjectWorkspace() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const graphCanvasRef = useRef<GraphCanvasHandle>(null);

  const { fetchProjects, setCurrentProject, currentProject } = useProjectStore();
  const { fetchGraphData, fetchStats, fetchAnalysisStatus, knowledgeGraph } = useGraphStore();
  const { setViewMode, viewMode, isFileTreeOpen, toggleFileTree, isRightPanelOpen, toggleRightPanel } = useUIStore();
  const { loadHistory } = useChatStore();

  useEffect(() => {
    if (!projectId) return;
    setViewMode('exploring');

    const init = async () => {
      try {
        await fetchProjects();
        const proj = useProjectStore.getState().projects.find(
          (p) => p.id === projectId || p.name === projectId
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
      } catch (error) {
        console.error('Failed to initialize workspace:', error);
        toast.error('加载项目失败');
      }
    };

    init();
  }, [projectId, fetchProjects, setCurrentProject, loadHistory, fetchGraphData, fetchStats, fetchAnalysisStatus, navigate, setViewMode]);

  return (
    <div className="h-screen w-screen relative overflow-hidden bg-void text-text-primary selection:bg-accent/30 app-shell">
      {/* 
        LAYER 0: The Graph Canvas / Wiki.
        This fills the entire screen underneath everything else. 
      */}
      <div className="absolute inset-0 z-0">
        {viewMode === 'exploring' && (
          <GraphCanvas ref={graphCanvasRef} />
        )}
        {viewMode === 'wiki' && (
          <Suspense fallback={<div className="empty-state h-full"><div className="empty-state-title">加载中...</div></div>}>
            <WikiBrowser />
          </Suspense>
        )}
      </div>

      {/* 
        LAYER 1: UI Overlays. 
        pointer-events-none on the container allows clicking through to canvas,
        but pointer-events-auto on the children makes the UI interactive.
      */}
      <div className="absolute inset-0 z-10 pointer-events-none flex flex-col pt-[72px]">
        {/* TopBar Floating */}
        <div className="absolute top-4 left-4 right-4 h-14 z-20 pointer-events-auto">
          <TopBar
            projectName={currentProject?.name || 'Aletheia'}
            leftOpen={isFileTreeOpen && viewMode !== 'wiki'}
            rightOpen={isRightPanelOpen}
            onToggleLeft={toggleFileTree}
            onToggleRight={toggleRightPanel}
          />
        </div>

        {/* Floating Side Panels */}
        <div className="flex-1 w-full relative">
          {viewMode !== 'wiki' && isFileTreeOpen && (
            <div className="absolute left-4 top-0 bottom-4 pointer-events-auto flex z-10">
              <FileTreePanel onFocusNode={(id) => graphCanvasRef.current?.focusNode(id)} />
            </div>
          )}

          {viewMode === 'exploring' && (
            <AnalysisPanel />
          )}

          <div className="absolute right-4 top-0 bottom-4 pointer-events-auto flex z-10">
            <InspectorPanel />
          </div>
        </div>
      </div>

      <CommandPalette onFocusNode={(id) => graphCanvasRef.current?.focusNode(id)} />
    </div>
  );
}
