import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useProjectStore } from '@/stores/projectStore';
import { useIngestionStore } from '@/stores/ingestionStore';
import { useUIStore } from '@/stores/uiStore';
import { toast } from 'sonner';
import { Trash2, Loader2, ArrowRight, FolderKanban, TerminalSquare, Github, UploadCloud } from 'lucide-react';
import { UploadZone } from '@/components/ingest/UploadZone';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
  DialogDescription, DialogFooter
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';

export function ProjectSelector() {
  const navigate = useNavigate();
  const {
    projects, loading, error, fetchProjects,
    indexingJobs, restoreActiveJobs, deleteProject,
    deletingJobs, exitingProjects, clearError,
  } = useProjectStore();
  const ingestion = useIngestionStore();
  const { setViewMode } = useUIStore();

  const [repoUrl, setRepoUrl] = useState('');
  const [language, setLanguage] = useState('go');
  const [activeTab, setActiveTab] = useState<'repo' | 'scip'>('repo');
  const [deleteTarget, setDeleteTarget] = useState<{ id: string; name: string } | null>(null);

  useEffect(() => {
    setViewMode('onboarding');
    fetchProjects();
    restoreActiveJobs();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // store actions 引用稳定，mount 时执行一次即可

  // 监听删除失败，弹出 toast
  useEffect(() => {
    if (error) {
      toast.error(error);
      clearError();
    }
  }, [error, clearError]);

  const handleSubmitRepo = async () => {
    if (!repoUrl.trim()) return;
    try {
      const repoName = repoUrl.trim().replace(/\.git$/, '').split('/').pop() || 'project';
      await ingestion.startRepoIngest(repoUrl, language, repoName);
      toast.success('索引任务已提交');
      setRepoUrl('');
      navigate(`/project/${repoName}/loading`);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : '提交失败');
    }
  };

  const handleUploadScip = async (file: File, projectName: string) => {
    try {
      await ingestion.startScipUpload(file, projectName);
      toast.success('SCIP 文件已上传');
      navigate(`/project/${projectName}/loading`);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : '上传失败');
    }
  };

  const handleSelectProject = (projectId: string) => {
    navigate(`/project/${projectId}`);
  };

  const handleDeleteConfirm = async () => {
    if (!deleteTarget) return;
    const target = deleteTarget;
    // 立即关闭 Dialog
    setDeleteTarget(null);
    try {
      await deleteProject(target.id);
      toast.success(`正在删除项目 ${target.name}...`);
    } catch {
      toast.error('删除失败，请重试');
    }
  };

  return (
    <div className="onboarding-shell min-h-screen w-full flex overflow-hidden">

      {/* Left: Hero & Brand (Asymmetrical Design) */}
      <div className="flex-1 hidden lg:flex flex-col justify-center px-16 xl:px-24 relative z-10">
        <div className="absolute inset-0 pointer-events-none bg-gradient-to-r from-void to-transparent z-0" />

        <div className="relative z-10 max-w-2xl animate-slide-up">
          <div className="w-16 h-16 rounded-2xl flex items-center justify-center text-3xl font-bold bg-gradient-to-br from-accent to-accent-dim text-white shadow-[0_0_30px_rgba(59,130,246,0.5)] mb-8 animate-float">
            AE
          </div>

          <h1 className="text-6xl xl:text-7xl font-bold text-transparent bg-clip-text bg-gradient-to-br from-white via-blue-100 to-text-secondary tracking-tight mb-6 leading-tight drop-shadow-2xl">
            Aletheia <br />
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-accent to-accent-secondary filter drop-shadow-[0_0_15px_rgba(59,130,246,0.4)]">代码图谱宇宙</span>
          </h1>

          <p className="text-xl text-text-secondary leading-relaxed max-w-lg mb-12 font-medium">
            从代码索引到图谱推理，用统一工作台完成工程事实发现，洞悉代码库的深层全息结构。
          </p>

          <div className="flex gap-5">
            <div className="glass-panel rounded-2xl p-5 w-36 shadow-glow-soft border-t border-t-accent/40 bg-surface hover:bg-hover transition-colors">
              <div className="flex items-center gap-2 text-text-muted text-xs font-bold uppercase mb-2">
                <TerminalSquare size={14} className="text-accent" />
                解析深度
              </div>
              <div className="text-3xl font-bold text-white tracking-widest">AST</div>
            </div>
            <div className="glass-panel rounded-2xl p-5 w-36 shadow-glow-soft border-t border-t-accent-secondary/40 bg-surface hover:bg-hover transition-colors delay-75">
              <div className="flex items-center gap-2 text-text-muted text-xs font-bold uppercase mb-2">
                <FolderKanban size={14} className="text-accent-secondary" />
                分析图谱
              </div>
              <div className="text-3xl font-bold text-white">Graph</div>
            </div>
          </div>
        </div>
      </div>

      {/* Right: Interactive Glass Panel (Workspace Selector) */}
      <div className="w-full lg:w-[560px] xl:w-[640px] flex flex-col justify-center p-6 sm:p-12 z-20 relative backdrop-blur-3xl bg-surface/30 border-l border-border-subtle shadow-[0_0_50px_rgba(0,0,0,0.5)]">

        {/* Mobile Header (Only visible on small screens) */}
        <div className="lg:hidden flex items-center gap-3 mb-10 animate-fade-in">
          <div className="w-12 h-12 rounded-xl flex items-center justify-center text-xl font-bold bg-gradient-to-br from-accent to-accent-dim text-white shadow-glow">
            AE
          </div>
          <h1 className="text-3xl font-bold text-white">Aletheia</h1>
        </div>

        <div className="w-full max-w-md mx-auto space-y-8 animate-slide-in-right">

          {/* New Project Section */}
          <div className="glass-panel rounded-3xl p-7 shadow-glow-soft relative overflow-hidden group">
            <div className="absolute top-0 inset-x-0 h-1 bg-gradient-to-r from-accent to-accent-secondary transform origin-left transition-transform duration-500 scale-x-50 group-hover:scale-x-100" />

            <h2 className="text-xl font-semibold text-white mb-5 flex items-center gap-2">
              <SparklesIcon className="text-accent w-5 h-5" /> 建立新宇宙
            </h2>

            <div className="flex gap-1 mb-6 rounded-xl p-1 bg-void/50 border border-border-subtle w-fit shadow-inner">
              <button
                onClick={() => setActiveTab('repo')}
                className={`px-4 py-2 text-sm font-medium rounded-lg transition-all ${activeTab === 'repo'
                    ? 'bg-gradient-to-r from-accent to-accent-dim text-white shadow-[0_4px_12px_rgba(59,130,246,0.3)]'
                    : 'text-text-secondary hover:text-white hover:bg-hover'
                  }`}
              >
                <div className="flex items-center gap-2"><Github size={14} /> Git 仓库</div>
              </button>
              <button
                onClick={() => setActiveTab('scip')}
                className={`px-4 py-2 text-sm font-medium rounded-lg transition-all ${activeTab === 'scip'
                    ? 'bg-gradient-to-r from-accent to-accent-dim text-white shadow-[0_4px_12px_rgba(59,130,246,0.3)]'
                    : 'text-text-secondary hover:text-white hover:bg-hover'
                  }`}
              >
                <div className="flex items-center gap-2"><UploadCloud size={14} /> SCIP 上传</div>
              </button>
            </div>

            {activeTab === 'repo' ? (
              <div className="space-y-4">
                <div className="relative">
                  <input
                    type="text"
                    placeholder="https://github.com/user/repo.git"
                    value={repoUrl}
                    onChange={(e) => setRepoUrl(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleSubmitRepo()}
                    className="w-full pl-4 pr-10 py-3 bg-void/60 border border-border-default rounded-xl text-sm text-white placeholder:text-text-muted focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent shadow-inner transition-colors"
                  />
                  <div className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none hidden group-hover-input:block">
                    <div className="w-2 h-2 rounded-full bg-accent animate-pulse" />
                  </div>
                </div>

                <div className="flex flex-col sm:flex-row gap-3">
                  <select
                    value={language}
                    onChange={(e) => setLanguage(e.target.value)}
                    className="px-4 py-3 bg-void/60 border border-border-default rounded-xl text-sm text-white focus:outline-none focus:border-accent shadow-inner sm:w-1/3"
                  >
                    <option value="go">Go</option>
                    <option value="python">Python</option>
                    <option value="typescript">TypeScript</option>
                    <option value="javascript">JavaScript</option>
                    <option value="java">Java</option>
                  </select>
                  <button
                    onClick={handleSubmitRepo}
                    disabled={loading || !repoUrl.trim()}
                    className="flex-1 inline-flex items-center justify-center gap-2 px-6 py-3 bg-white text-void hover:bg-gray-100 text-sm font-semibold rounded-xl transition-all duration-300 hover:scale-[1.02] shadow-[0_0_20px_rgba(255,255,255,0.2)] disabled:opacity-50 disabled:cursor-not-allowed group/btn"
                  >
                    {loading ? '准备飞船...' : '启动索引引擎'}
                    {!loading && <ArrowRight size={16} className="text-void group-hover/btn:translate-x-1 transition-transform" />}
                  </button>
                </div>
              </div>
            ) : (
              <UploadZone
                onSubmit={handleUploadScip}
                loading={ingestion.status === 'uploading'}
                uploadPercent={
                  ingestion.status === 'uploading'
                    ? (ingestion.stages.find((s) => s.name === 'uploading')?.subProgress ?? undefined)
                    : undefined
                }
              />
            )}
          </div>

          {/* Active Jobs Section */}
          {indexingJobs.size > 0 && (
            <div className="glass-panel rounded-3xl p-6 shadow-glass relative border border-accent/20">
              <h2 className="text-sm font-semibold text-text-primary mb-4 flex items-center gap-2">
                <Loader2 size={14} className="text-accent animate-spin" />
                跃迁任务进行中 ({indexingJobs.size})
              </h2>
              <div className="space-y-3">
                {Array.from(indexingJobs.entries()).map(([jobId, status]) => (
                  <div key={jobId} className="flex items-center gap-3 px-4 py-3 bg-void/40 border border-border-subtle rounded-xl">
                    <div className="flex-1">
                      <div className="text-xs text-text-secondary font-medium tracking-wide mb-1.5">{status.message || status.status}</div>
                      {status.progress != null && status.progress > 0 && (
                        <div className="h-1.5 bg-void rounded-full overflow-hidden border border-border-subtle">
                          <div
                            className="h-full bg-gradient-to-r from-accent to-accent-secondary rounded-full transition-all duration-300 relative"
                            style={{ width: `${status.progress}%` }}
                          >
                            <div className="absolute inset-0 bg-white/20 animate-shimmer" />
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Existing Projects Section */}
          {projects.length > 0 && (
            <div className="glass-panel rounded-3xl p-6 shadow-glass">
              <h2 className="text-sm font-semibold text-text-secondary mb-4 flex items-center gap-2 uppercase tracking-wider">
                <FolderKanban size={14} />
                已知图谱宇宙
              </h2>
              <div className="grid gap-3 max-h-[300px] overflow-y-auto pr-2 scrollbar-thin">
                {projects.map((p) => {
                  const isDeleting = deletingJobs.has(p.id);
                  const isExiting = exitingProjects.has(p.id);

                  return (
                    <div
                      key={p.id}
                      className="group relative flex items-center justify-between p-4 bg-void/50 border border-border-subtle rounded-xl transition-all duration-300 hover:border-accent hover:bg-void/80 hover:-translate-y-1 hover:shadow-[0_8px_20px_rgba(59,130,246,0.15)] cursor-pointer"
                      onClick={() => !isDeleting && handleSelectProject(p.name || p.id)}
                      style={isExiting ? { animation: 'deleteExit 300ms cubic-bezier(0.4,0,0.2,1) forwards' } : isDeleting ? { opacity: 0.5, pointerEvents: 'none' } : undefined}
                    >
                      {isDeleting && (
                        <div className="absolute inset-0 rounded-xl overflow-hidden pointer-events-none border border-accent/30 bg-accent/5" />
                      )}

                      <div className="flex flex-col gap-1">
                        <div className="flex items-center gap-2 text-white font-medium">
                          <div className="w-1.5 h-1.5 bg-accent rounded-full group-hover:shadow-[0_0_8px_rgba(59,130,246,0.8)] transition-shadow" />
                          {p.name}
                        </div>
                        <div className="flex items-center gap-3 text-xs text-text-muted mt-0.5">
                          {p.language && <span className="uppercase font-mono text-[10px] tracking-wider text-accent-secondary">{p.language}</span>}
                          {p.file_count != null && <span>{p.file_count} 节点</span>}
                        </div>
                      </div>

                      <div className="flex items-center gap-2">
                        {!isDeleting && (
                          <div className="w-8 h-8 rounded-full bg-hover flex items-center justify-center opacity-0 group-hover:opacity-100 transition-all transform group-hover:translate-x-0 -translate-x-2 text-white">
                            <ArrowRight size={14} />
                          </div>
                        )}
                        {isDeleting ? (
                          <Loader2 size={16} className="animate-spin text-text-muted" />
                        ) : (
                          <button
                            onClick={(e) => { e.stopPropagation(); setDeleteTarget({ id: p.id, name: p.name }); }}
                            className="w-8 h-8 rounded-full flex items-center justify-center text-text-muted hover:text-error hover:bg-error/10 opacity-0 group-hover:opacity-100 transition-all cursor-pointer z-10"
                            title="销毁宇宙"
                          >
                            <Trash2 size={14} />
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

        </div>
      </div>

      <Dialog open={!!deleteTarget} onOpenChange={(open) => !open && setDeleteTarget(null)}>
        <DialogContent className="glass-panel border-error/20">
          <DialogHeader>
            <DialogTitle className="text-white">销毁图谱宇宙</DialogTitle>
            <DialogDescription className="text-text-secondary mt-2">
              确认彻底销毁 <span className="text-white font-semibold">{deleteTarget?.name}</span>？
              <br />
              此操作将清除该项目的所有结构数据，不可回溯。
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="mt-6 border-t border-border-subtle pt-4">
            <Button variant="outline" className="text-white bg-transparent border-border-default hover:bg-hover hover:text-white" onClick={() => setDeleteTarget(null)}>
              中止请求
            </Button>
            <Button variant="destructive" className="bg-error hover:bg-error-dim" onClick={handleDeleteConfirm}>
              确认销毁
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

// SparklesIcon component replacing the Missing Icon in standard Lucide for this context
function SparklesIcon(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...props}>
      <path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z" />
      <path d="M5 3v4" /><path d="M19 17v4" /><path d="M3 5h4" /><path d="M17 19h4" />
    </svg>
  );
}
