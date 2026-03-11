import { useWikiStore } from '@/stores/wikiStore';
import { MarkdownRenderer } from '@/components/MarkdownRenderer';
import { FileText } from 'lucide-react';

interface WikiPageViewProps {
  onLinkClick?: (href: string) => void;
}

export function WikiPageView({ onLinkClick }: WikiPageViewProps) {
  const { wiki, currentPageId } = useWikiStore();

  if (!wiki || !currentPageId) {
    return (
      <div className="flex-1 empty-state">
        <div className="empty-state-icon">
          <FileText className="w-5 h-5" />
        </div>
        <div className="empty-state-title">请选择页面</div>
        <div className="empty-state-desc">请先从左侧目录选择一个页面开始阅读。</div>
      </div>
    );
  }

  const page = wiki.pages[currentPageId];
  if (!page) {
    return (
      <div className="flex-1 empty-state">
        <div className="empty-state-icon">
          <FileText className="w-5 h-5" />
        </div>
        <div className="empty-state-title">页面不存在</div>
        <div className="empty-state-desc">该页面可能已被删除或尚未生成，请返回目录重新选择。</div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto p-6 scrollbar-thin">
      <article className="max-w-3xl mx-auto">
        <h1 className="text-2xl font-bold text-text-primary mb-2">{page.title}</h1>
        {page.importance > 0 && (
          <div className="flex items-center gap-2 mb-4">
            <span className="text-xs px-2 py-0.5 bg-accent/20 text-accent rounded-full">
              重要度：{Math.round(Math.min(page.importance, 1) * 100)}%
            </span>
            {page.file_paths.length > 0 && (
              <span className="text-xs text-text-muted">
                {page.file_paths.length} 个文件
              </span>
            )}
          </div>
        )}
        <div className="chat-prose">
          <MarkdownRenderer content={page.content} onLinkClick={onLinkClick} />
        </div>
      </article>
    </div>
  );
}
