import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { X, Search, Route, GitBranch, MessageSquare, FileCode2, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { navAPI } from '@/api';
import type { GinEndpointHit, NavReferenceNode } from '@/api/types';
import { useProjectStore } from '@/stores/projectStore';
import { useGraphStore } from '@/stores/graphStore';
import { useUIStore } from '@/stores/uiStore';
import { useChatStore } from '@/stores/chatStore';
import { formatNodeLabel } from '@/lib/nodeLabel';
import type { GraphNode } from '@/types/graph';

type PaletteMode = 'mixed' | 'endpoint' | 'refs' | 'ask';

interface CommandPaletteProps {
  onFocusNode?: (nodeId: string) => void;
}

function parseFileLine(input: string): { filePath: string; startLine?: number } | null {
  const raw = input.trim();
  if (!raw) return null;
  const m = raw.match(/^(.*):(\d+)$/);
  if (!m) return { filePath: raw };
  return { filePath: m[1].trim(), startLine: Number(m[2]) };
}

function parsePrefixedQuery(input: string, fallbackMode: PaletteMode): { mode: PaletteMode; query: string } {
  const raw = input.trim();
  if (!raw) return { mode: fallbackMode, query: '' };
  const m = raw.match(/^(endpoint|refs|ask|接口|引用|提问)\s+(.+)$/i);
  if (!m) return { mode: fallbackMode, query: raw };
  const cmd = m[1].toLowerCase();
  const query = m[2].trim();
  if (cmd === 'endpoint' || cmd === '接口') return { mode: 'endpoint', query };
  if (cmd === 'refs' || cmd === '引用') return { mode: 'refs', query };
  return { mode: 'ask', query };
}

export function CommandPalette({ onFocusNode }: CommandPaletteProps) {
  const { currentProject } = useProjectStore();
  const { knowledgeGraph, searchNodes, searchResults, selectNode, setHighlightedNodeIds } = useGraphStore();
  const { addCodeReference, setCodePanelOpen, setRightPanelTab, addOperation } = useUIStore();
  const { sendMessage } = useChatStore();

  const [open, setOpen] = useState(false);
  const [input, setInput] = useState('');
  const [mode, setMode] = useState<PaletteMode>('mixed');
  const [endpointHits, setEndpointHits] = useState<GinEndpointHit[]>([]);
  const [refPreview, setRefPreview] = useState<NavReferenceNode[]>([]);
  const [loading, setLoading] = useState(false);

  const inputRef = useRef<HTMLInputElement>(null);

  const parsed = useMemo(() => parsePrefixedQuery(input, mode), [input, mode]);
  const effectiveMode = parsed.mode;
  const normalizedInput = parsed.query;
  const projectId = currentProject?.name ?? '';

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setOpen(true);
      }
      if (e.key === 'Escape' && open) {
        e.preventDefault();
        setOpen(false);
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [open]);

  useEffect(() => {
    const handler = (e: Event) => {
      const customEvent = e as CustomEvent<{ initialQuery?: string; mode?: PaletteMode }>;
      setOpen(true);
      if (customEvent.detail?.initialQuery) setInput(customEvent.detail.initialQuery);
      if (customEvent.detail?.mode) setMode(customEvent.detail.mode);
    };
    window.addEventListener('aletheia:open-command', handler as EventListener);
    return () => window.removeEventListener('aletheia:open-command', handler as EventListener);
  }, []);

  useEffect(() => {
    if (open) {
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }, [open]);

  const openCodeRef = useCallback((filePath: string, startLine1?: number, nodeId?: string, name?: string) => {
    addCodeReference({
      id: `cmd-${Date.now()}`,
      filePath,
      startLine: startLine1 ? Math.max(0, startLine1 - 1) : undefined,
      endLine: startLine1 ? Math.max(0, startLine1 - 1) : undefined,
      nodeId,
      label: '文件',
      name: name ?? filePath.split('/').pop() ?? filePath,
      source: 'user',
    });
    setCodePanelOpen(true);
  }, [addCodeReference, setCodePanelOpen]);

  const focusGraphNode = useCallback((nodeId: string) => {
    const node = knowledgeGraph?.nodes.find((n) => n.id === nodeId) ?? null;
    if (node) selectNode(node);
    onFocusNode?.(nodeId);
  }, [knowledgeGraph, selectNode, onFocusNode]);

  useEffect(() => {
    let disposed = false;
    if (!open || !projectId || !normalizedInput) {
      setEndpointHits([]);
      setRefPreview([]);
      return;
    }

    const timer = setTimeout(async () => {
      setLoading(true);
      try {
        if (effectiveMode === 'mixed' || effectiveMode === 'endpoint') {
          const endpointRes = await navAPI.searchGinEndpoints(projectId, normalizedInput, 8);
          if (!disposed) setEndpointHits(endpointRes.hits);
        } else {
          setEndpointHits([]);
        }

        if (effectiveMode === 'mixed') {
          await searchNodes(projectId, normalizedInput);
        }

        if (effectiveMode === 'refs') {
          const refRes = await navAPI.getReferences(projectId, normalizedInput, 'both', 2, 120);
          if (!disposed) setRefPreview(refRes.nodes.slice(0, 8));
        } else {
          setRefPreview([]);
        }
      } catch (err) {
        if (!disposed) {
          const msg = err instanceof Error ? err.message : '命令检索失败';
          toast.error(msg);
          setEndpointHits([]);
          setRefPreview([]);
        }
      } finally {
        if (!disposed) setLoading(false);
      }
    }, 180);

    return () => {
      disposed = true;
      clearTimeout(timer);
    };
  }, [open, projectId, normalizedInput, effectiveMode, searchNodes]);

  const mixedNodeResults = useMemo(() => (effectiveMode === 'mixed' ? searchResults.slice(0, 8) : []), [effectiveMode, searchResults]);

  const handlePickGraphNode = useCallback((node: GraphNode) => {
    selectNode(node);
    setCodePanelOpen(true);
    onFocusNode?.(node.id);
    if (node.properties.filePath) {
      openCodeRef(node.properties.filePath, node.properties.startLine, node.id, node.properties.name);
    }
    addOperation({ kind: 'node', label: `节点: ${node.properties.name}` });
    setOpen(false);
  }, [onFocusNode, openCodeRef, selectNode, setCodePanelOpen, addOperation]);

  const handlePickEndpoint = useCallback((hit: GinEndpointHit) => {
    openCodeRef(hit.file_path, hit.start_line, hit.node_id, hit.handler_symbol);
    if (hit.node_id) focusGraphNode(hit.node_id);
    addOperation({ kind: 'endpoint', label: `${hit.method} ${hit.route}` });
    setOpen(false);
  }, [focusGraphNode, openCodeRef, addOperation]);

  const handleRunReferences = useCallback(async () => {
    if (!projectId || !normalizedInput) return;
    try {
      setLoading(true);
      const refRes = await navAPI.getReferences(projectId, normalizedInput, 'both', 2, 400);
      const ids = new Set(refRes.nodes.map((n) => n.id));
      setHighlightedNodeIds(ids);
      focusGraphNode(refRes.center_node_id);
      const center = refRes.nodes.find((n) => n.id === refRes.center_node_id);
      if (center?.file_path) {
        openCodeRef(center.file_path, center.start_line, center.id, center.name || normalizedInput);
      }
      addOperation({ kind: 'references', label: `引用: ${normalizedInput}` });
      toast.success(`已加载引用关系：${refRes.stats.edge_count ?? refRes.edges.length} 条边`);
      setOpen(false);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '引用关系查询失败');
    } finally {
      setLoading(false);
    }
  }, [focusGraphNode, normalizedInput, openCodeRef, projectId, setHighlightedNodeIds, addOperation]);

  const handleAsk = useCallback(async () => {
    if (!projectId || !normalizedInput) return;
    setRightPanelTab('chat');
    await sendMessage(normalizedInput, projectId);
    addOperation({ kind: 'chat', label: `问答: ${normalizedInput.slice(0, 48)}` });
    setOpen(false);
  }, [normalizedInput, projectId, sendMessage, setRightPanelTab, addOperation]);

  const handleOpenFile = useCallback(() => {
    if (!normalizedInput) return;
    const parsed = parseFileLine(normalizedInput);
    if (!parsed) return;
    openCodeRef(parsed.filePath, parsed.startLine);
    addOperation({ kind: 'file', label: `文件: ${parsed.filePath}${parsed.startLine ? `:${parsed.startLine}` : ''}` });
    setOpen(false);
  }, [normalizedInput, openCodeRef, addOperation]);

  const canShowOpenFileAction = normalizedInput.includes('/');

  const handleEnterExecute = useCallback(async () => {
    if (!normalizedInput) return;
    if (effectiveMode === 'ask') {
      await handleAsk();
      return;
    }
    if (effectiveMode === 'refs') {
      await handleRunReferences();
      return;
    }
    if (effectiveMode === 'endpoint' && endpointHits.length > 0) {
      handlePickEndpoint(endpointHits[0]);
      return;
    }
    if (effectiveMode === 'mixed') {
      if (endpointHits.length > 0) {
        handlePickEndpoint(endpointHits[0]);
        return;
      }
      if (mixedNodeResults.length > 0) {
        handlePickGraphNode(mixedNodeResults[0]);
        return;
      }
      if (canShowOpenFileAction) {
        handleOpenFile();
      }
    }
  }, [
    normalizedInput,
    effectiveMode,
    handleAsk,
    handleRunReferences,
    endpointHits,
    mixedNodeResults,
    canShowOpenFileAction,
    handlePickEndpoint,
    handlePickGraphNode,
    handleOpenFile,
  ]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[60] bg-black/45 backdrop-blur-[1px] flex items-start justify-center pt-[10vh]">
      <div className="w-[760px] max-w-[95vw] overflow-hidden rounded-2xl border border-border-default bg-deep shadow-[0_28px_58px_rgba(14,116,184,0.24)]">
        <div className="panel-header gap-2">
          <Search className="w-4 h-4 text-text-muted" />
          <input
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault();
                void handleEnterExecute();
              }
            }}
            placeholder="输入命令或关键词：接口 / 引用 / 提问 / 文件路径"
            className="flex-1 bg-transparent outline-none text-sm text-text-primary placeholder:text-text-muted"
          />
          {loading && <Loader2 className="w-4 h-4 text-accent animate-spin" />}
          <button
            onClick={() => setOpen(false)}
            className="icon-button cursor-pointer"
            title="关闭"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="flex items-center gap-2 border-b border-border-subtle px-4 py-2 text-xs">
          {(['mixed', 'endpoint', 'refs', 'ask'] as const).map((m) => (
            <button
              key={m}
              onClick={() => setMode(m)}
              className={`cursor-pointer rounded-full border px-2.5 py-1 transition-colors ${
                mode === m ? 'bg-accent/12 border-accent/45 text-accent' : 'bg-elevated border-border-subtle text-text-secondary hover:border-accent/25 hover:text-text-primary'
              }`}
            >
              {m === 'mixed' ? '综合' : m === 'endpoint' ? '接口入口' : m === 'refs' ? '引用关系' : '问答'}
            </button>
          ))}
          <span className="ml-auto chip chip-muted">Ctrl/Cmd + K</span>
        </div>

        <div className="max-h-[62vh] overflow-auto p-3 space-y-3 scrollbar-thin">
          {effectiveMode === 'refs' && normalizedInput && (
            <button
              onClick={handleRunReferences}
              className="w-full rounded-xl border border-border-subtle bg-elevated px-3 py-2 text-left cursor-pointer hover:border-accent/50"
            >
              <div className="flex items-center gap-2">
                <GitBranch className="w-4 h-4 text-accent" />
                <span className="text-sm text-text-primary">查看函数引用关系（2 跳）：{normalizedInput}</span>
              </div>
              <div className="text-xs text-text-muted mt-1">将高亮关联节点并定位中心符号</div>
            </button>
          )}

          {effectiveMode === 'ask' && normalizedInput && (
            <button
              onClick={handleAsk}
              className="w-full rounded-xl border border-border-subtle bg-elevated px-3 py-2 text-left cursor-pointer hover:border-accent/50"
            >
              <div className="flex items-center gap-2">
                <MessageSquare className="w-4 h-4 text-accent" />
                <span className="text-sm text-text-primary">发起研究问答：{normalizedInput}</span>
              </div>
            </button>
          )}

          {canShowOpenFileAction && (
            <button
              onClick={handleOpenFile}
              className="w-full rounded-xl border border-border-subtle bg-elevated px-3 py-2 text-left cursor-pointer hover:border-accent/50"
            >
              <div className="flex items-center gap-2">
                <FileCode2 className="w-4 h-4 text-accent" />
                <span className="text-sm text-text-primary">打开代码位置：{normalizedInput}</span>
              </div>
            </button>
          )}

          {(effectiveMode === 'mixed' || effectiveMode === 'endpoint') && endpointHits.length > 0 && (
            <div className="space-y-1.5">
              <div className="section-kicker flex items-center gap-1.5">
                <Route className="w-3.5 h-3.5" />
                Gin 接口入口
              </div>
              {endpointHits.map((hit, idx) => (
                <button
                  key={`${hit.route}-${hit.handler_symbol}-${idx}`}
                  onClick={() => handlePickEndpoint(hit)}
                  className="w-full rounded-xl border border-border-subtle bg-elevated px-3 py-2 text-left cursor-pointer hover:border-accent/50"
                >
                  <div className="flex items-center gap-2">
                    <span className="chip chip-accent">
                      {hit.method}
                    </span>
                    <span className="font-mono text-sm text-text-primary truncate">{hit.route}</span>
                    <span className="ml-auto chip chip-muted">分数 {hit.score.toFixed(2)}</span>
                  </div>
                  <div className="text-xs text-text-secondary mt-1 truncate">
                    {hit.handler_symbol} · {hit.file_path}:{hit.start_line ?? 1}
                  </div>
                </button>
              ))}
            </div>
          )}

          {effectiveMode === 'mixed' && mixedNodeResults.length > 0 && (
            <div className="space-y-1.5">
              <div className="section-kicker">图谱节点</div>
              {mixedNodeResults.map((n) => (
                <button
                  key={n.id}
                  onClick={() => handlePickGraphNode(n)}
                  className="w-full rounded-xl border border-border-subtle bg-elevated px-3 py-2 text-left cursor-pointer hover:border-accent/50"
                >
                  <div className="text-sm text-text-primary truncate">{n.properties.name}</div>
                  <div className="text-xs text-text-secondary truncate">{formatNodeLabel(n.label)} · {n.properties.filePath || '-'}</div>
                </button>
              ))}
            </div>
          )}

          {effectiveMode === 'refs' && refPreview.length > 0 && (
            <div className="space-y-1.5">
              <div className="section-kicker">引用预览</div>
              {refPreview.map((n) => (
                <div key={n.id} className="px-3 py-2 rounded-lg border border-border-subtle bg-elevated">
                  <div className="text-sm text-text-primary truncate">{n.name || n.id}</div>
                  <div className="text-xs text-text-secondary truncate">{formatNodeLabel(n.label as GraphNode['label'])} · {n.file_path || '-'}</div>
                </div>
              ))}
            </div>
          )}

          {!loading && normalizedInput && endpointHits.length === 0 && mixedNodeResults.length === 0 && refPreview.length === 0 && (
            <div className="empty-state py-8">
              <div className="empty-state-title">未找到结果</div>
              <div className="empty-state-desc">可尝试“引用 符号名”或“接口 关键词”。</div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
