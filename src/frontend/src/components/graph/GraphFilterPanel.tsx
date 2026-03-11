import { useState, useEffect } from 'react';
import { Filter, ChevronDown } from 'lucide-react';
import { useGraphStore } from '@/stores/graphStore';
import { NODE_COLORS, FILTERABLE_LABELS, ALL_EDGE_TYPES, EDGE_INFO } from '@/lib/constants';
import { formatNodeLabel } from '@/lib/nodeLabel';
import type { NodeLabel } from '@/types/graph';

export function GraphFilterPanel() {
  const [open, setOpen] = useState(false);

  const {
    visibleLabels,
    visibleEdgeTypes,
    depthFilter,
    selectedNode,
    toggleLabelVisibility,
    toggleEdgeVisibility,
    setDepthFilter,
    setAllLabelsVisible,
    setAllEdgesVisible,
  } = useGraphStore();

  const allLabelsOn = FILTERABLE_LABELS.every(l => visibleLabels.includes(l));
  const allEdgesOn = ALL_EDGE_TYPES.every(e => visibleEdgeTypes.includes(e));

  // Reset depth filter when node is deselected
  useEffect(() => {
    if (!selectedNode) setDepthFilter(null);
  }, [selectedNode]);

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(o => !o)}
        className={`flex items-center gap-1.5 rounded-full border px-2.5 py-1.5 text-xs font-medium transition-colors cursor-pointer ${
          open
            ? 'bg-accent/12 border-accent/45 text-accent'
            : 'bg-elevated border-border-subtle text-text-secondary hover:border-accent/25 hover:text-text-primary'
        }`}
        title="过滤图谱"
      >
        <Filter className="w-3.5 h-3.5" />
        <span>过滤</span>
        <ChevronDown className={`w-3 h-3 transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>

      {open && (
        <div className="absolute top-full left-0 z-30 mt-1.5 w-56 overflow-hidden rounded-xl border border-border-default/80 bg-surface shadow-[0_20px_38px_rgba(14,116,184,0.18)] animate-fade-in">
          {/* Node types */}
          <div className="px-3 pt-2.5 pb-1">
            <div className="flex items-center justify-between mb-1.5">
              <span className="section-kicker">节点类型</span>
              <button
                onClick={() => setAllLabelsVisible(!allLabelsOn)}
                className="chip chip-muted cursor-pointer hover:border-accent/25"
              >
                {allLabelsOn ? '全部隐藏' : '全部显示'}
              </button>
            </div>
            <div className="space-y-0.5">
              {FILTERABLE_LABELS.map(label => {
                const active = visibleLabels.includes(label);
                const color = NODE_COLORS[label as NodeLabel] || '#6b7280';
                return (
                  <button
                    key={label}
                    onClick={() => toggleLabelVisibility(label)}
                    className={`w-full flex items-center gap-2 px-2 py-1 rounded-lg text-xs transition-colors cursor-pointer ${
                      active ? 'bg-hover text-text-primary border border-accent/20' : 'text-text-muted border border-transparent hover:bg-hover/60'
                    }`}
                  >
                    <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ backgroundColor: color }} />
                    <span>{formatNodeLabel(label)}</span>
                    <span className={`ml-auto w-3 h-3 rounded border flex-shrink-0 flex items-center justify-center ${active ? 'border-accent bg-accent/20' : 'border-border-subtle'}`}>
                      {active && <span className="w-1.5 h-1.5 rounded-sm bg-accent" />}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>

          <div className="h-px bg-border-subtle mx-3 my-1" />

          {/* Edge types */}
          <div className="px-3 pb-1">
            <div className="flex items-center justify-between mb-1.5">
              <span className="section-kicker">关系类型</span>
              <button
                onClick={() => setAllEdgesVisible(!allEdgesOn)}
                className="chip chip-muted cursor-pointer hover:border-accent/25"
              >
                {allEdgesOn ? '全部隐藏' : '全部显示'}
              </button>
            </div>
            <div className="space-y-0.5">
              {ALL_EDGE_TYPES.map(edgeType => {
                const active = visibleEdgeTypes.includes(edgeType);
                const info = EDGE_INFO[edgeType];
                return (
                  <button
                    key={edgeType}
                    onClick={() => toggleEdgeVisibility(edgeType)}
                    className={`w-full flex items-center gap-2 px-2 py-1 rounded-lg text-xs transition-colors cursor-pointer ${
                      active ? 'bg-hover text-text-primary border border-accent/20' : 'text-text-muted border border-transparent hover:bg-hover/60'
                    }`}
                  >
                    <span className="w-3 h-0.5 rounded flex-shrink-0" style={{ backgroundColor: info.color }} />
                    <span>{info.label}</span>
                    <span className={`ml-auto w-3 h-3 rounded border flex-shrink-0 flex items-center justify-center ${active ? 'border-accent bg-accent/20' : 'border-border-subtle'}`}>
                      {active && <span className="w-1.5 h-1.5 rounded-sm bg-accent" />}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Depth filter */}
          {selectedNode && (
            <>
              <div className="h-px bg-border-subtle mx-3 my-1" />
              <div className="px-3 pb-2.5">
                <span className="section-kicker block mb-1.5">选中节点深度</span>
                <select
                  value={depthFilter ?? ''}
                  onChange={e => setDepthFilter(e.target.value ? Number(e.target.value) : null)}
                  className="w-full bg-surface border border-border-subtle rounded-md px-2 py-1 text-xs text-text-primary cursor-pointer focus:outline-none focus:border-accent"
                >
                  <option value="">全部跳数</option>
                  {[1, 2, 3, 4, 5].map(n => (
                    <option key={n} value={n}>{n} 跳</option>
                  ))}
                </select>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
