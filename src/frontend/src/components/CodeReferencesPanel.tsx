import { useCallback, useEffect, useMemo, useRef, useState, lazy, Suspense } from 'react';
import { Code, PanelLeftClose, PanelLeft, Trash2, X, FileCode, Sparkles, MousePointerClick, Target, Zap, Loader2, Copy, Check, Network, ChevronRight, Route } from 'lucide-react';
import { useGraphStore } from '@/stores/graphStore';
import { useUIStore } from '@/stores/uiStore';
import { useProjectStore } from '@/stores/projectStore';
import { navAPI } from '@/api';
import { NODE_COLORS } from '@/lib/constants';
import { formatNodeLabel } from '@/lib/nodeLabel';
import type { NodeLabel } from '@/types/graph';
import type { GinEndpointHit } from '@/api/types';
import type { NodeDetail, NeighborNode } from '@/api/types';
const CodeHighlighter = lazy(async () => {
  const mod = await import('@/components/CodeHighlighter');
  return { default: mod.CodeHighlighter };
});

const detectLanguage = (path: string): string => {
  const ext = path.split('.').pop()?.toLowerCase() || '';
  const map: Record<string, string> = {
    py: 'python', js: 'javascript', jsx: 'javascript', ts: 'typescript', tsx: 'typescript',
    go: 'go', rs: 'rust', java: 'java', rb: 'ruby', cpp: 'cpp', c: 'c', h: 'c',
  };
  return map[ext] || 'text';
};

interface CodeReferencesPanelProps {
  onFocusNode?: (nodeId: string) => void;
}

const PANEL_WIDTH_KEY = 'aletheia:codePanelWidth';

