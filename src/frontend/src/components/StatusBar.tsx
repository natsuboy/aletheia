import { useMemo } from 'react';
import { useGraphStore } from '@/stores/graphStore';
import { useIngestionStore } from '@/stores/ingestionStore';
import { useParams } from 'react-router-dom';

export function StatusBar() {
  const {
    knowledgeGraph,
    loadedCount,
    totalCount,
    hasMore,
    loadingMore,
    fetchMoreNodes,
    coverage,
    taskMetadata,
    snapshotVersion,
    currentTask,
    stats,
    analysisStatus,
  } = useGraphStore();
  const { overallProgress, currentStage, status, traceId, retryCount, failureClass } = useIngestionStore();
  const { projectId } = useParams<{ projectId: string }>();

  const progress = (status === 'processing' || status === 'uploading') && currentStage
    ? { stage: currentStage, percent: overallProgress, message: currentStage }
    : null;

  const edgeCount = knowledgeGraph?.relationships.length ?? 0;

  const primaryLanguage = useMemo(() => {
    if (!knowledgeGraph) return null;
    const languages = knowledgeGraph.nodes
      .map(n => n.properties.language)
      .filter(Boolean);
    if (languages.length === 0) return null;
    const counts = languages.reduce((acc, lang) => {
      acc[lang!] = (acc[lang!] || 0) + 1;
      return acc;
    }, {} as Record<string, number>);
    return Object.entries(counts).sort((a, b) => b[1] - a[1])[0]?.[0];
  }, [knowledgeGraph]);

  const freshness = taskMetadata?.freshness || stats?.metadata?.freshness || analysisStatus?.metadata?.freshness;
  const snapshotUpdatedAt = taskMetadata?.snapshot_updated_at || stats?.metadata?.snapshot_updated_at || analysisStatus?.metadata?.snapshot_updated_at;
  const freshnessSource = taskMetadata?.source || stats?.metadata?.source || analysisStatus?.metadata?.source;

  const freshnessLabel = freshness === 'fresh'
    ? '最新'
    : freshness === 'rebuilding'
      ? '重建中'
      : freshness === 'stale'
        ? '过期'
        : freshness;

  return (
    <footer className="flex items-center justify-between px-4 py-2 bg-surface border-t border-border-subtle text-xs text-text-muted">
      <div className="flex items-center gap-3">
        {progress && progress.stage !== 'complete' ? (
          <>
            <div className="w-28 h-1 bg-elevated rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-accent to-node-interface rounded-full transition-all duration-300"
                style={{ width: `${progress.percent}%` }}
              />
            </div>
            <span>处理中：{progress.message}</span>
          </>
        ) : (
          <div className="flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 bg-node-function rounded-full" />
            <span>就绪</span>
          </div>
        )}
      </div>
      <div className="flex items-center gap-2.5">
        {knowledgeGraph && (
          <>
            <div className="flex items-center gap-1.5">
              <span>{totalCount > 0 ? `${loadedCount} / ${totalCount}` : loadedCount} 节点</span>
              {hasMore && projectId && (
                <button
                  onClick={() => fetchMoreNodes(projectId)}
                  disabled={loadingMore}
                  className="flex items-center justify-center w-3.5 h-3.5 rounded-sm bg-elevated border border-border-subtle hover:bg-hover hover:text-text-primary transition-colors disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
                  title="加载更多节点"
                >
                  {loadingMore
                    ? <span className="w-2 h-2 border border-current border-t-transparent rounded-full animate-spin block" />
                    : <span className="leading-none">+</span>
                  }
                </button>
              )}
            </div>
            <span className="text-border-default">·</span>
            <span>{edgeCount} 边</span>
            {coverage && (
              <>
                <span className="text-border-default">·</span>
                <span>覆盖率 {Math.round(coverage.node_coverage * 100)}% / {Math.round(coverage.edge_coverage * 100)}%</span>
                {coverage.truncated && <span className="text-text-secondary">已截断</span>}
              </>
            )}
            <span className="text-border-default">·</span>
            <span>{currentTask}</span>
            {taskMetadata?.cache_hit && (
              <>
                <span className="text-border-default">·</span>
                <span className="text-accent">缓存</span>
              </>
            )}
            {taskMetadata?.partial && (
              <>
                <span className="text-border-default">·</span>
                <span className="text-text-secondary">部分结果</span>
              </>
            )}
            {freshness && (
              <>
                <span className="text-border-default">·</span>
                <span className={freshness === 'stale' ? 'text-error' : 'text-text-secondary'}>
                  {freshnessLabel}
                </span>
              </>
            )}
            {freshnessSource && (
              <>
                <span className="text-border-default">·</span>
                <span>{freshnessSource}</span>
              </>
            )}
            {snapshotUpdatedAt && (
              <>
                <span className="text-border-default">·</span>
                <span>{new Date(snapshotUpdatedAt).toLocaleTimeString()}</span>
              </>
            )}
            <span className="text-border-default">·</span>
            <span className="font-mono">{snapshotVersion}</span>
            {primaryLanguage && (
              <>
                <span className="text-border-default">·</span>
                <span>{primaryLanguage}</span>
              </>
            )}
            {traceId && (
              <>
                <span className="text-border-default">·</span>
                <span className="font-mono">追踪 {traceId.slice(0, 8)}</span>
              </>
            )}
            {retryCount > 0 && (
              <>
                <span className="text-border-default">·</span>
                <span>重试 {retryCount}</span>
              </>
            )}
            {status === 'failed' && failureClass && (
              <>
                <span className="text-border-default">·</span>
                <span className="text-error">{failureClass}</span>
              </>
            )}
          </>
        )}
      </div>
    </footer>
  );
}
