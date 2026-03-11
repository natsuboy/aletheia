/**
 * 分析结果底部弹出卡片
 * 当 Impact 分析或 Entry Flow 分析结束后，从画布底部滑入展示结果摘要。
 * 不再使用常驻浮动面板，避免遮挡图谱节点。
 */
import { X, AlertTriangle, Workflow, CheckCircle2 } from 'lucide-react';
import { useGraphStore } from '@/stores/graphStore';

// 风险等级对应的颜色 chip
const riskChip: Record<string, string> = {
  critical: 'chip chip-error',
  high: 'chip chip-error',
  medium: 'chip chip-muted',
  low: 'chip chip-secondary',
};

export function AnalysisPanel() {
  const {
    currentTask,
    loading,
    impactSummary,
    pathCandidates,
    activePathRank,
    selectPathCandidate,
    reset: _reset,
    // 用于关闭：清除高亮并重置 task 相关状态
    setHighlightedNodeIds,
    setBlastRadiusNodeIds,
    runOverviewView,
  } = useGraphStore();

  // 只有在有分析结果时才显示底部卡片
  const hasImpact = !!impactSummary;
  const hasPaths = pathCandidates.length > 0;
  const showCard = hasImpact || hasPaths;

  if (!showCard && !loading) return null;

  // 关闭：清除分析结果高亮，隐藏卡片
  const handleClose = () => {
    setHighlightedNodeIds(new Set());
    setBlastRadiusNodeIds(new Set());
    // 重置回 overview task 清除 impactSummary
    useGraphStore.setState({
      impactSummary: null,
      pathCandidates: [],
      activePathRank: null,
      currentTask: 'overview',
      blastRadiusNodeIds: new Set(),
      highlightedNodeIds: new Set(),
      highlightedEdgePairs: new Set(),
    });
  };

  return (
    /* 绝对定位在画布底部中央，从底部滑入 */
    <div
      className="absolute bottom-12 left-1/2 -translate-x-1/2 z-30 pointer-events-auto animate-slide-up"
      style={{ maxWidth: '640px', width: '100%' }}
    >
      <div className="mx-4 bg-surface/98 backdrop-blur-xl border border-border-default rounded-2xl shadow-2xl overflow-hidden">
        {/* 顶部标题栏 */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-border-subtle bg-elevated/60">
          <div className="flex items-center gap-2">
            {currentTask === 'impact' && (
              <AlertTriangle className="w-4 h-4 text-accent" />
            )}
            {currentTask === 'entry_flow' && (
              <Workflow className="w-4 h-4 text-accent" />
            )}
            {currentTask === 'path' && (
              <CheckCircle2 className="w-4 h-4 text-accent" />
            )}
            <span className="text-sm font-semibold text-text-primary">
              {currentTask === 'impact' && '影响范围分析'}
              {currentTask === 'entry_flow' && '执行链路追踪'}
              {currentTask === 'path' && '路径分析'}
            </span>
          </div>
          <button
            onClick={handleClose}
            className="icon-button cursor-pointer"
            title="关闭"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* 内容区域 */}
        <div className="p-4">
          {/* 加载中 */}
          {loading && (
            <div className="flex items-center gap-3 py-2">
              <div className="h-4 w-4 border-2 border-accent border-t-transparent rounded-full animate-spin" />
              <span className="text-sm text-text-secondary">分析中，请稍候...</span>
            </div>
          )}

          {/* 影响范围结果 */}
          {!loading && hasImpact && (
            <div className="flex flex-wrap items-center gap-4">
              {/* 风险等级 */}
              <div className="flex items-center gap-2">
                <span className="text-xs text-text-muted">风险</span>
                <span className={riskChip[impactSummary!.risk] ?? 'chip chip-secondary'}>
                  {impactSummary!.risk}
                </span>
              </div>
              {/* 影响总数 */}
              <div className="flex items-center gap-2">
                <span className="text-xs text-text-muted">影响节点</span>
                <span className="text-sm font-mono font-semibold text-text-primary">
                  {impactSummary!.total_affected}
                </span>
              </div>
              {/* 直接影响 */}
              {impactSummary!.direct_affected != null && (
                <div className="flex items-center gap-2">
                  <span className="text-xs text-text-muted">直接影响</span>
                  <span className="text-sm font-mono text-text-secondary">
                    {impactSummary!.direct_affected}
                  </span>
                </div>
              )}
              <div className="ml-auto text-xs text-text-muted">
                修改此代码将波及以上节点，画布已高亮显示
              </div>
            </div>
          )}

          {/* 路径候选结果 */}
          {!loading && hasPaths && (
            <div className="space-y-2">
              <p className="text-xs text-text-muted mb-2">找到 {pathCandidates.length} 条路径，点击切换高亮：</p>
              <div className="flex flex-wrap gap-2">
                {pathCandidates.map((p) => (
                  <button
                    key={p.rank}
                    onClick={() => selectPathCandidate(p.rank)}
                    className={`px-3 py-1.5 rounded-lg border text-xs transition-colors cursor-pointer ${activePathRank === p.rank
                        ? 'bg-accent/20 border-accent/40 text-text-primary'
                        : 'bg-elevated border-border-subtle text-text-secondary hover:text-text-primary'
                      }`}
                  >
                    路径 #{p.rank} · {p.length} 跳
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
