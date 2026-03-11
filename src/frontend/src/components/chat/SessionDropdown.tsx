import { Plus } from 'lucide-react';
import { useChatStore } from '@/stores/chatStore';

export function SessionDropdown() {
  const { sessionId, newSession } = useChatStore();

  return (
    <div className="flex items-center gap-1.5">
      <span className="text-xs text-text-muted font-mono truncate max-w-[96px]" title={sessionId ?? ''}>
        {sessionId ? sessionId.slice(0, 8) : '—'}
      </span>
      <button
        onClick={newSession}
        aria-label="新建会话"
        title="新建会话"
        className="p-1 text-text-muted hover:text-text-primary hover:bg-hover rounded transition-colors cursor-pointer"
      >
        <Plus className="w-3.5 h-3.5" />
      </button>
    </div>
  );
}
