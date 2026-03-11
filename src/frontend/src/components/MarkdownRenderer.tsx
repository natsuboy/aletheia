import { useMemo, useCallback, useState, lazy, Suspense } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Copy, Check } from 'lucide-react';

const MermaidDiagram = lazy(async () => {
  const mod = await import('./MermaidDiagram');
  return { default: mod.MermaidDiagram };
});
const CodeHighlighter = lazy(async () => {
  const mod = await import('./CodeHighlighter');
  return { default: mod.CodeHighlighter };
});

interface MarkdownRendererProps {
  content: string;
  onLinkClick?: (href: string) => void;
}

export function MarkdownRenderer({ content, onLinkClick }: MarkdownRendererProps) {
  const [copiedBlock, setCopiedBlock] = useState<string | null>(null);
  // Transform grounding links: [[path/to/file.ts:10-20]] → clickable code refs
  // and node refs: [[Class:MyClass]] → clickable node refs
  // Protect code blocks from [[]] replacement by splitting on ```
  const processed = useMemo(() => {
    const segments = content.split(/(```[\s\S]*?```)/g);
    return segments
      .map((seg, i) => {
        // Odd indices are code blocks — leave untouched
        if (i % 2 === 1) return seg;
        return seg.replace(/\[\[([^\]]+?)\]\]/g, (_, inner: string) => {
          const trimmed = inner.trim();
          if (/^(Class|Function|Method|Interface|File|Folder|Variable|Enum|Type|CodeElement):/.test(trimmed)) {
            return `[${trimmed}](node-ref:${encodeURIComponent(trimmed)})`;
          }
          return `[\`${trimmed}\`](code-ref:${encodeURIComponent(trimmed)})`;
        });
      })
      .join('');
  }, [content]);

  const handleClick = useCallback((href: string) => {
    if (href.startsWith('code-ref:') || href.startsWith('node-ref:')) {
      onLinkClick?.(href);
    }
  }, [onLinkClick]);

  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        a: ({ href, children }) => {
          if (href?.startsWith('code-ref:')) {
            return (
              <button
                onClick={() => handleClick(href)}
                className="chip chip-accent cursor-pointer font-mono"
              >
                {children}
              </button>
            );
          }
          if (href?.startsWith('node-ref:')) {
            return (
              <button
                onClick={() => handleClick(href)}
                className="chip chip-secondary cursor-pointer font-mono"
              >
                {children}
              </button>
            );
          }
          return (
            <a href={href} target="_blank" rel="noopener noreferrer" className="text-accent hover:underline">
              {children}
            </a>
          );
        },
        code: ({ className, children, ...props }) => {
          const isInline = !className;
          if (isInline) {
            return <code className="px-1.5 py-0.5 bg-elevated rounded text-[13px] font-mono text-text-primary" {...props}>{children}</code>;
          }
          const lang = className?.replace('language-', '') || '';
          const codeString = String(children).replace(/\n$/, '');
          if (lang === 'mermaid') {
            return (
              <Suspense fallback={<div className="my-3 rounded-lg border border-border-subtle bg-elevated/40 p-3 text-xs text-text-muted">图表加载中...</div>}>
                <MermaidDiagram code={codeString} />
              </Suspense>
            );
          }
          const blockId = `${lang}-${codeString.slice(0, 32)}`;
          const isCopied = copiedBlock === blockId;
          return (
            <div className="my-3 rounded-lg overflow-hidden border border-border-subtle">
              <div className="flex items-center justify-between px-3 py-1 bg-elevated border-b border-border-subtle">
                {lang ? <span className="section-kicker">{lang}</span> : <span />}
                <button
                  onClick={() => {
                    navigator.clipboard.writeText(codeString).then(() => {
                      setCopiedBlock(blockId);
                      setTimeout(() => setCopiedBlock(prev => prev === blockId ? null : prev), 1500);
                    }).catch(() => {});
                  }}
                  className="p-0.5 text-text-muted hover:text-text-primary transition-colors cursor-pointer"
                  title="复制代码"
                >
                  {isCopied ? <Check className="w-3.5 h-3.5 text-accent-secondary" /> : <Copy className="w-3.5 h-3.5" />}
                </button>
              </div>
              <Suspense
                fallback={(
                  <pre className="m-0 bg-void px-3 py-3 text-[13px] text-text-secondary overflow-x-auto">
                    <code>{codeString}</code>
                  </pre>
                )}
              >
                <CodeHighlighter code={codeString} language={lang || 'text'} />
              </Suspense>
            </div>
          );
        },
        p: ({ children }) => <p className="mb-3 last:mb-0 text-sm leading-relaxed">{children}</p>,
        ul: ({ children }) => <ul className="mb-3 pl-4 list-disc space-y-1 text-sm">{children}</ul>,
        ol: ({ children }) => <ol className="mb-3 pl-4 list-decimal space-y-1 text-sm">{children}</ol>,
        li: ({ children }) => <li className="text-text-secondary">{children}</li>,
        h1: ({ children }) => <h1 className="text-base font-semibold mb-2 mt-4">{children}</h1>,
        h2: ({ children }) => <h2 className="text-sm font-semibold mb-2 mt-3">{children}</h2>,
        h3: ({ children }) => <h3 className="text-sm font-medium mb-1 mt-2">{children}</h3>,
        blockquote: ({ children }) => <blockquote className="border-l-2 border-accent/40 pl-3 text-text-secondary italic">{children}</blockquote>,
      }}
    >
      {processed}
    </ReactMarkdown>
  );
}
