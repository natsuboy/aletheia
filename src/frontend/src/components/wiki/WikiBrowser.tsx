import { useEffect, useState } from 'react';
import { useProjectStore } from '@/stores/projectStore';
import { useWikiStore } from '@/stores/wikiStore';
import { Sparkles } from 'lucide-react';
import { WikiSidebar } from './WikiSidebar';
import { WikiPageView } from './WikiPageView';
import { WikiGenerateButton } from './WikiGenerateButton';
import type { WikiDiagnosticResponse } from '@/types/wiki';

function GenerationProgress({ status }: { status: ReturnType<typeof useWikiStore.getState>['generationStatus'] }) {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    setElapsed(0);
    const timer = setInterval(() => setElapsed((e) => e + 1), 1000);
    return () => clearInterval(timer);
  }, [status?.status]);

  const isPending = !status || status.status === 'pending';
  const progress = status?.progress ?? 0;
  const message = status?.message || (isPending ? '任务排队中，等待 Worker 处理…' : 'Wiki 生成中…');

  const formatTime = (s: number) => {
    const m = Math.floor(s / 60);
    const sec = s % 60;
    return m > 0 ? `${m}分${sec.toString().padStart(2, '0')}秒` : `${sec}秒`;
  };

  return (
    <div className="flex-1 flex flex-col items-center justify-center gap-5 text-center px-8">
      {/* 状态标签 */}
      <div className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${
        isPending
          ? 'bg-yellow-500/10 text-yellow-400'
          : 'bg-accent/10 text-accent'
      }`}>
        <span className={`w-1.5 h-1.5 rounded-full ${
          isPending ? 'bg-yellow-400 animate-pulse' : 'bg-accent animate-pulse'
        }`} />
        {isPending ? '排队中' : '生成中'}
      </div>

      {/* Spinner */}
      <div className={`h-8 w-8 border-2 rounded-full animate-spin ${
        isPending
          ? 'border-yellow-400/30 border-t-yellow-400'
          : 'border-accent/30 border-t-accent'
      }`} />

      {/* 消息 */}
      <div className="text-text-muted text-sm">{message}</div>

      {/* 进度条 - 仅 running 时显示实际进度 */}
      <div className="w-56">
        {isPending ? (
          <div className="h-1.5 bg-elevated rounded-full overflow-hidden">
            <div className="h-full w-1/3 bg-yellow-400/50 rounded-full animate-[indeterminate_1.5s_ease-in-out_infinite]" />
          </div>
        ) : (
          <div className="h-1.5 bg-elevated rounded-full overflow-hidden">
            <div
              className="h-full bg-accent rounded-full transition-all duration-500"
              style={{ width: `${Math.max(progress, 2)}%` }}
            />
          </div>
        )}
        {!isPending && progress > 0 && (
          <div className="text-text-muted text-xs mt-1.5">{Math.round(progress)}%</div>
        )}
      </div>

      {/* 已用时间 */}
      <div className="text-text-muted/60 text-xs">
        已等待 {formatTime(elapsed)}
      </div>
    </div>
  );
}

function WikiDiagnosticPanel({ diagnostic }: { diagnostic: WikiDiagnosticResponse }) {
  const g = diagnostic.graph;
  const c = diagnostic.clustering;
  const cache = diagnostic.cache;
  const job = diagnostic.job;

  return (
    <div className="w-full max-w-md text-left text-xs space-y-3 p-4 bg-elevated rounded-lg border border-border">
      <div className="text-text-muted font-medium text-sm">诊断信息</div>

      <div className="space-y-1.5">
        <div className="flex justify-between">
          <span className="text-text-muted">图节点</span>
          <span>{g.error ? '错误' : g.node_count}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-text-muted">图边</span>
          <span>{g.error ? '错误' : g.edge_count}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-text-muted">社区检测</span>
          <span>{g.error ? '错误' : g.has_community_ids ? '已启用' : '未启用'}</span>
        </div>
      </div>

      <div className="space-y-1.5">
        <div className="flex justify-between">
          <span className="text-text-muted">社区数量</span>
          <span>{c.error ? '错误' : c.community_count}</span>
        </div>
      </div>

      <div className="space-y-1.5">
        <div className="flex justify-between">
          <span className="text-text-muted">Redis 缓存</span>
          <span>{cache.error ? '错误' : cache.redis_exists ? '存在' : '不存在'}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-text-muted">文件缓存</span>
          <span>{cache.error ? '错误' : cache.file_exists ? `${(cache.file_size_bytes / 1024).toFixed(1)} KB` : '不存在'}</span>
        </div>
      </div>

      {job.last_job_id && (
        <div className="space-y-1.5">
          <div className="flex justify-between">
            <span className="text-text-muted">最近任务</span>
            <span>{job.last_status ?? '未知'}</span>
          </div>
          {job.last_message && (
            <div className="text-text-muted/70 truncate">{job.last_message}</div>
          )}
        </div>
      )}
    </div>
  );
}

export function WikiBrowser() {
  const { currentProject } = useProjectStore();
  const { wiki, loading, error, isGenerating, generationStatus, diagnostic, restoreWikiJob } = useWikiStore();

  useEffect(() => {
    if (currentProject) {
      restoreWikiJob(currentProject.name);
    }
  }, [currentProject, restoreWikiJob]);

  if (isGenerating) {
    return <GenerationProgress status={generationStatus} />;
  }

  if (loading) {
    return (
      <div className="flex-1 empty-state">
        <div className="empty-state-icon">
          <Sparkles className="w-5 h-5" />
        </div>
        <div className="empty-state-title">文档加载中</div>
        <div className="empty-state-desc">正在读取文档内容，请稍候。</div>
      </div>
    );
  }

  if (!wiki) {
    return (
      <div className="flex-1 empty-state px-8">
        <div className="empty-state-icon">
          <Sparkles className="w-5 h-5" />
        </div>
        <div className="empty-state-desc">
          {error ? `错误：${error}` : '当前项目尚未生成 Wiki。'}
        </div>
        {diagnostic && <WikiDiagnosticPanel diagnostic={diagnostic} />}
        <WikiGenerateButton />
      </div>
    );
  }

  return (
    <div className="flex-1 flex overflow-hidden">
      <WikiSidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <div className="flex items-center justify-end px-4 py-2 border-b border-border">
          <WikiGenerateButton variant="regenerate" />
        </div>
        <WikiPageView />
      </div>
    </div>
  );
}
