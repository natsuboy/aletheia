import { Microscope } from 'lucide-react';
import { useChatStore } from '@/stores/chatStore';

export function ResearchToggle() {
  const { isResearchMode, setResearchMode } = useChatStore();

  return (
    <button
      onClick={() => setResearchMode(!isResearchMode)}
      aria-pressed={isResearchMode}
      title={isResearchMode ? 'Switch to normal chat' : 'Switch to DeepResearch mode'}
      className={`flex items-center gap-1 px-2 py-1 text-xs rounded-md transition-all cursor-pointer ${
        isResearchMode
          ? 'bg-gradient-to-r from-accent to-node-interface text-white shadow-glow'
          : 'text-text-muted hover:text-text-primary hover:bg-hover border border-border-subtle'
      }`}
    >
      <Microscope className="w-3.5 h-3.5" />
      <span>Research</span>
    </button>
  );
}
