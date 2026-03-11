import { useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  ArrowLeft,
  BookOpen,
  Bot,
  FileCode2,
  Files,
  GitGraph,
  LayoutPanelTop,
  Loader2,
  PanelLeftClose,
  PanelLeftOpen,
} from 'lucide-react';
import { useProjectStore } from '@/stores/projectStore';
import { useUIStore } from '@/stores/uiStore';
import { useIngestionStore } from '@/stores/ingestionStore';
import { useChatStore } from '@/stores/chatStore';

interface WorkflowRailProps {
  collapsed: boolean;
  onToggleCollapse: () => void;
}

function RailButton({
  active,
  label,
  icon,
  onClick,
  collapsed,
  hint,
}: {
  active?: boolean;
  label: string;
  icon: React.ReactNode;
  onClick: () => void;
  collapsed: boolean;
  hint?: string;
}) {
  return (
    <button
      onClick={onClick}
      title={collapsed ? label : hint ?? label}
      className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-xl border transition-colors text-left cursor-pointer ${
        active
          ? 'bg-accent/12 border-accent/45 text-text-primary'
          : 'bg-elevated border-border-subtle text-text-secondary hover:text-text-primary hover:border-accent/25'
      }`}
    >
      <span className="shrink-0">{icon}</span>
      {!collapsed && (
        <span className="text-xs font-medium truncate">{label}</span>
      )}
    </button>
  );
}

export function WorkflowRail({ collapsed, onToggleCollapse }: WorkflowRailProps) {
  const navigate = useNavigate();
  const { projectId } = useParams<{ projectId: string }>();
  const { currentProject } = useProjectStore();
  const {
    viewMode,
    setViewMode,
    isFileTreeOpen,
    isCodePanelOpen,
    isRightPanelOpen,
    toggleFileTree,
    toggleCodePanel,
    toggleRightPanel,
    operationTimeline,
  } = useUIStore();
  const { status, currentStage, overallProgress } = useIngestionStore();
  const { messages } = useChatStore();
  const [endpointQuery, setEndpointQuery] = useState('');
  const [referenceQuery, setReferenceQuery] = useState('');
  const [askQuery, setAskQuery] = useState('');

  const dispatchCommand = (mode: 'endpoint' | 'refs' | 'ask', initialQuery?: string) => {
    const q = initialQuery?.trim();
    window.dispatchEvent(new CustomEvent('aletheia:open-command', {
      detail: q ? { mode, initialQuery: q } : { mode },
    }));
  };

  const ingestActive = status === 'processing' || status === 'uploading';
  const projectLabel = currentProject?.name || projectId || '未命名项目';
  const modeLabel = viewMode === 'wiki' ? '文档阅读模式' : '图谱探索模式';

  const checklist = useMemo(
    () => [
      { key: 'project', label: '1. 选择项目', done: !!currentProject },
      { key: 'explore', label: '2. 浏览结构', done: viewMode === 'exploring' },
      { key: 'evidence', label: '3. 查看证据', done: isCodePanelOpen },
      { key: 'ask', label: '4. 问答推理', done: messages.some((m) => m.role === 'assistant') },
    ],
    [currentProject, viewMode, isCodePanelOpen, messages],
  );

  const nextAction = useMemo(() => {
    if (!currentProject) {
      return {
        label: '返回并选择项目',
        detail: '先选定目标项目，才能进入分析流程',
        onClick: () => navigate('/'),
      };
    }
    if (ingestActive) {
      return {
        label: '查看索引进度',
        detail: `${currentStage || '处理中'} · ${Math.round(overallProgress)}%`,
        onClick: () => navigate(`/project/${projectId}/loading`),
      };
    }
    if (viewMode !== 'exploring') {
      return {
        label: '切到图谱探索',
        detail: '先从结构视图定位关键模块',
        onClick: () => setViewMode('exploring'),
      };
    }
    if (!isCodePanelOpen) {
      return {
        label: '打开代码证据面板',
        detail: '让引用定位与证据对齐',
        onClick: () => toggleCodePanel(),
      };
    }
    if (!isRightPanelOpen) {
      return {
        label: '打开 AI 对话面板',
        detail: '开始针对当前结构进行问答',
        onClick: () => toggleRightPanel(),
      };
    }
    if (!messages.some((m) => m.role === 'assistant')) {
      return {
        label: '发起第一轮问题',
        detail: '例如：解释核心架构与关键调用链',
        onClick: () => toggleRightPanel(),
      };
    }
      return {
        label: '切到文档阅读模式',
        detail: '对照文档继续深挖设计细节',
        onClick: () => setViewMode('wiki'),
      };
  }, [
    currentProject,
    ingestActive,
    currentStage,
    overallProgress,
    navigate,
    projectId,
    viewMode,
    setViewMode,
    isCodePanelOpen,
    toggleCodePanel,
    isRightPanelOpen,
    toggleRightPanel,
    messages,
  ]);

  return (
    <aside className={`${collapsed ? 'w-[64px]' : 'w-[240px]'} border-r border-border-subtle bg-surface flex flex-col transition-all duration-200 shrink-0`}>
      <div className="p-3 border-b border-border-subtle space-y-2">
        <div className="flex items-center justify-between gap-2">
          {!collapsed && (
            <button
              onClick={() => navigate('/')}
              className="inline-flex items-center gap-1 text-xs text-text-muted hover:text-text-primary cursor-pointer"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              项目列表
            </button>
          )}
          <button
            onClick={onToggleCollapse}
            className="icon-button cursor-pointer"
            title={collapsed ? '展开导航' : '收起导航'}
          >
            {collapsed ? <PanelLeftOpen className="w-4 h-4" /> : <PanelLeftClose className="w-4 h-4" />}
          </button>
        </div>

        {!collapsed && (
          <>
            <div className="px-2 py-1.5 rounded-lg bg-elevated border border-border-subtle">
              <div className="section-kicker">当前项目</div>
              <div className="text-sm font-medium text-text-primary truncate">{projectLabel}</div>
              <div className="text-xs text-text-muted mt-0.5">{modeLabel}</div>
            </div>
            {ingestActive && (
              <button
                onClick={() => navigate(`/project/${projectId}/loading`)}
                className="w-full px-2 py-1.5 rounded-lg bg-accent/10 border border-accent/30 text-left cursor-pointer"
              >
                <div className="flex items-center gap-1.5 text-xs text-accent">
                  <Loader2 className="w-3 h-3 animate-spin" />
                  {currentStage || '处理中'} · {Math.round(overallProgress)}%
                </div>
              </button>
            )}
          </>
        )}
      </div>

      <div className="p-3 space-y-2">
        <RailButton
          active={viewMode === 'exploring'}
          label="图谱探索"
          icon={<GitGraph className="w-4 h-4" />}
          onClick={() => setViewMode('exploring')}
          collapsed={collapsed}
          hint="切换到图谱模式"
        />
        <RailButton
          active={viewMode === 'wiki'}
          label="文档阅读"
          icon={<BookOpen className="w-4 h-4" />}
          onClick={() => setViewMode('wiki')}
          collapsed={collapsed}
          hint="切换到文档阅读模式"
        />
      </div>

      <div className="px-3 pb-3 space-y-2 border-b border-border-subtle">
        <RailButton
          active={isFileTreeOpen}
          label="文件树"
          icon={<Files className="w-4 h-4" />}
          onClick={toggleFileTree}
          collapsed={collapsed}
        />
        <RailButton
          active={isCodePanelOpen}
          label="代码证据"
          icon={<FileCode2 className="w-4 h-4" />}
          onClick={toggleCodePanel}
          collapsed={collapsed}
        />
        <RailButton
          active={isRightPanelOpen}
          label="AI 对话"
          icon={<Bot className="w-4 h-4" />}
          onClick={toggleRightPanel}
          collapsed={collapsed}
        />
      </div>

      {!collapsed && (
        <div className="p-3 flex-1 overflow-y-auto space-y-2">
          <div className="section-kicker">下一步</div>
          <button onClick={nextAction.onClick} className="w-full px-2.5 py-2 rounded-md border border-accent/40 bg-accent/10 text-left hover:bg-accent/20 transition-colors cursor-pointer">
            <div className="text-xs font-medium text-text-primary">{nextAction.label}</div>
            <div className="text-xs text-text-muted mt-0.5">{nextAction.detail}</div>
          </button>
          <div className="section-kicker">操作路径</div>
          {checklist.map((item) => (
            <div
              key={item.key}
              className={`px-2 py-1.5 rounded-md text-xs border ${
                item.done
                  ? 'bg-accent-secondary/10 border-accent-secondary/30 text-accent-secondary'
                  : 'bg-elevated border-border-subtle text-text-secondary'
              }`}
            >
              {item.label}
            </div>
          ))}
          <div className="pt-2 border-t border-border-subtle text-xs text-text-muted">
            <div className="flex items-center gap-1.5"><LayoutPanelTop className="w-3 h-3" /> Ctrl/Cmd + K: 搜索节点</div>
            <div className="mt-1">Esc: 依次关闭选中节点/证据面板/聊天面板</div>
          </div>

          <div className="pt-2 border-t border-border-subtle space-y-2">
            <div className="section-kicker">高频任务</div>

            <div className="interactive-surface rounded-xl p-2 space-y-1.5">
              <div className="text-xs text-text-secondary">找 Gin 接口实现入口</div>
              <div className="flex gap-1.5">
                <input
                  value={endpointQuery}
                  onChange={(e) => setEndpointQuery(e.target.value)}
                  placeholder="例如 /api/user"
                  className="flex-1 h-7 px-2 rounded bg-surface border border-border-subtle text-xs text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent"
                />
                <button
                  onClick={() => dispatchCommand('endpoint', endpointQuery)}
                  disabled={!endpointQuery.trim()}
                  className="chip chip-accent px-2 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  查找
                </button>
              </div>
            </div>

            <div className="interactive-surface rounded-xl p-2 space-y-1.5">
              <div className="text-xs text-text-secondary">查看函数引用关系（2 跳）</div>
              <div className="flex gap-1.5">
                <input
                  value={referenceQuery}
                  onChange={(e) => setReferenceQuery(e.target.value)}
                  placeholder="例如 创建用户"
                  className="flex-1 h-7 px-2 rounded bg-surface border border-border-subtle text-xs text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent"
                />
                <button
                  onClick={() => dispatchCommand('refs', referenceQuery)}
                  disabled={!referenceQuery.trim()}
                  className="chip chip-accent px-2 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  分析
                </button>
              </div>
            </div>

            <div className="interactive-surface rounded-xl p-2 space-y-1.5">
              <div className="text-xs text-text-secondary">研究问答（回答优先）</div>
              <div className="flex gap-1.5">
                <input
                  value={askQuery}
                  onChange={(e) => setAskQuery(e.target.value)}
                  placeholder="例如 核心调用链是什么？"
                  className="flex-1 h-7 px-2 rounded bg-surface border border-border-subtle text-xs text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent"
                />
                <button
                  onClick={() => dispatchCommand('ask', askQuery)}
                  disabled={!askQuery.trim()}
                  className="chip chip-secondary px-2 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  提问
                </button>
              </div>
            </div>
          </div>

          <div className="pt-2 border-t border-border-subtle space-y-1.5">
            <div className="section-kicker">最近操作</div>
            {operationTimeline.length === 0 ? (
              <div className="empty-state py-5 px-2 rounded bg-elevated border border-border-subtle">
                <div className="empty-state-title text-sm">暂无记录</div>
                <div className="empty-state-desc">先执行一个任务，系统会在这里记录你的操作轨迹。</div>
              </div>
            ) : (
              operationTimeline.slice(0, 5).map((op) => (
                <div key={op.id} className="px-2 py-1 rounded bg-elevated border border-border-subtle">
                  <div className="text-xs text-text-primary truncate">{op.label}</div>
                  <div className="text-xs text-text-muted">{new Date(op.timestamp).toLocaleTimeString()}</div>
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </aside>
  );
}
