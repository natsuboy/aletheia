import { Search, Sparkles, Route, GitBranch } from 'lucide-react';
import { useState, useMemo, useRef, useEffect } from 'react';
import { useProjectStore } from '@/stores/projectStore';
import { useGraphStore } from '@/stores/graphStore';
import { useUIStore } from '@/stores/uiStore';
import { NODE_COLORS } from '@/lib/constants';
import { formatNodeLabel } from '@/lib/nodeLabel';
import type { GraphNode, NodeLabel } from '@/types/graph';

interface HeaderProps {
  onFocusNode?: (nodeId: string) => void;
}

export function Header({ onFocusNode }: HeaderProps) {
  const { currentProject } = useProjectStore();
  const { knowledgeGraph, selectNode } = useGraphStore();
  const { isRightPanelOpen, rightPanelTab, setRightPanelTab, setCodePanelOpen, viewMode } = useUIStore();

  const [searchQuery, setSearchQuery] = useState('');
  const [isSearchOpen, setIsSearchOpen] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const searchRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const nodeCount = knowledgeGraph?.nodeCount ?? 0;
  const edgeCount = knowledgeGraph?.relationshipCount ?? 0;

  const searchResults = useMemo(() => {
    if (!knowledgeGraph || !searchQuery.trim()) return [];
    const q = searchQuery.toLowerCase();
    return knowledgeGraph.nodes
      .filter((n) => n.properties.name.toLowerCase().includes(q))
      .slice(0, 10);
  }, [knowledgeGraph, searchQuery]);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (searchRef.current && !searchRef.current.contains(e.target as Node)) {
        setIsSearchOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        inputRef.current?.focus();
        setIsSearchOpen(true);
      }
      if (e.key === 'Escape') {
        setIsSearchOpen(false);
        inputRef.current?.blur();
      }
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, []);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!isSearchOpen || searchResults.length === 0) return;
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIndex((i) => Math.min(i + 1, searchResults.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIndex((i) => Math.max(i - 1, 0));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      const selected = searchResults[selectedIndex];
      if (selected) handleSelectNode(selected);
    }
  };

  const handleSelectNode = (node: GraphNode) => {
    selectNode(node);
    setCodePanelOpen(true);
    onFocusNode?.(node.id);
    setSearchQuery('');
    setIsSearchOpen(false);
    setSelectedIndex(0);
  };

  const openChatPanel = () => setRightPanelTab('chat');
  const openCommand = (mode: 'endpoint' | 'refs') => {
    window.dispatchEvent(new CustomEvent('aletheia:open-command', { detail: { mode } }));
  };

  return (
    <header className="flex items-center justify-between gap-3 px-3 md:px-5 py-3 panel-surface rounded-none border-x-0 border-t-0">
      {/* Left */}
      <div className="flex items-center gap-2 md:gap-4 min-w-0">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 flex items-center justify-center bg-elevated border border-border-subtle rounded-md text-text-secondary text-xs font-semibold">
            AE
          </div>
          <span className="font-semibold text-[15px] tracking-tight">Aletheia</span>
        </div>
        {currentProject && (
          <div className="hidden md:flex items-center gap-2 px-3 py-1.5 bg-surface/85 border border-border-subtle rounded-xl text-sm text-text-secondary shadow-[0_6px_14px_rgba(15,23,42,0.04)]">
            <span className="w-1.5 h-1.5 bg-node-function rounded-full animate-pulse" />
            <span className="truncate max-w-[200px]">{currentProject.name}</span>
          </div>
        )}
        {currentProject && (
          <div className="hidden lg:block px-2 py-1 rounded-xl border border-border-subtle bg-elevated/80 text-xs text-text-muted">
            {viewMode === 'wiki' ? '文档模式' : '图谱模式'}
          </div>
        )}
      </div>

      {/* Center - Search */}
      <div className="hidden md:block flex-1 max-w-md mx-2 lg:mx-6 relative" ref={searchRef}>
        <div className="flex items-center gap-2.5 px-3.5 py-2 bg-surface border border-border-subtle rounded-lg transition-all focus-within:border-accent focus-within:ring-2 focus-within:ring-accent/20">
          <Search className="w-4 h-4 text-text-muted flex-shrink-0" />
          <input
            ref={inputRef}
            type="text"
            placeholder="搜索符号或文件..."
            value={searchQuery}
            onChange={(e) => { setSearchQuery(e.target.value); setIsSearchOpen(true); setSelectedIndex(0); }}
            onFocus={() => setIsSearchOpen(true)}
            onKeyDown={handleKeyDown}
            className="flex-1 bg-transparent border-none outline-none text-sm text-text-primary placeholder:text-text-muted"
          />
          <kbd className="px-1.5 py-0.5 bg-elevated border border-border-subtle rounded text-xs text-text-muted font-mono">⌘K</kbd>
        </div>

        {isSearchOpen && searchQuery.trim() && (
          <div className="absolute top-full left-0 right-0 mt-1 bg-surface border border-border-subtle rounded-lg shadow-xl overflow-hidden z-50">
            {searchResults.length === 0 ? (
              <div className="empty-state py-6">
                <div className="empty-state-title text-sm">未找到匹配节点</div>
                <div className="empty-state-desc">请尝试更短的关键词，或使用函数/文件名进行搜索。</div>
              </div>
            ) : (
              <div className="max-h-80 overflow-y-auto">
                {searchResults.map((node, index) => (
                  <button
                    key={node.id}
                    onClick={() => handleSelectNode(node)}
                    className={`w-full px-4 py-2.5 flex items-center gap-3 text-left transition-colors ${
                      index === selectedIndex ? 'bg-accent/20 text-text-primary' : 'hover:bg-hover text-text-secondary'
                    }`}
                  >
                    <span className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ backgroundColor: NODE_COLORS[node.label as NodeLabel] || '#6b7280' }} />
                    <div className="flex-1 min-w-0">
                      <span className="truncate text-sm font-medium block">{node.properties.name}</span>
                      {node.properties.filePath && (
                        <span className="truncate text-xs text-text-muted block">{node.properties.filePath}</span>
                      )}
                    </div>
                    <span className="text-xs text-text-muted px-2 py-0.5 bg-elevated rounded flex-shrink-0">{formatNodeLabel(node.label)}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Right */}
      <div className="flex items-center gap-1.5 md:gap-2 shrink-0">
        <button
          onClick={() => openCommand('endpoint')}
          className="hidden md:flex items-center gap-1.5 px-2.5 py-1.5 rounded-xl border border-border-subtle bg-elevated/80 text-xs text-text-secondary hover:text-text-primary hover:border-accent/50 cursor-pointer"
          title="定位 Gin 接口实现入口"
        >
          <Route className="w-3.5 h-3.5" />
          接口入口
        </button>
        <button
          onClick={() => openCommand('refs')}
          className="hidden md:flex items-center gap-1.5 px-2.5 py-1.5 rounded-xl border border-border-subtle bg-elevated/80 text-xs text-text-secondary hover:text-text-primary hover:border-accent/50 cursor-pointer"
          title="查看函数引用关系"
        >
          <GitBranch className="w-3.5 h-3.5" />
          引用关系
        </button>
        {knowledgeGraph && (
          <div className="hidden xl:flex items-center gap-4 mr-2 text-xs text-text-muted">
            <span>{nodeCount} 节点</span>
            <span>{edgeCount} 边</span>
          </div>
        )}
        <button
          onClick={openChatPanel}
          className={`flex items-center gap-1.5 px-2.5 md:px-3.5 py-2 rounded-lg text-xs md:text-sm font-medium transition-all ${
            isRightPanelOpen && rightPanelTab === 'chat'
              ? 'bg-accent text-white shadow-glow'
              : 'bg-gradient-to-r from-accent to-accent-dim text-white shadow-glow hover:shadow-lg'
          }`}
        >
          <Sparkles className="w-4 h-4" />
          <span className="hidden sm:inline">智能问答</span>
        </button>
      </div>
    </header>
  );
}
