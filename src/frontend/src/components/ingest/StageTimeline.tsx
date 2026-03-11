import { CheckCircle2, Circle, XCircle, Loader2 } from 'lucide-react';
import type { StageInfo } from '@/stores/ingestionStore';

function formatDuration(startedAt: number | null, completedAt: number | null): string {
  if (!startedAt) return '—';
  const end = completedAt || Date.now(); // 进行中阶段依赖父组件每秒 re-render 来更新显示值
  const ms = Math.max(0, end - startedAt);
  if (ms < 1000) return `${ms}ms`;
  const secs = ms / 1000;
  if (secs < 60) return `${secs.toFixed(1)}s`;
  const mins = Math.floor(secs / 60);
  return `${mins}m ${Math.round(secs % 60)}s`;
}

function StageIcon({ status }: { status: StageInfo['status'] }) {
  const cls = 'w-4 h-4 shrink-0';
  switch (status) {
    case 'completed': return <CheckCircle2 className={`${cls} text-accent-secondary`} />;
    case 'active':    return <Loader2 className={`${cls} text-accent animate-spin`} />;
    case 'failed':    return <XCircle className={`${cls} text-error`} />;
    default:          return <Circle className={`${cls} text-border-default`} />;
  }
}

export function StageTimeline({ stages }: { stages: StageInfo[] }) {
  return (
    <div className="space-y-0">
      {stages.map((stage, i) => {
        const isLast = i === stages.length - 1;
        return (
          <div key={stage.name} className="flex gap-2.5">
            {/* Icon + connector */}
            <div className="flex flex-col items-center w-4 shrink-0">
              <StageIcon status={stage.status} />
              {!isLast && (
                <div
                  className={`w-px flex-1 min-h-[14px] mt-0.5 transition-colors duration-500 ${
                    stage.status === 'completed'
                      ? 'bg-accent-secondary/50'
                      : stage.status === 'active'
                        ? 'bg-accent/30'
                        : 'bg-border-subtle'
                  }`}
                />
              )}
            </div>

            {/* Label + duration */}
            <div className={`flex-1 ${isLast ? 'pb-0' : 'pb-3'}`}>
              <div className="flex items-center justify-between">
                <span
                  className={`text-xs font-medium transition-all duration-300 ${
                    stage.status === 'active'
                      ? 'text-text-primary'
                      : stage.status === 'completed'
                        ? 'text-text-muted'
                        : stage.status === 'failed'
                          ? 'text-error'
                          : 'text-border-default'
                  }`}
                >
                  {stage.label}
                </span>
                <span className="text-xs font-mono text-text-muted">
                  {stage.status === 'completed'
                    ? formatDuration(stage.startedAt, stage.completedAt)
                    : stage.status === 'active'
                      ? formatDuration(stage.startedAt, null)
                      : ''}
                </span>
              </div>

              {stage.status === 'active' && stage.subMessage && (
                <p className="text-xs text-text-muted mt-0.5 truncate">{stage.subMessage}</p>
              )}
              {stage.status === 'failed' && stage.subMessage && (
                <p className="text-xs text-error mt-0.5">{stage.subMessage}</p>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
