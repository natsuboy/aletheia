import { useUIStore } from '@/stores/uiStore';
import type { ViewMode } from '@/types/graph';

const TABS: { mode: ViewMode; label: string }[] = [
  { mode: 'exploring', label: '图谱' },
  { mode: 'wiki', label: '文档' },
];

export function ViewTabs() {
  const { viewMode, setViewMode } = useUIStore();

  return (
    <div className="flex items-center bg-surface border border-border-subtle rounded-lg p-0.5" role="tablist" aria-label="视图模式">
      {TABS.map((tab) => (
        <button
          key={tab.mode}
          role="tab"
          aria-selected={viewMode === tab.mode}
          onClick={() => setViewMode(tab.mode)}
          className={`px-3 py-1.5 text-xs font-medium rounded-md transition-all cursor-pointer ${
            viewMode === tab.mode
              ? 'bg-accent text-white shadow-sm'
              : 'text-text-muted hover:text-text-primary hover:bg-hover'
          }`}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}
