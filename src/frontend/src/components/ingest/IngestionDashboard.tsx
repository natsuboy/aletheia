import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, ChevronDown, ChevronUp } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useIngestionStore } from '@/stores/ingestionStore';
import { StageTimeline } from './StageTimeline';
import { MetricsPanel } from './MetricsPanel';
import { ActivityLog } from './ActivityLog';

function formatElapsed(startedAt: number | null): string {
  if (!startedAt) return '0s';
  const ms = Date.now() - startedAt;
  const secs = Math.floor(ms / 1000);
  if (secs < 60) return `${secs}s`;
  return `${Math.floor(secs / 60)}m ${secs % 60}s`;
}

export function IngestionDashboard() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const {
    projectName, status, overallProgress, currentStage,
    writePhase, itemsTotal, itemsDone,
    stages, metrics, activityLog, startedAt, error, traceId, retryCount, failureClass,
    restoreProjectProgress, disconnect, cancelJob,
  } = useIngestionStore();

  const [elapsed, setElapsed] = useState('0s');
  const [expanded, setExpanded] = useState(false);
  const [countdown, setCountdown] = useState(3);

  useEffect(() => {
    if (status !== 'processing' && status !== 'uploading') return;
    const t = setInterval(() => setElapsed(formatElapsed(startedAt)), 1000);
    return () => clearInterval(t);
  }, [status, startedAt]);

  // 失败时自动展开详情，方便定位出错阶段
  useEffect(() => {
    if (status === 'failed') setExpanded(true);
  }, [status]);

  // 完成或失败时定格最终耗时
  useEffect(() => {
    if (status === 'completed' || status === 'failed') {
      setElapsed(formatElapsed(startedAt));
    }
  }, [status, startedAt]);

  useEffect(() => {
    if (projectId && status === 'idle') {
      void restoreProjectProgress(projectId);
    }
    return () => disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]); // restoreProjectProgress/disconnect 是 Zustand store actions，引用稳定，故意省略

  useEffect(() => {
    if (status !== 'completed') return;
    if (countdown <= 0) { navigate(`/project/${projectId}`); return; }
    const t = setTimeout(() => setCountdown((c) => c - 1), 1000);
    return () => clearTimeout(t);
  }, [status, countdown, projectId, navigate]);

  const isCompleted = status === 'completed';
  const isFailed = status === 'failed';
  const isActive = status === 'processing' || status === 'uploading';

  const stageIndex = stages.findIndex((s) => s.name === currentStage);
  const activeStageLabel = stages.find((s) => s.name === currentStage)?.label || '';
  const stageSubMessage = stages.find((s) => s.name === currentStage)?.subMessage || '';
  const writePhaseLabel = (() => {
    switch (writePhase) {
      case 'clear': return '清理项目图谱';
      case 'insert_nodes': return '写入节点';
      case 'snapshot': return '准备边快照';
      case 'bulk_load': return '批量写入边';
      case 'verify': return '校验边关系';
      case 'vectorizing': return '向量化处理中';
      case 'completed': return '完成';
      default: return '';
    }
  })();

  const borderClass = isCompleted
    ? 'border-accent-secondary/40'
    : isFailed
      ? 'border-error/40'
      : 'border-border-subtle';

  const barClass = isCompleted
    ? 'bg-accent-secondary'
    : isFailed
      ? 'bg-error'
      : 'bg-gradient-to-r from-accent to-node-interface';

  return (
    <div className="min-h-screen onboarding-shell flex flex-col items-center justify-center p-4 md:p-8">
      {/* Logo */}
      <div className="flex items-center gap-2.5 mb-10">
        <div className="w-8 h-8 flex items-center justify-center bg-gradient-to-br from-accent to-accent-secondary rounded-lg shadow-glow text-white text-sm font-bold">
          ◇
        </div>
        <span className="text-lg font-semibold tracking-tight">Aletheia</span>
      </div>

      <div className="w-full max-w-2xl space-y-3 relative z-10">
        {/* Main card */}
        <div className={`panel-surface rounded-2xl p-6 space-y-4 transition-colors duration-500 ${borderClass}`}>

          {/* Project name + status badge */}
          <div className="flex items-center justify-between">
            <h1 className="text-xl font-semibold text-text-primary truncate">
              {projectName || projectId}
            </h1>
            {isCompleted && (
              <span className="text-xs font-medium text-accent-secondary">✓ 已完成</span>
            )}
            {isFailed && (
              <span className="text-xs font-medium text-error">失败</span>
            )}
          </div>

          {/* Stage description */}
          <p className="text-sm text-text-secondary min-h-[20px]">
            {isCompleted
              ? '索引已完成。'
              : isFailed
                ? (error || '处理过程中出现错误。')
                : activeStageLabel
                  ? `${activeStageLabel}${stageSubMessage ? ` · ${stageSubMessage}` : ''}${writePhaseLabel ? ` · ${writePhaseLabel}` : '...'}`
                  : '正在启动...'}
          </p>
          {itemsTotal != null && itemsTotal > 0 && (
            <p className="text-xs text-text-muted font-mono">
              {Math.max(0, itemsDone ?? 0)} / {itemsTotal}
            </p>
          )}

          {/* Progress bar */}
          <div className="space-y-1.5">
            <div className="relative h-1.5 rounded-full bg-elevated overflow-hidden">
              <div
                className={`h-full rounded-full transition-all duration-700 ease-out ${barClass}`}
                style={{ width: `${overallProgress}%` }}
              />
              {isActive && overallProgress > 0 && (
                <div
                  className="absolute inset-y-0 left-0 bg-gradient-to-r from-transparent via-white/10 to-transparent animate-shimmer"
                  style={{ width: `${overallProgress}%` }}
                />
              )}
            </div>
            <div className="flex justify-between text-xs text-text-secondary font-mono">
              <span>
                {stageIndex >= 0 && stages.length > 0
                  ? `阶段 ${stageIndex + 1} / ${stages.length}`
                  : isCompleted
                    ? `${stages.length} 个阶段`
                    : ''}
              </span>
              <span>
                {isCompleted ? overallProgress : Math.round(overallProgress)}%
                {isActive && ` · ${elapsed}`}
              </span>
            </div>
          </div>

          {/* Metrics row — always visible */}
          <MetricsPanel metrics={metrics} />

          {/* Completed CTA */}
          {isCompleted && (
            <div className="flex items-center gap-3 pt-1 animate-fade-in">
              <Button onClick={() => navigate(`/project/${projectId}`)} className="flex-1">
                打开项目（{countdown}s）
              </Button>
              <button
                onClick={() => navigate(`/project/${projectId}`)}
                className="text-xs text-text-muted hover:text-text-secondary transition-colors"
              >
                跳过
              </button>
            </div>
          )}

          {/* Failed CTA */}
          {isFailed && (
            <div className="pt-1 animate-fade-in">
              <Button variant="outline" onClick={() => navigate('/')} className="w-full">
                返回上传页
              </Button>
            </div>
          )}

          {/* Cancel CTA */}
          {isActive && (
            <div className="pt-1">
              <Button
                variant="outline"
                onClick={() => void cancelJob()}
                className="w-full text-text-muted hover:text-error hover:border-error/50"
              >
                取消任务
              </Button>
            </div>
          )}

          {/* Expand toggle */}
          {stages.length > 0 && (
            <button
              onClick={() => setExpanded((e) => !e)}
              className="flex items-center gap-1 text-xs text-text-muted hover:text-text-secondary transition-colors ml-auto"
            >
              {expanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
              {expanded ? '收起' : '详情'}
            </button>
          )}
        </div>

        {/* Expandable detail panel */}
        {expanded && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 animate-fade-in">
            <div className="panel-surface rounded-xl p-4">
              <p className="section-kicker mb-3">阶段进度</p>
              <StageTimeline stages={stages} />
            </div>
            <div className="panel-surface rounded-xl p-4">
              <p className="section-kicker mb-3">活动日志</p>
              <ActivityLog logs={activityLog} />
              {(traceId || failureClass || retryCount > 0) && (
                <div className="mt-3 pt-3 border-t border-border-subtle space-y-1 text-xs text-text-muted font-mono">
                  {traceId && <div>追踪: {traceId}</div>}
                  {retryCount > 0 && <div>重试次数: {retryCount}</div>}
                  {failureClass && <div>失败类型: {failureClass}</div>}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Back link */}
        <button
          onClick={() => navigate('/')}
          className="flex items-center gap-1.5 text-xs text-text-muted hover:text-text-secondary transition-colors"
        >
          <ArrowLeft className="w-3 h-3" />
          返回项目列表
        </button>
      </div>
    </div>
  );
}
