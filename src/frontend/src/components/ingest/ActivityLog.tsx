import { ScrollArea } from '@/components/ui/scroll-area';
import type { ActivityLogEntry } from '@/stores/ingestionStore';

interface ActivityLogProps {
  logs: ActivityLogEntry[];
}

function formatTime(ts: number): string {
  const d = new Date(ts);
  return d.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

export function ActivityLog({ logs }: ActivityLogProps) {
  return (
    <ScrollArea className="h-[160px]">
      <div className="space-y-0.5">
        {logs.length === 0 ? (
          <p className="text-xs text-text-muted py-4 text-center">Waiting for activity...</p>
        ) : (
          logs.map((entry, i) => (
            <div
              key={`${entry.ts}-${entry.message.slice(0, 40)}`}
              className={`flex gap-3 py-0.5 pl-2 border-l-2 transition-colors duration-500 ${
                i === 0 ? 'border-accent animate-fade-in' : 'border-transparent'
              }`}
            >
              <span className="text-xs font-mono text-text-muted shrink-0 pt-px">
                {formatTime(entry.ts)}
              </span>
              <span className="text-xs text-text-secondary leading-relaxed">{entry.message}</span>
            </div>
          ))
        )}
      </div>
    </ScrollArea>
  );
}
