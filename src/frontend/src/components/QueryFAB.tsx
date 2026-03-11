import { useState, useRef, useEffect, useCallback } from 'react';
import { Terminal, X, Play, Trash2, ChevronDown } from 'lucide-react';
import { useGraphStore } from '@/stores/graphStore';

const EXAMPLE_QUERIES = [
  { label: '所有类', cypher: "MATCH (n:Class) RETURN n.name AS name, n.file_path AS file LIMIT 25" },
  { label: '函数调用链', cypher: "MATCH (a:Function)-[:CALLS]->(b:Function) RETURN a.name AS caller, b.name AS callee LIMIT 25" },
  { label: '被导入最多的文件', cypher: "MATCH (a)-[:IMPORTS]->(b:File) RETURN b.file_path AS file, count(a) AS imports ORDER BY imports DESC LIMIT 10" },
  { label: '循环依赖', cypher: "MATCH (a:File)-[:IMPORTS]->(b:File)-[:IMPORTS]->(a) RETURN a.file_path AS file_a, b.file_path AS file_b LIMIT 10" },
];

export function QueryFAB() {
  const { queryResult, runCypherQuery, setHighlightedNodeIds } = useGraphStore();
  const [isOpen, setIsOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [isRunning, setIsRunning] = useState(false);
  const [showExamples, setShowExamples] = useState(false);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);

  // Focus input when opened
  useEffect(() => {
    if (isOpen) inputRef.current?.focus();
  }, [isOpen]);

  // Close on outside click
  useEffect(() => {
    if (!isOpen) return;
    const handler = (e: MouseEvent) => {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [isOpen]);

  const handleRun = useCallback(async () => {
    if (!query.trim() || isRunning) return;
    setIsRunning(true);
    await runCypherQuery(query.trim());
    setIsRunning(false);
  }, [query, isRunning, runCypherQuery]);

  const handleClose = useCallback(() => {
    setIsOpen(false);
    setHighlightedNodeIds(new Set());
  }, [setHighlightedNodeIds]);

  const handleClear = useCallback(() => {
    setQuery('');
    setHighlightedNodeIds(new Set());
    inputRef.current?.focus();
  }, [setHighlightedNodeIds]);

  if (!isOpen) {
    return (
      <button
        onClick={() => setIsOpen(true)}
        className="absolute bottom-5 right-5 flex h-12 w-12 items-center justify-center rounded-full border border-accent/35 bg-[linear-gradient(135deg,#0ea5e9_0%,#06b6d4_55%,#f97316_130%)] text-white shadow-[0_14px_30px_rgba(14,165,233,0.34)] transition-all hover:scale-[1.06] hover:shadow-[0_18px_36px_rgba(14,165,233,0.42)] cursor-pointer z-20"
        title="图查询"
      >
        <Terminal className="w-5 h-5" />
      </button>
    );
  }

  return (
    <div ref={panelRef} className="absolute bottom-5 right-5 w-[420px] overflow-hidden rounded-2xl border border-border-default/80 bg-surface shadow-[0_26px_52px_rgba(14,116,184,0.2)] z-20 animate-slide-up">
      {/* Header */}
      <div className="panel-header">
        <div className="flex items-center gap-2">
          <Terminal className="w-4 h-4 text-accent" />
          <span className="panel-header-title">图查询</span>
        </div>
        <button onClick={handleClose} className="icon-button cursor-pointer" aria-label="关闭图查询面板">
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Query input */}
      <div className="p-3">
        <textarea
          ref={inputRef}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) { e.preventDefault(); handleRun(); } }}
          placeholder="例如：MATCH (n:Function) RETURN n.name LIMIT 10"
          rows={3}
          className="w-full px-3 py-2 bg-void border border-border-subtle rounded-lg text-sm font-mono text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent resize-none scrollbar-thin"
        />
        <div className="flex items-center gap-2 mt-2">
          <button onClick={handleRun} disabled={!query.trim() || isRunning}
            className="flex items-center gap-1.5 rounded-lg border border-accent/40 bg-accent px-3 py-1.5 text-xs font-medium text-white shadow-[0_8px_20px_rgba(14,165,233,0.26)] transition-colors hover:bg-accent-dim disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer">
            <Play className="w-3 h-3" />
            {isRunning ? '执行中...' : '执行'}
            <span className="text-xs opacity-70 ml-1">⌘↵</span>
          </button>
          <button onClick={handleClear}
            className="icon-button cursor-pointer" title="清空">
            <Trash2 className="w-3.5 h-3.5" />
          </button>
          <button onClick={() => setShowExamples(!showExamples)}
            className="ml-auto flex items-center gap-1 rounded-full border border-border-subtle bg-elevated px-2.5 py-1 text-xs text-text-secondary hover:border-accent/30 hover:text-text-primary cursor-pointer">
            示例 <ChevronDown className={`w-3 h-3 transition-transform ${showExamples ? 'rotate-180' : ''}`} />
          </button>
        </div>
      </div>

      {/* Example queries */}
      {showExamples && (
        <div className="px-3 pb-3 space-y-1">
          {EXAMPLE_QUERIES.map((ex) => (
            <button key={ex.label} onClick={() => { setQuery(ex.cypher); setShowExamples(false); inputRef.current?.focus(); }}
              className="w-full rounded-lg border border-border-subtle bg-elevated px-3 py-2 text-left text-xs text-text-secondary transition-colors hover:border-accent/35 hover:text-text-primary cursor-pointer">
              <span className="text-accent font-medium">{ex.label}</span>
              <span className="block font-mono text-xs text-text-muted mt-0.5 truncate">{ex.cypher}</span>
            </button>
          ))}
        </div>
      )}

      {/* Results */}
      {queryResult && (
        <div className="border-t border-border-subtle">
          <div className="flex items-center justify-between px-4 py-2 bg-elevated/50">
            <span className="chip chip-muted">{queryResult.count} 条结果</span>
            {queryResult.highlightedNodeIds && queryResult.highlightedNodeIds.length > 0 && (
              <span className="chip chip-accent">高亮 {queryResult.highlightedNodeIds.length} 个节点</span>
            )}
          </div>
          <div className="max-h-48 overflow-auto scrollbar-thin">
            {queryResult.results.length > 0 ? (
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-border-subtle">
                    {Object.keys(queryResult.results[0]).map((key) => (
                      <th key={key} className="px-3 py-1.5 text-left text-text-muted font-medium">{key}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {queryResult.results.slice(0, 50).map((row, i) => (
                    <tr key={i} className="border-b border-border-subtle/50 hover:bg-hover/50">
                      {Object.values(row).map((val, j) => (
                        <td key={j} className="px-3 py-1.5 text-text-secondary font-mono truncate max-w-[200px]">
                          {typeof val === 'object' ? JSON.stringify(val) : String(val ?? '')}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div className="empty-state py-6">
                <div className="empty-state-title">无结果</div>
                <div className="empty-state-desc">可以调整查询条件，或尝试“示例”中的模板语句。</div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
