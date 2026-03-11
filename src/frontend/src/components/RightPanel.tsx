import { useState, useRef, useEffect, useCallback } from 'react';
import { Send, Sparkles, User, PanelRightClose, Loader2, Copy, Check, StopCircle } from 'lucide-react';
import { useGraphStore } from '@/stores/graphStore';
import { useUIStore } from '@/stores/uiStore';
import { useChatStore } from '@/stores/chatStore';
import { useProjectStore } from '@/stores/projectStore';
import { MarkdownRenderer } from './MarkdownRenderer';
import { ResearchToggle } from './chat/ResearchToggle';
import { ResearchProgress } from './chat/ResearchProgress';
import { SessionDropdown } from './chat/SessionDropdown';

const CHAT_PANEL_WIDTH_KEY = 'aletheia:chatPanelWidth';

export function RightPanel() {
  const { knowledgeGraph } = useGraphStore();
  const { toggleRightPanel, addCodeReference } = useUIStore();
  const { currentProject } = useProjectStore();
  const { messages, loading: isLoading, error, sendMessage, clearChat, stopStreaming } = useChatStore();

  const [chatInput, setChatInput] = useState('');
  const [panelWidth, setPanelWidth] = useState(() => {
    const saved = localStorage.getItem(CHAT_PANEL_WIDTH_KEY);
    const parsed = saved ? Number(saved) : NaN;
    return Number.isFinite(parsed) ? parsed : 420;
  });
  const [copiedMsgId, setCopiedMsgId] = useState<string | null>(null);
  const [expandedEvidence, setExpandedEvidence] = useState<Set<string>>(new Set());
  const [messageViewMode, setMessageViewMode] = useState<Record<string, 'answer' | 'audit'>>({});
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const resizeRef = useRef<{ startX: number; startWidth: number } | null>(null);
  const shouldAutoScrollRef = useRef(true);
  const panelWidthRef = useRef(panelWidth);

  const isNearBottom = useCallback(() => {
    const el = messagesContainerRef.current;
    if (!el) return true;
    return el.scrollHeight - el.scrollTop - el.clientHeight < 64;
  }, []);

  useEffect(() => {
    panelWidthRef.current = panelWidth;
  }, [panelWidth]);

  useEffect(() => {
    const clampToViewport = () => {
      const viewportMax = Math.max(320, Math.min(680, window.innerWidth - 24));
      const viewportMin = Math.min(420, viewportMax);
      const next = Math.max(viewportMin, Math.min(panelWidthRef.current, viewportMax));
      if (next !== panelWidthRef.current) setPanelWidth(next);
    };
    clampToViewport();
    window.addEventListener('resize', clampToViewport);
    return () => window.removeEventListener('resize', clampToViewport);
  }, []);

  // Resize handle (left side — drag left to increase width)
  const startResize = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    resizeRef.current = { startX: e.clientX, startWidth: panelWidth };
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
    const onMove = (ev: MouseEvent) => {
      if (!resizeRef.current) return;
      const viewportMax = Math.max(320, Math.min(680, window.innerWidth - 24));
      const viewportMin = Math.min(420, viewportMax);
      const next = Math.max(viewportMin, Math.min(resizeRef.current.startWidth - (ev.clientX - resizeRef.current.startX), viewportMax));
      setPanelWidth(next);
    };
    const onUp = () => {
      resizeRef.current = null;
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
      localStorage.setItem(CHAT_PANEL_WIDTH_KEY, String(panelWidthRef.current));
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
    };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
  }, [panelWidth]);

  // Auto-scroll only when user stays near bottom
  useEffect(() => {
    const container = messagesContainerRef.current;
    if (!container) return;
    const onScroll = () => {
      shouldAutoScrollRef.current = isNearBottom();
    };
    container.addEventListener('scroll', onScroll);
    return () => container.removeEventListener('scroll', onScroll);
  }, [isNearBottom]);

  useEffect(() => {
    if (!shouldAutoScrollRef.current) return;
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [messages, isLoading]);

  // Resolve file path from grounding links
  const resolveFilePathForUI = useCallback((requestedPath: string): string | null => {
    if (!knowledgeGraph) return null;
    const req = requestedPath.replace(/\\/g, '/').replace(/^\.?\//, '').toLowerCase();
    if (!req) return null;

    const fileNodes = knowledgeGraph.nodes.filter(n => n.label === 'File');
    // Exact match
    for (const n of fileNodes) {
      const norm = n.properties.filePath.replace(/\\/g, '/').replace(/^\.?\//, '').toLowerCase();
      if (norm === req) return n.properties.filePath;
    }
    // Ends-with match
    let best: { path: string; score: number } | null = null;
    for (const n of fileNodes) {
      const norm = n.properties.filePath.replace(/\\/g, '/').replace(/^\.?\//, '').toLowerCase();
      if (norm.endsWith(req)) {
        const score = 1000 - norm.length;
        if (!best || score > best.score) best = { path: n.properties.filePath, score };
      }
    }
    return best?.path ?? null;
  }, [knowledgeGraph]);

  const findFileNodeId = useCallback((filePath: string): string | undefined => {
    if (!knowledgeGraph) return undefined;
    const target = filePath.replace(/\\/g, '/').replace(/^\.?\//, '');
    return knowledgeGraph.nodes.find(
      n => n.label === 'File' && n.properties.filePath.replace(/\\/g, '/').replace(/^\.?\//, '') === target
    )?.id;
  }, [knowledgeGraph]);

  const openCodeReferenceByPath = useCallback((rawPath: string, startLine1?: number, endLine1?: number) => {
    const resolvedPath = resolveFilePathForUI(rawPath);
    if (!resolvedPath) return;
    const nodeId = findFileNodeId(resolvedPath);
    addCodeReference({
      id: `ai-ref-${Date.now()}`,
      filePath: resolvedPath,
      startLine: startLine1 ? Math.max(0, startLine1 - 1) : undefined,
      endLine: endLine1 ? Math.max(0, endLine1 - 1) : undefined,
      nodeId,
      label: '文件',
      name: resolvedPath.split('/').pop() ?? resolvedPath,
      source: 'ai',
    });
  }, [addCodeReference, findFileNodeId, resolveFilePathForUI]);

  // Handle grounding link clicks from markdown
  const handleGroundingClick = useCallback((inner: string) => {
    const raw = inner.trim();
    if (!raw) return;
    let rawPath = raw;
    let startLine1: number | undefined;
    let endLine1: number | undefined;
    const lineMatch = raw.match(/^(.*):(\d+)(?:[-–](\d+))?$/);
    if (lineMatch) {
      rawPath = lineMatch[1].trim();
      startLine1 = parseInt(lineMatch[2], 10);
      endLine1 = parseInt(lineMatch[3] || lineMatch[2], 10);
    }
    openCodeReferenceByPath(rawPath, startLine1, endLine1);
  }, [openCodeReferenceByPath]);

  const handleNodeGroundingClick = useCallback((raw: string) => {
    if (!raw.trim() || !knowledgeGraph) return;
    const match = raw.trim().match(/^(Class|Function|Method|Interface|File|Folder|Variable|Enum|Type|CodeElement):(.+)$/);
    if (!match) return;
    const [, nodeType, nodeName] = match;
    const node = knowledgeGraph.nodes.find(n => n.label === nodeType && n.properties.name === nodeName.trim());
    if (!node?.properties.filePath) return;
    const resolvedPath = resolveFilePathForUI(node.properties.filePath);
    if (!resolvedPath) return;
    addCodeReference({
      id: `ai-node-${Date.now()}`, filePath: resolvedPath,
      startLine: node.properties.startLine ? node.properties.startLine - 1 : undefined,
      endLine: node.properties.endLine ? node.properties.endLine - 1 : undefined,
      nodeId: node.id, label: node.label, name: node.properties.name, source: 'ai',
    });
  }, [knowledgeGraph, resolveFilePathForUI, addCodeReference]);

  const handleLinkClick = useCallback((href: string) => {
    if (href.startsWith('code-ref:')) handleGroundingClick(decodeURIComponent(href.slice('code-ref:'.length)));
    else if (href.startsWith('node-ref:')) handleNodeGroundingClick(decodeURIComponent(href.slice('node-ref:'.length)));
  }, [handleGroundingClick, handleNodeGroundingClick]);

  const adjustTextareaHeight = useCallback(() => {
    const ta = textareaRef.current;
    if (!ta) return;
    ta.style.height = 'auto';
    const h = Math.min(ta.scrollHeight, 160);
    ta.style.height = `${h}px`;
    ta.style.overflowY = ta.scrollHeight > 160 ? 'auto' : 'hidden';
  }, []);

  useEffect(() => { adjustTextareaHeight(); }, [chatInput, adjustTextareaHeight]);

  const handleSendMessage = async () => {
    if (!chatInput.trim() || !currentProject) return;
    const text = chatInput.trim();
    setChatInput('');
    if (textareaRef.current) { textareaRef.current.style.height = '36px'; textareaRef.current.style.overflowY = 'hidden'; }
    await sendMessage(text, currentProject.name);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSendMessage(); }
  };

  const suggestions = [
    '解释这个项目的整体架构',
    '这个项目的核心职责是什么？',
    '列出最关键的代码文件',
    '找出所有 API 处理入口',
  ];

  const isAuditMode = (msgId: string) => messageViewMode[msgId] === 'audit';

  return (
    <aside
      className="flex flex-col animate-slide-in relative z-30 flex-shrink-0 glass-panel rounded-2xl overflow-hidden shadow-2xl"
      style={{ width: panelWidth }}
    >
      {/* Resize handle (left side) */}
      <div
        onMouseDown={startResize}
        role="separator"
        aria-orientation="vertical"
        aria-label="调整对话面板宽度"
        className="absolute top-0 left-0 h-full w-2 cursor-col-resize bg-transparent hover:bg-accent/25 transition-colors z-10"
        title="拖拽调整面板宽度"
      />
      {/* Header */}
      <div className="panel-header">
        <div className="flex items-center gap-2">
          <span className="w-6 h-6 rounded-md bg-gradient-to-br from-accent to-accent-secondary text-white inline-flex items-center justify-center shadow-[0_8px_18px_rgba(14,165,233,0.3)]">
            <Sparkles className="w-3.5 h-3.5" />
          </span>
          <span className="panel-header-title">智能问答</span>
          <SessionDropdown />
        </div>
        <div className="flex items-center gap-1.5">
          <ResearchToggle />
          <button onClick={toggleRightPanel} className="icon-button transition-colors cursor-pointer" title="关闭面板">
            <PanelRightClose className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Research progress bar */}
      <ResearchProgress />

      {/* Error banner */}
      {error && (
        <div className="px-4 py-2 bg-error/10 border-b border-error/30 text-error text-sm">{error}</div>
      )}

      {/* Messages */}
      <div ref={messagesContainerRef} className="flex-1 overflow-y-auto p-4 scrollbar-thin">
        {messages.length === 0 ? (
          <div className="empty-state h-full px-4">
            <div className="empty-state-icon">
              <Sparkles className="w-5 h-5" />
            </div>
            <h3 className="empty-state-title">开始提问</h3>
            <p className="empty-state-desc mb-2">
              我可以帮你理解架构、定位函数实现或解释模块关系。
            </p>
            <div className="flex flex-wrap gap-2 justify-center">
              {suggestions.map(s => (
                <button key={s} onClick={() => setChatInput(s)}
                  className="px-3 py-1.5 bg-elevated border border-border-subtle rounded-full text-sm text-text-secondary hover:border-accent hover:text-text-primary transition-colors cursor-pointer">
                  {s}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="flex flex-col gap-6">
            {messages.map(msg => (
              <div key={msg.id} className="animate-fade-in">
                {msg.role === 'user' && (
                  <div className="mb-4 rounded-2xl border border-border-subtle bg-surface/85 px-3 py-3 shadow-[0_8px_20px_rgba(15,23,42,0.04)]">
                    <div className="flex items-center gap-2 mb-2 pl-1">
                      <User className="w-4 h-4 text-text-muted" />
                      <span className="section-kicker">你</span>
                    </div>
                    <div className="pl-6 text-sm text-text-primary leading-relaxed">{msg.content}</div>
                  </div>
                )}
                {msg.role === 'assistant' && (
                  <div className="rounded-2xl border border-border-subtle bg-gradient-to-b from-surface/90 to-elevated/65 px-3 py-3 shadow-[0_10px_24px_rgba(14,116,184,0.07)]">
                    <div className="flex items-center gap-2 mb-3 pl-1">
                      <Sparkles className="w-4 h-4 text-accent" />
                      <span className="section-kicker">Aletheia 助手</span>
                      {typeof msg.qualityScore === 'number' && (
                        <span className="chip chip-accent">
                          Q {msg.qualityScore.toFixed(2)}
                        </span>
                      )}
                      {isLoading && msg === messages[messages.length - 1] && (
                        <Loader2 className="w-3 h-3 animate-spin text-accent" />
                      )}
                      <div className="ml-auto flex items-center gap-1">
                        <div className="flex items-center gap-1 rounded-xl border border-border-subtle bg-surface/80 p-0.5">
                          <button
                            onClick={() => setMessageViewMode((prev) => ({ ...prev, [msg.id]: 'answer' }))}
                            className={`px-2 py-0.5 text-xs rounded cursor-pointer ${!isAuditMode(msg.id) ? 'bg-accent/20 text-text-primary' : 'text-text-muted hover:text-text-primary'
                              }`}
                          >
                            回答
                          </button>
                          <button
                            onClick={() => setMessageViewMode((prev) => ({ ...prev, [msg.id]: 'audit' }))}
                            className={`px-2 py-0.5 text-xs rounded cursor-pointer ${isAuditMode(msg.id) ? 'bg-accent/20 text-text-primary' : 'text-text-muted hover:text-text-primary'
                              }`}
                          >
                            审计
                          </button>
                        </div>
                        <button
                          onClick={() => {
                            navigator.clipboard.writeText(msg.content).then(() => {
                              setCopiedMsgId(msg.id);
                              setTimeout(() => setCopiedMsgId(prev => prev === msg.id ? null : prev), 1500);
                            }).catch(() => { });
                          }}
                          className="icon-button transition-colors cursor-pointer"
                          title="复制回答"
                        >
                          {copiedMsgId === msg.id ? <Check className="w-3.5 h-3.5 text-accent-secondary" /> : <Copy className="w-3.5 h-3.5" />}
                        </button>
                      </div>
                    </div>
                    {!isAuditMode(msg.id) && (
                      <div className="pl-6 chat-prose">
                        {msg.steps && msg.steps.length > 0 ? (
                          <div className="space-y-4">
                            {msg.steps.map(step => (
                              <div key={step.id}>
                                {step.type === 'reasoning' && step.content && (
                                  <div className="text-text-secondary text-sm italic border-l-2 border-text-muted/30 pl-3 mb-3">
                                    <MarkdownRenderer content={step.content} onLinkClick={handleLinkClick} />
                                  </div>
                                )}
                                {step.type === 'content' && step.content && (
                                  <MarkdownRenderer content={step.content} onLinkClick={handleLinkClick} />
                                )}
                              </div>
                            ))}
                          </div>
                        ) : (
                          <MarkdownRenderer content={msg.content} onLinkClick={handleLinkClick} />
                        )}
                      </div>
                    )}

                    {isAuditMode(msg.id) && (
                      <div className="pl-6 mt-1 space-y-2">
                        <div className="rounded-lg border border-border-subtle bg-elevated/70 px-2.5 py-2 text-xs text-text-muted">
                          审计视图：检查来源、证据、质量分与追踪ID。
                        </div>
                      </div>
                    )}

                    {isAuditMode(msg.id) && msg.evidence && msg.evidence.length > 0 && (
                      <div className="pl-6 mt-2 space-y-2">
                        <div className="flex items-center gap-2">
                          <div className="section-kicker">证据</div>
                          <button
                            onClick={() => {
                              setExpandedEvidence((prev) => {
                                const next = new Set(prev);
                                if (next.has(msg.id)) next.delete(msg.id);
                                else next.add(msg.id);
                                return next;
                              });
                            }}
                            className="chip chip-muted cursor-pointer hover:border-accent/25"
                          >
                            {expandedEvidence.has(msg.id) ? '收起' : '展开'}
                          </button>
                        </div>
                        {(expandedEvidence.has(msg.id) ? msg.evidence : msg.evidence.slice(0, 2)).map((ev) => (
                          <div key={ev.id} className="rounded-lg border border-border-subtle bg-elevated/65 px-2.5 py-2">
                            <div className="flex items-center gap-2 mb-1">
                              <span className="chip chip-muted">
                                {ev.sourceType}
                              </span>
                              <span className="text-xs text-text-muted">分数 {ev.score.toFixed(2)}</span>
                              {ev.filePath && (
                                <button
                                  onClick={() => openCodeReferenceByPath(ev.filePath || '')}
                                  className="text-xs text-accent hover:text-accent-dim truncate cursor-pointer"
                                  title="跳转到代码引用"
                                >
                                  {ev.filePath}
                                </button>
                              )}
                            </div>
                            <div className="text-xs text-text-secondary line-clamp-3">{ev.content}</div>
                          </div>
                        ))}
                      </div>
                    )}
                    {isAuditMode(msg.id) && msg.sources && msg.sources.length > 0 && (
                      <div className="pl-6 mt-2 space-y-1">
                        <div className="section-kicker">来源</div>
                        {msg.sources.slice(0, 3).map((src, idx) => (
                          <div key={`${msg.id}-src-${idx}`} className="text-xs text-text-secondary rounded-lg border border-border-subtle bg-elevated/70 px-2 py-1.5">
                            <div className="flex items-center gap-2">
                              <button
                                onClick={() => openCodeReferenceByPath(src.source)}
                                className="text-accent hover:text-accent-dim font-mono truncate cursor-pointer"
                                title="跳转到代码引用"
                              >
                                {src.source}
                              </button>
                              <span className="ml-auto text-text-muted">分数 {src.score.toFixed(2)}</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                    {isAuditMode(msg.id) && (typeof msg.qualityScore === 'number' || msg.retrievalTraceId || (msg.evidence?.length ?? 0) > 0) && (
                      <div className="pl-6 mt-2 flex items-center flex-wrap gap-1.5 text-xs">
                        {(msg.evidence?.length ?? 0) > 0 && (
                          <span className="chip chip-muted">
                            证据 {(msg.evidence?.length ?? 0)}
                          </span>
                        )}
                        {typeof msg.qualityScore === 'number' && (
                          <span className="chip chip-accent">
                            质量 {msg.qualityScore.toFixed(2)}
                          </span>
                        )}
                        {msg.retrievalTraceId && (
                          <span className="chip chip-muted font-mono">
                            追踪 {msg.retrievalTraceId.slice(0, 12)}
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="p-3 border-t border-border-subtle bg-gradient-to-r from-surface/75 to-elevated/65">
        <div className="flex items-end gap-2 px-3 py-2 bg-surface/85 border border-border-subtle rounded-2xl transition-all focus-within:border-accent focus-within:ring-2 focus-within:ring-accent/20 shadow-[0_8px_20px_rgba(15,23,42,0.04)]">
          <textarea ref={textareaRef} value={chatInput} onChange={e => setChatInput(e.target.value)} onKeyDown={handleKeyDown}
            placeholder="输入问题，例如：这个模块的调用链是什么？" rows={1}
            className="flex-1 bg-transparent border-none outline-none text-sm text-text-primary placeholder:text-text-muted resize-none min-h-[36px] scrollbar-thin"
            style={{ height: '36px', overflowY: 'hidden' }} />
          <button onClick={() => clearChat()} className="px-2 py-1 text-sm text-text-muted hover:text-text-primary transition-colors cursor-pointer" title="清空会话">清空</button>
          {isLoading && (
            <button
              onClick={() => stopStreaming()}
              className="px-2 py-1 text-sm text-error hover:text-error-dim transition-colors cursor-pointer flex items-center gap-1"
              title="停止生成"
            >
              <StopCircle className="w-3.5 h-3.5" />
              停止
            </button>
          )}
          <button onClick={handleSendMessage} disabled={!chatInput.trim() || isLoading}
            className="w-9 h-9 flex items-center justify-center bg-gradient-to-r from-accent to-accent-secondary rounded-xl text-white transition-all hover:brightness-105 hover:-translate-y-[1px] disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer shadow-[0_8px_18px_rgba(14,165,233,0.3)]">
            {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
          </button>
        </div>
      </div>
    </aside>
  );
}
