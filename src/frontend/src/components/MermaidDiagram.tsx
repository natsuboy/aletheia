import { useEffect, useRef, useState } from 'react';
import mermaid from 'mermaid';

mermaid.initialize({
  startOnLoad: false,
  theme: 'base',
  themeVariables: {
    darkMode: false,
    background: '#F6F8FB',
    primaryColor: '#E7EEF9',
    primaryTextColor: '#0F172A',
    lineColor: '#94A3B8',
    secondaryColor: '#EEF2F7',
    tertiaryColor: '#FFFFFF',
  },
});

let idCounter = 0;

interface MermaidDiagramProps {
  code: string;
}

export function MermaidDiagram({ code }: MermaidDiagramProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);
  const idRef = useRef(`mermaid-${++idCounter}`);

  useEffect(() => {
    if (!containerRef.current) return;
    let cancelled = false;

    const render = async () => {
      try {
        const { svg } = await mermaid.render(idRef.current, code.trim());
        if (!cancelled && containerRef.current) {
          containerRef.current.innerHTML = svg;
          setError(null);
        }
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : 'Mermaid 语法无效');
        }
      }
    };

    render();
    return () => { cancelled = true; };
  }, [code]);

  if (error) {
    return (
      <div className="my-3 rounded-lg overflow-hidden border border-border-subtle">
        <div className="px-3 py-1 bg-elevated border-b border-border-subtle">
          <span className="chip chip-error">Mermaid 渲染失败</span>
        </div>
        <pre className="p-3 bg-void overflow-x-auto text-[13px] leading-relaxed text-text-secondary">
          <code>{code}</code>
        </pre>
      </div>
    );
  }

  return (
    <div className="my-3 rounded-lg overflow-hidden border border-border-subtle bg-void p-4">
      <div ref={containerRef} className="flex justify-center [&>svg]:max-w-full" />
    </div>
  );
}