export function CodeReferencesPanel({ onFocusNode }: CodeReferencesPanelProps) {
  const { selectedNode, selectNode, fileContents, fileContentsLoading, fetchFileContent, fetchImpactAnalysis, blastRadiusNodeIds, setBlastRadiusNodeIds, selectedNodeDetail, nodeDetailLoading, fetchNodeDetail } = useGraphStore();
  const { codeReferences, removeCodeReference, clearCodeReferences, codeReferenceFocus } = useUIStore();
  const { currentProject } = useProjectStore();

  const [isCollapsed, setIsCollapsed] = useState(false);
  const [panelWidth, setPanelWidth] = useState(() => {
    const saved = localStorage.getItem(PANEL_WIDTH_KEY);
    return saved ? Number(saved) : 560;
  });
  const [glowRefId, setGlowRefId] = useState<string | null>(null);
  const [entrypointHits, setEntrypointHits] = useState<GinEndpointHit[]>([]);
  const [entrypointLoading, setEntrypointLoading] = useState(false);
  const resizeRef = useRef<{ startX: number; startWidth: number } | null>(null);
  const panelWidthRef = useRef(panelWidth);
  useEffect(() => { panelWidthRef.current = panelWidth; }, [panelWidth]);
  const refCardEls = useRef<Map<string, HTMLDivElement | null>>(new Map());
  const glowTimerRef = useRef<number | null>(null);

  useEffect(() => { return () => { if (glowTimerRef.current) window.clearTimeout(glowTimerRef.current); }; }, []);

  // Resize handle
  const startResize = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    resizeRef.current = { startX: e.clientX, startWidth: panelWidth };
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
    const onMove = (ev: MouseEvent) => {
      if (!resizeRef.current) return;
      const next = Math.max(420, Math.min(resizeRef.current.startWidth + (ev.clientX - resizeRef.current.startX), 900));
      setPanelWidth(next);
    };
    const onUp = () => {
      resizeRef.current = null;
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
      localStorage.setItem(PANEL_WIDTH_KEY, String(panelWidthRef.current));
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
    };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
  }, [panelWidth]);

  const aiReferences = useMemo(() => codeReferences.filter(r => r.source === 'ai'), [codeReferences]);

  // Auto-fetch file content for selected node and AI references
  useEffect(() => {
    if (!currentProject) return;
    const paths = new Set<string>();
    if (selectedNode?.properties?.filePath) paths.add(selectedNode.properties.filePath);
    aiReferences.forEach(r => paths.add(r.filePath));
    paths.forEach(p => {
      if (!fileContents.has(p) && !fileContentsLoading.has(p)) {
        fetchFileContent(currentProject.name, p);
      }
    });
  }, [selectedNode, aiReferences, currentProject, fileContents, fileContentsLoading, fetchFileContent]);

  // Fetch node detail when selected node changes
  useEffect(() => {
    if (!selectedNode || !currentProject) return;
    fetchNodeDetail(currentProject.name, selectedNode.id);
  }, [selectedNode?.id, currentProject?.name]);

  // Reverse lookup entrypoints for current node
  useEffect(() => {
    let cancelled = false;
    if (!selectedNode || !currentProject) {
      setEntrypointHits([]);
      return;
    }
    setEntrypointLoading(true);
    navAPI.reverseLookupEntrypoint(currentProject.name, selectedNode.id, 8)
      .then((res) => { if (!cancelled) setEntrypointHits(res.hits); })
      .catch(() => { if (!cancelled) setEntrypointHits([]); })
      .finally(() => { if (!cancelled) setEntrypointLoading(false); });
    return () => { cancelled = true; };
  }, [selectedNode?.id, currentProject?.name]);

  // Focus effect when citation is clicked in chat
  useEffect(() => {
    if (!codeReferenceFocus) return;
    setIsCollapsed(false);
    const { filePath, startLine, endLine } = codeReferenceFocus;
    const target = aiReferences.find(r => r.filePath === filePath && r.startLine === startLine && r.endLine === endLine)
      ?? aiReferences.find(r => r.filePath === filePath);
    if (!target) return;
    requestAnimationFrame(() => requestAnimationFrame(() => {
      const el = refCardEls.current.get(target.id);
      if (!el) return;
      el.scrollIntoView({ behavior: 'smooth', block: 'center' });
      setGlowRefId(target.id);
      if (glowTimerRef.current) window.clearTimeout(glowTimerRef.current);
      glowTimerRef.current = window.setTimeout(() => {
        setGlowRefId(prev => prev === target.id ? null : prev);
        glowTimerRef.current = null;
      }, 1200);
    }));
  }, [codeReferenceFocus, aiReferences]);

  const selectedFilePath = selectedNode?.properties?.filePath;
  const selectedFileContent = selectedFilePath ? fileContents.get(selectedFilePath) : undefined;
  const selectedFileLoading = selectedFilePath ? fileContentsLoading.has(selectedFilePath) : false;
  const showSelectedViewer = !!selectedNode && !!selectedFilePath;
  const showCitations = aiReferences.length > 0;

  if (isCollapsed) {
    return (
      <aside className="h-full w-12 bg-surface border-r border-border-subtle flex flex-col items-center py-3 gap-2 flex-shrink-0">
        <button onClick={() => setIsCollapsed(false)} className="icon-button cursor-pointer" title="展开代码面板">
          <PanelLeft className="w-5 h-5" />
        </button>
        <div className="w-6 h-px bg-border-subtle my-1" />
        {showSelectedViewer && <div className="chip chip-accent rotate-90 whitespace-nowrap">选中</div>}
        {showCitations && <div className="chip chip-secondary rotate-90 whitespace-nowrap mt-4">AI · {aiReferences.length}</div>}
      </aside>
    );
  }

  return (
    <aside className="h-full bg-surface/95 backdrop-blur-md border-r border-border-subtle flex flex-col animate-slide-in relative shadow-2xl" style={{ width: panelWidth }}>
      {/* Resize handle */}
      <div onMouseDown={startResize} className="absolute top-0 right-0 h-full w-2 cursor-col-resize bg-transparent hover:bg-accent/20 transition-colors" title="拖拽调整宽度" />

      {/* Header */}
      <div className="panel-header">
        <div className="flex items-center gap-2">
          <Code className="w-4 h-4 text-accent" />
          <span className="panel-header-title">代码检视</span>
        </div>
        <div className="flex items-center gap-1.5">
          {showCitations && (
            <button onClick={() => clearCodeReferences()} className="icon-button hover:text-error hover:bg-error/10 transition-colors cursor-pointer" title="清空 AI 引用">
              <Trash2 className="w-4 h-4" />
            </button>
          )}
          <button onClick={() => setIsCollapsed(true)} className="icon-button transition-colors cursor-pointer" title="收起面板">
            <PanelLeftClose className="w-4 h-4" />
          </button>
        </div>
      </div>

      <div className="flex-1 min-h-0 flex flex-col">
        {/* Selected file viewer */}
        {showSelectedViewer && (
          <SelectedFileViewer
            selectedNode={selectedNode!}
            filePath={selectedFilePath!}
            content={selectedFileContent}
            loading={selectedFileLoading}
            onClear={() => selectNode(null)}
            flexClass={showCitations ? 'h-[42%]' : 'flex-1'}
            onImpactAnalysis={currentProject ? (nodeId) => fetchImpactAnalysis(currentProject.name, nodeId) : undefined}
            blastRadiusNodeIds={blastRadiusNodeIds}
            onClearImpact={() => setBlastRadiusNodeIds(new Set())}
            entrypointHits={entrypointHits}
            entrypointLoading={entrypointLoading}
          />
        )}

        {/* Node detail: neighbors */}
        {selectedNode && (
          <NodeDetailSection
            detail={selectedNodeDetail}
            loading={nodeDetailLoading}
            onFocusNode={onFocusNode}
          />
        )}

        {/* AI citation snippets */}
        {showCitations && (
          <div className={`${showSelectedViewer ? 'flex-1' : 'flex-1'} min-h-0 flex flex-col`}>
            <div className="px-3 py-2 bg-gradient-to-r from-accent/8 to-accent/4 border-b border-accent/20 flex items-center gap-2">
              <Sparkles className="w-3.5 h-3.5 text-accent" />
              <span className="section-title text-accent">AI 引用</span>
              <span className="text-xs text-text-muted ml-auto">{aiReferences.length}</span>
            </div>
            <div className="flex-1 overflow-y-auto scrollbar-thin p-2 space-y-2">
              {aiReferences.map(ref => {
                const content = fileContents.get(ref.filePath);
                const loading = fileContentsLoading.has(ref.filePath);
                const isGlowing = glowRefId === ref.id;
                return (
                  <div
                    key={ref.id}
                    ref={el => { refCardEls.current.set(ref.id, el); }}
                    className={`rounded-lg border overflow-hidden transition-all ${isGlowing ? 'border-accent/60 shadow-[0_0_12px_rgba(37,99,235,0.25)]' : 'border-border-subtle'}`}
                  >
                    <div className="flex items-center gap-1.5 px-3 py-1.5 bg-elevated/80">
                      {/* Node type color label */}
                      {ref.label && (
                        <span
                          className="chip"
                          style={{
                            color: NODE_COLORS[ref.label as NodeLabel] || '#9ca3af',
                            backgroundColor: `${NODE_COLORS[ref.label as NodeLabel] || '#9ca3af'}20`,
                          }}
                        >
                          {formatNodeLabel(ref.label as NodeLabel)}
                        </span>
                      )}
                      <FileCode className="w-3 h-3 text-accent/80" />
                      <span className="text-xs font-mono text-text-primary truncate flex-1" title={ref.filePath}>
                        {ref.filePath}
                      </span>
                      {ref.startLine != null && (
                        <span className="text-xs text-text-muted shrink-0">
                          L{ref.startLine + 1}{ref.endLine != null && ref.endLine !== ref.startLine ? `-${ref.endLine + 1}` : ''}
                          {ref.endLine != null && ref.endLine > ref.startLine && (
                            <span className="text-text-muted/60 ml-0.5">({ref.endLine - ref.startLine + 1})</span>
                          )}
                        </span>
                      )}
                      {/* 在图谱中定位 button */}
                      {ref.nodeId && onFocusNode && (
                        <button
                          onClick={() => onFocusNode(ref.nodeId!)}
                          className="icon-button p-0.5 cursor-pointer"
                          title="在图谱中定位"
                        >
                          <Target className="w-3 h-3" />
                        </button>
                      )}
                      <button onClick={() => removeCodeReference(ref.id)} className="p-0.5 text-text-muted hover:text-error rounded transition-colors cursor-pointer">
                        <X className="w-3 h-3" />
                      </button>
                    </div>
                    <div className="max-h-48 overflow-auto scrollbar-thin">
                      {loading ? (
                        <div className="px-3 py-4 text-xs text-text-muted animate-pulse">文件内容加载中...</div>
                      ) : content ? (
                        <HighlightedSnippet content={content} startLine={ref.startLine} endLine={ref.endLine} language={detectLanguage(ref.filePath)} />
                      ) : (
                        <div className="px-3 py-3 text-xs text-text-muted">文件内容不可用</div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Empty state */}
        {!showSelectedViewer && !showCitations && (
          <div className="flex-1 flex flex-col items-center justify-center text-center px-6">
            <MousePointerClick className="w-8 h-8 text-text-muted/30 mb-3" />
            <p className="text-sm text-text-muted">请在图谱中选择节点，或通过 AI 问答查看代码证据</p>
          </div>
        )}
      </div>
    </aside>
  );
}

// ── Helper: Selected file viewer ──

interface SelectedFileViewerProps {
  selectedNode: { id: string; properties: { filePath?: string; name: string; startLine?: number; endLine?: number }; label: string };
  filePath: string;
  content: string | undefined;
  loading: boolean;
  onClear: () => void;
  flexClass: string;
  onImpactAnalysis?: (nodeId: string) => Promise<void>;
  blastRadiusNodeIds?: Set<string>;
  onClearImpact?: () => void;
  entrypointHits?: GinEndpointHit[];
  entrypointLoading?: boolean;
}

function SelectedFileViewer({ selectedNode, filePath, content, loading, onClear, flexClass, onImpactAnalysis, blastRadiusNodeIds, onClearImpact, entrypointHits = [], entrypointLoading = false }: SelectedFileViewerProps) {
  const [impactLoading, setImpactLoading] = useState(false);
  const [codeCopied, setCodeCopied] = useState(false);
  const hasBlastRadius = blastRadiusNodeIds && blastRadiusNodeIds.size > 0;

  const handleCopyCode = useCallback(() => {
    if (!content) return;
    navigator.clipboard.writeText(content).then(() => {
      setCodeCopied(true);
      setTimeout(() => setCodeCopied(false), 1500);
    }).catch(() => {});
  }, [content]);

  return (
    <div className={`${flexClass} min-h-0 flex flex-col`}>
      <div className="px-3 py-2 bg-gradient-to-r from-accent/10 to-accent/5 border-b border-accent/20 flex items-center gap-2">
        <div className="chip chip-accent">
          <MousePointerClick className="w-3 h-3 text-accent" />
          <span>选中</span>
        </div>
        <FileCode className="w-3.5 h-3.5 text-accent/80 ml-1" />
        <span className="text-xs text-text-primary font-mono truncate flex-1">
          {filePath.split('/').pop() ?? selectedNode.properties.name}
        </span>
        {content && (
          <button
            onClick={handleCopyCode}
            className="icon-button p-1 cursor-pointer"
            title="复制代码"
          >
            {codeCopied ? <Check className="w-3.5 h-3.5 text-accent-secondary" /> : <Copy className="w-3.5 h-3.5" />}
          </button>
        )}
        {onImpactAnalysis && (
          hasBlastRadius ? (
            <button
              onClick={onClearImpact}
              className="chip chip-error hover:bg-error/15 transition-colors cursor-pointer"
              title="清除影响分析"
            >
              <X className="w-3 h-3" />
              清除
            </button>
          ) : (
            <button
              disabled={impactLoading}
              onClick={async () => {
                setImpactLoading(true);
                try { await onImpactAnalysis(selectedNode.id); }
                finally { setImpactLoading(false); }
              }}
              className="chip chip-accent hover:bg-accent/15 transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
              title="分析影响范围"
            >
              {impactLoading ? <Loader2 className="w-3 h-3 animate-spin" /> : <Zap className="w-3 h-3" />}
              {impactLoading ? '分析中...' : '影响'}
            </button>
          )
        )}
        <button onClick={onClear} className="icon-button p-1 cursor-pointer" title="清除选中">
          <X className="w-4 h-4" />
        </button>
      </div>
      <div className="flex-1 min-h-0 overflow-auto scrollbar-thin">
        {(entrypointLoading || entrypointHits.length > 0) && (
          <div className="px-3 py-2 border-b border-border-subtle bg-elevated/50">
            <div className="flex items-center gap-1.5 mb-1">
              <Route className="w-3 h-3 text-accent" />
              <span className="section-kicker">接口入口映射</span>
            </div>
            {entrypointLoading ? (
              <div className="text-xs text-text-muted flex items-center gap-1.5">
                <Loader2 className="w-3 h-3 animate-spin" />
                查找中...
              </div>
            ) : (
              <div className="space-y-1">
                {entrypointHits.slice(0, 4).map((hit, idx) => (
                  <div key={`${hit.route}-${idx}`} className="text-xs text-text-secondary rounded-lg border border-border-subtle bg-surface px-2 py-1">
                    <span className="chip chip-accent font-mono mr-1">{hit.method}</span>
                    <span className="font-mono text-text-primary">{hit.route}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
        {loading ? (
          <div className="px-4 py-8 text-center text-sm text-text-muted animate-pulse">文件加载中...</div>
        ) : content ? (
          <HighlightedSnippet
            content={content}
            startLine={selectedNode.properties.startLine}
            endLine={selectedNode.properties.endLine}
            language={detectLanguage(filePath)}
            showFullFile
          />
        ) : (
          <div className="px-3 py-3 text-sm text-text-muted">
            当前文件暂不可用： <span className="font-mono">{filePath}</span>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Helper: Syntax-highlighted code snippet ──

interface HighlightedSnippetProps {
  content: string;
  startLine?: number;
  endLine?: number;
  language: string;
  showFullFile?: boolean;
}

function HighlightedSnippet({ content, startLine, endLine, language, showFullFile }: HighlightedSnippetProps) {
  const lines = content.split('\n');
  const total = lines.length;

  let dStart: number, dEnd: number;
  if (showFullFile) {
    dStart = 0; dEnd = total - 1;
  } else {
    const s = startLine ?? 0;
    const e = endLine ?? s;
    dStart = Math.max(0, s - 3);
    dEnd = Math.min(total - 1, e + 20);
  }

  const displayCode = lines.slice(dStart, dEnd + 1).join('\n');
  const hlStart = startLine != null ? startLine + 1 : -1;
  const hlEnd = endLine != null ? endLine + 1 : hlStart;

  return (
    <Suspense
      fallback={(
        <pre className="m-0 bg-void px-3 py-3 text-[13px] text-text-secondary overflow-x-auto">
          <code>{displayCode}</code>
        </pre>
      )}
    >
      <CodeHighlighter
        code={displayCode}
        language={language}
        showLineNumbers
        startingLineNumber={dStart + 1}
        wrapLines
        lineProps={(lineNumber: number) => {
          const isHL = hlStart > 0 && lineNumber >= hlStart && lineNumber <= hlEnd;
          return {
            style: {
              backgroundColor: isHL ? 'rgba(37, 99, 235, 0.12)' : undefined,
              borderLeft: isHL ? '3px solid #2563eb' : '3px solid transparent',
              display: 'block',
              paddingLeft: '0.5em',
            },
          };
        }}
        customStyle={{
          margin: 0,
          padding: '0.5em 0',
          background: 'transparent',
          fontSize: '13px',
        }}
        className="bg-void"
      />
    </Suspense>
  );
}

// ── Helper: Node detail section (neighbors) ──

interface NodeDetailSectionProps {
  detail: NodeDetail | null;
  loading: boolean;
  onFocusNode?: (nodeId: string) => void;
}

function NodeDetailSection({ detail, loading, onFocusNode }: NodeDetailSectionProps) {
  const [expanded, setExpanded] = useState(true);

  if (loading) {
    return (
      <div className="px-3 py-2 border-t border-border-subtle flex items-center gap-2 text-xs text-text-muted">
        <Loader2 className="w-3 h-3 animate-spin" />
        邻居加载中...
      </div>
    );
  }

  if (!detail) return null;

  const allNeighbors = Object.entries(detail.neighbors);
  if (allNeighbors.length === 0) return null;

  const outgoing = allNeighbors.flatMap(([rel, nodes]) =>
    nodes.filter(n => n.direction === 'outgoing').map(n => ({ ...n, rel }))
  );
  const incoming = allNeighbors.flatMap(([rel, nodes]) =>
    nodes.filter(n => n.direction === 'incoming').map(n => ({ ...n, rel }))
  );

  return (
    <div className="border-t border-border-subtle flex-shrink-0">
      <button
        onClick={() => setExpanded(e => !e)}
        className="w-full flex items-center gap-2 px-3 py-2 bg-gradient-to-r from-accent/8 to-accent/4 hover:from-accent/12 transition-colors cursor-pointer"
      >
        <Network className="w-3.5 h-3.5 text-accent" />
        <span className="section-kicker text-accent">关联节点</span>
        <span className="chip chip-muted ml-auto">{outgoing.length + incoming.length}</span>
        <ChevronRight className={`w-3 h-3 text-text-muted transition-transform ${expanded ? 'rotate-90' : ''}`} />
      </button>

      {expanded && (
        <div className="max-h-48 overflow-y-auto scrollbar-thin px-2 py-1.5 space-y-1">
          {outgoing.length > 0 && (
            <NeighborGroup label="出向" nodes={outgoing} onFocusNode={onFocusNode} />
          )}
          {incoming.length > 0 && (
            <NeighborGroup label="入向" nodes={incoming} onFocusNode={onFocusNode} />
          )}
        </div>
      )}
    </div>
  );
}

function NeighborGroup({
  label,
  nodes,
  onFocusNode,
}: {
  label: string;
  nodes: (NeighborNode & { rel: string })[];
  onFocusNode?: (nodeId: string) => void;
}) {
  return (
    <div>
      <div className="section-kicker px-1 py-0.5">{label}</div>
      {nodes.map((n, i) => {
        const color = NODE_COLORS[n.type as NodeLabel] || '#6b7280';
        return (
          <div key={`${n.id}-${i}`} className="flex items-center gap-1.5 px-1 py-0.5 rounded hover:bg-hover group">
            <span className="w-1.5 h-1.5 rounded-full flex-shrink-0" style={{ backgroundColor: color }} />
            <span className="text-xs text-text-muted shrink-0 font-mono">{n.rel}</span>
            <span className="text-xs text-text-primary font-mono truncate flex-1">{n.name}</span>
            {onFocusNode && (
              <button
                onClick={() => onFocusNode(n.id)}
                className="icon-button opacity-0 group-hover:opacity-100 p-0.5 transition-all cursor-pointer"
                title="在图谱中定位"
              >
                <Target className="w-3 h-3" />
              </button>
            )}
          </div>
        );
      })}
    </div>
  );
}
