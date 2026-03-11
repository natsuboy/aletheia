import { useState } from 'react';
import { ChevronRight, ChevronDown, FileText, BookOpen } from 'lucide-react';
import { useWikiStore } from '@/stores/wikiStore';
import type { WikiSection } from '@/types/wiki';

interface SectionNodeProps {
  sectionId: string;
  depth: number;
}

function SectionNode({ sectionId, depth }: SectionNodeProps) {
  const { wiki, currentPageId, setCurrentPage } = useWikiStore();
  const [expanded, setExpanded] = useState(true);

  if (!wiki) return null;
  const section = wiki.sections[sectionId];
  if (!section) return null;

  const hasChildren = section.pages.length > 0 || section.subsections.length > 0;

  return (
    <div>
      <button
        role="treeitem"
        aria-expanded={expanded}
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-1.5 px-2 py-1.5 text-sm text-text-secondary hover:text-text-primary hover:bg-hover rounded transition-colors cursor-pointer"
        style={{ paddingLeft: `${depth * 12 + 8}px` }}
      >
        {hasChildren ? (
          expanded ? <ChevronDown className="w-3.5 h-3.5 flex-shrink-0" /> : <ChevronRight className="w-3.5 h-3.5 flex-shrink-0" />
        ) : (
          <span className="w-3.5" />
        )}
        <span className="truncate font-medium">{section.title}</span>
      </button>

      {expanded && (
        <div>
          {section.pages.map((pageId) => {
            const page = wiki.pages[pageId];
            if (!page) return null;
            return (
              <button
                key={pageId}
                onClick={() => setCurrentPage(pageId)}
                className={`w-full flex items-center gap-1.5 px-2 py-1.5 text-xs rounded transition-colors cursor-pointer ${
                  currentPageId === pageId
                    ? 'bg-accent/20 text-accent'
                    : 'text-text-muted hover:text-text-primary hover:bg-hover'
                }`}
                style={{ paddingLeft: `${(depth + 1) * 12 + 8}px` }}
              >
                <FileText className="w-3 h-3 flex-shrink-0" />
                <span className="truncate">{page.title}</span>
              </button>
            );
          })}
          {section.subsections.map((subId) => (
            <SectionNode key={subId} sectionId={subId} depth={depth + 1} />
          ))}
        </div>
      )}
    </div>
  );
}

export function WikiSidebar() {
  const { wiki } = useWikiStore();

  if (!wiki) {
    return (
      <div className="w-60 bg-surface border-r border-border-subtle">
        <div className="empty-state h-full">
          <div className="empty-state-icon">
            <BookOpen className="w-5 h-5" />
          </div>
          <div className="empty-state-title text-sm">暂无文档</div>
          <div className="empty-state-desc">请先生成 Wiki，再进行结构化阅读。</div>
        </div>
      </div>
    );
  }

  return (
    <aside className="w-60 bg-surface border-r border-border-subtle flex flex-col overflow-hidden flex-shrink-0">
      <div className="px-3 py-2.5 border-b border-border-subtle">
        <h2 className="text-sm font-semibold text-text-primary truncate">{wiki.title}</h2>
        <p className="text-xs text-text-muted mt-0.5 truncate">{wiki.description}</p>
      </div>
      <nav className="flex-1 overflow-y-auto py-1 scrollbar-thin" role="tree" aria-label="Wiki 导航">
        {wiki.root_sections.map((sectionId) => (
          <SectionNode key={sectionId} sectionId={sectionId} depth={0} />
        ))}
      </nav>
    </aside>
  );
}
