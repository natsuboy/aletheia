import { X, FileCode } from 'lucide-react';
import { CodeHighlighter } from '@/components/CodeHighlighter';

interface CodePreviewProps {
  content: string;
  language: string;
  startLine: number;
  endLine: number;
  highlightLines?: number[];
  filePath?: string;
  onClose?: () => void;
}

export function CodePreview({
  content, language, startLine, endLine,
  highlightLines = [], filePath, onClose,
}: CodePreviewProps) {
  const highlightSet = new Set(highlightLines);

  return (
    <div className="rounded-lg border border-border-default overflow-hidden bg-deep">
      {/* 顶部信息栏 */}
      <div className="flex items-center gap-2 px-3 py-1.5 bg-surface border-b border-border-default text-xs">
        <FileCode className="h-3.5 w-3.5 text-text-muted" />
        {filePath && (
          <span className="text-text-secondary truncate">{filePath}</span>
        )}
        <span className="text-text-muted px-1.5 py-0.5 rounded bg-elevated">{language}</span>
        <span className="text-text-muted ml-auto">L{startLine}-{endLine}</span>
        {onClose && (
          <button onClick={onClose} className="text-text-muted hover:text-text-primary cursor-pointer">
            <X className="h-3.5 w-3.5" />
          </button>
        )}
      </div>

      {/* 代码区域 */}
      <div className="max-h-[400px] overflow-auto scrollbar-thin">
        <CodeHighlighter
          code={content}
          language={language}
          showLineNumbers
          startingLineNumber={startLine}
          wrapLines
          lineProps={(lineNumber: number) => {
            const isHighlighted = highlightSet.has(lineNumber);
            return {
              style: {
                backgroundColor: isHighlighted ? 'rgba(124, 58, 237, 0.12)' : undefined,
                borderLeft: isHighlighted ? '2px solid var(--color-accent)' : '2px solid transparent',
                display: 'block',
                paddingLeft: '0.5em',
              },
            };
          }}
          customStyle={{
            margin: 0,
            padding: '0.5em 0',
            background: 'transparent',
            fontSize: '13px',
          }}
        >
        </CodeHighlighter>
      </div>
    </div>
  );
}
