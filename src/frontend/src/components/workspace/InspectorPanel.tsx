import { Suspense, lazy } from 'react';
import { X } from 'lucide-react';
import { useUIStore } from '../../stores/uiStore';

const CodeReferencesPanel = lazy(async () => {
  const mod = await import('@/components/CodeReferencesPanel');
  return { default: mod.CodeReferencesPanel };
});

const RightPanel = lazy(async () => {
  const mod = await import('@/components/RightPanel');
  return { default: mod.RightPanel };
});

export function InspectorPanel() {
  const { isCodePanelOpen, isRightPanelOpen, setCodePanelOpen } = useUIStore();

  if (!isCodePanelOpen && !isRightPanelOpen) return null;

  // 主任务优先：同一时刻只展示一个右侧次级面板
  const showCodePanel = isCodePanelOpen;

  return (
    <>
      {/* 代码引用面板 */}
      {showCodePanel && (
        <aside
          className="w-[400px] glass-panel rounded-2xl animate-slide-in-right overflow-hidden shadow-2xl flex flex-col"
        >
          <div className="h-full flex flex-col">
            <div className="panel-header">
              <h3 className="section-title text-text-primary">
                代码引用
              </h3>
              <button
                onClick={() => setCodePanelOpen(false)}
                aria-label="关闭代码引用面板"
                className="icon-button cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="flex-1 overflow-hidden">
              <Suspense fallback={<div className="empty-state h-full"><div className="empty-state-title">代码引用加载中</div><div className="empty-state-desc">正在准备代码证据，请稍候。</div></div>}>
                <CodeReferencesPanel />
              </Suspense>
            </div>
          </div>
        </aside>
      )}

      {/* AI 对话面板 */}
      {!showCodePanel && isRightPanelOpen && (
        <Suspense fallback={<div className="w-[420px] border-l border-border-subtle bg-surface" />}>
          <RightPanel />
        </Suspense>
      )}
    </>
  );
}
