import { ChevronDown, ChevronRight } from 'lucide-react';
import { useState } from 'react';
import { useResearchStore } from '@/stores/researchStore';
import { MarkdownRenderer } from '@/components/MarkdownRenderer';

export function ResearchProgress() {
  const { session } = useResearchStore();

  if (!session || session.iterations.length === 0) return null;

  return (
    <div className="px-4 py-2 border-b border-accent/30 bg-gradient-to-r from-accent/10 to-node-interface/10">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-medium text-accent">
          深度研究 {session.iterations.length}/{session.max_iterations}
        </span>
        <span className="text-xs text-text-muted">
          {session.status === 'active' ? '进行中' : session.status === 'concluded' ? '已完成' : session.status}
        </span>
      </div>
      <div className="w-full h-1 bg-surface rounded-full overflow-hidden" role="progressbar" aria-valuenow={session.iterations.length} aria-valuemin={0} aria-valuemax={session.max_iterations} aria-label="研究进度">
        <div
          className="h-full bg-gradient-to-r from-accent to-node-interface rounded-full transition-all"
          style={{ width: `${(session.iterations.length / session.max_iterations) * 100}%` }}
        />
      </div>
      <div className="mt-2 space-y-1">
        {session.iterations.map((iter) => (
          <IterationAccordion key={iter.iteration} iteration={iter} />
        ))}
      </div>
    </div>
  );
}

function IterationAccordion({ iteration }: { iteration: { iteration: number; query: string; findings: string } }) {
  const [open, setOpen] = useState(false);

  return (
    <div className="border border-border-subtle rounded-md overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-1.5 px-2 py-1.5 text-xs text-text-secondary hover:bg-hover transition-colors cursor-pointer"
      >
        {open ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
        <span className="font-medium">轮次 {iteration.iteration}</span>
        <span className="text-text-muted truncate ml-1">· {iteration.query}</span>
      </button>
      {open && (
        <div className="px-3 py-2 text-xs border-t border-border-subtle chat-prose">
          <MarkdownRenderer content={iteration.findings} />
        </div>
      )}
    </div>
  );
}
