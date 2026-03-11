import { Network, FileText } from 'lucide-react';
import { useUIStore } from '../../stores/uiStore';
import { FileTreePanel } from '@/components/FileTreePanel';
import { cn } from '../../lib/utils';

interface SidebarProps {
  fileCount?: number;
  symbolCount?: number;
  onFocusNode: (nodeId: string) => void;
}

export function Sidebar({ fileCount = 0, symbolCount = 0, onFocusNode }: SidebarProps) {
  const { viewMode, setViewMode } = useUIStore();

  return (
    <aside className="w-[280px] rounded-r-2xl p-6 flex flex-col gap-6" style={{
      background: 'var(--color-surface)'
    }}>
      {/* 视图切换 */}
      <div className="flex gap-2 p-1 rounded-xl" style={{ background: 'rgba(27, 45, 74, 0.5)' }}>
        <button
          onClick={() => setViewMode('exploring')}
          className={cn(
            "flex-1 px-4 py-2 rounded-lg text-sm font-medium transition-all duration-250 flex items-center justify-center gap-2",
            viewMode === 'exploring' ? "text-white" : "hover:bg-[var(--color-elevated)]"
          )}
          style={viewMode === 'exploring' ? {
            background: 'var(--color-accent)',
            boxShadow: '0 0 20px rgba(0, 102, 255, 0.3)'
          } : { color: 'var(--color-text-secondary)' }}
        >
          <Network className="w-4 h-4" />
          图谱
        </button>
        <button
          onClick={() => setViewMode('wiki')}
          className={cn(
            "flex-1 px-4 py-2 rounded-lg text-sm font-medium transition-all duration-250 flex items-center justify-center gap-2",
            viewMode === 'wiki' ? "text-white" : "hover:bg-[var(--color-elevated)]"
          )}
          style={viewMode === 'wiki' ? {
            background: 'var(--color-accent)',
            boxShadow: '0 0 20px rgba(0, 102, 255, 0.3)'
          } : { color: 'var(--color-text-secondary)' }}
        >
          <FileText className="w-4 h-4" />
          文档
        </button>
      </div>

      {/* 统计卡片 */}
      <div className="p-4 rounded-xl" style={{
        background: 'rgba(21, 34, 56, 0.6)',
        backdropFilter: 'blur(20px)',
        border: '1px solid rgba(255, 255, 255, 0.08)'
      }}>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <div className="text-xs" style={{ color: 'var(--color-text-muted)' }}>文件数</div>
            <div className="text-2xl font-bold" style={{ color: 'var(--color-text-primary)' }}>
              {fileCount}
            </div>
          </div>
          <div>
            <div className="text-xs" style={{ color: 'var(--color-text-muted)' }}>符号数</div>
            <div className="text-2xl font-bold" style={{ color: 'var(--color-text-primary)' }}>
              {symbolCount}
            </div>
          </div>
        </div>
      </div>

      {/* 文件树 */}
      <div className="flex-1 overflow-hidden">
        <FileTreePanel onFocusNode={onFocusNode} />
      </div>
    </aside>
  );
}
