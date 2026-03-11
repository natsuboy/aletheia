import { PanelLeft, PanelRight, Sparkles } from 'lucide-react';

interface TopBarProps {
  projectName: string;
  leftOpen: boolean;
  rightOpen: boolean;
  onToggleLeft: () => void;
  onToggleRight: () => void;
}

export function TopBar({
  projectName,
  leftOpen,
  rightOpen,
  onToggleLeft,
  onToggleRight,
}: TopBarProps) {
  return (
    <header
      className="h-full px-4 rounded-2xl glass-panel border border-border-default flex items-center justify-between"
    >
      <div className="flex items-center gap-3">
        <div
          className="w-8 h-8 rounded-lg flex items-center justify-center text-sm font-semibold shadow-[0_4px_12px_rgba(59,130,246,0.3)]"
          style={{
            background: 'linear-gradient(135deg, var(--color-accent) 0%, var(--color-accent-dim) 100%)',
            color: '#fff'
          }}
        >
          AE
        </div>
        <span className="text-base font-semibold" style={{ color: 'var(--color-text-primary)' }}>
          {projectName}
        </span>
      </div>

      <div className="flex items-center gap-2">
        <button
          onClick={onToggleLeft}
          aria-label="切换文件面板"
          className={`px-3 h-9 inline-flex items-center gap-1.5 rounded-lg border text-sm transition-all duration-200 cursor-pointer ${leftOpen
              ? 'bg-accent/12 text-text-primary border-accent/35 shadow-[0_8px_20px_rgba(14,165,233,0.12)]'
              : 'text-text-secondary border-border-subtle hover:bg-hover hover:border-accent/35'
            }`}
        >
          <PanelLeft className="w-4 h-4" />
          文件
        </button>
        <button
          onClick={onToggleRight}
          aria-label="切换对话面板"
          className={`px-3 h-9 inline-flex items-center gap-1.5 rounded-lg border text-sm transition-all duration-200 cursor-pointer ${rightOpen
              ? 'bg-gradient-to-r from-accent to-accent-secondary text-white border-transparent shadow-[0_10px_24px_rgba(14,165,233,0.28)]'
              : 'text-text-secondary border-border-subtle hover:bg-hover hover:border-accent/35'
            }`}
        >
          <Sparkles className="w-4 h-4" />
          对话
          <PanelRight className="w-4 h-4" />
        </button>
      </div>
    </header>
  );
}
