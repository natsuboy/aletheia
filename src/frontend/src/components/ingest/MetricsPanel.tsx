import { useRef, useEffect, useState } from 'react';
import type { ParsedMetrics } from '@/stores/ingestionStore';


interface MetricsPanelProps {
  metrics: ParsedMetrics;
}

function formatNumber(n: number | null): string {
  if (n == null) return '—';
  return new Intl.NumberFormat().format(n);
}

function InlineMetric({ label, value }: { label: string; value: number | null }) {
  const prevRef = useRef(value);
  const [flash, setFlash] = useState(false);

  useEffect(() => {
    if (value !== prevRef.current && value != null && prevRef.current != null) {
      setFlash(true);
      const t = setTimeout(() => setFlash(false), 300);
      prevRef.current = value;
      return () => clearTimeout(t);
    }
    prevRef.current = value;
  }, [value]);

  return (
    <span className="flex items-baseline gap-1.5">
      <span
        className={`font-mono text-sm transition-colors duration-300 ${
          flash ? 'text-accent-secondary' : 'text-text-primary'
        }`}
        style={{ fontVariantNumeric: 'tabular-nums' }}
      >
        {value == null ? (
          <span className="inline-block w-8 h-3 bg-hover rounded animate-pulse" />
        ) : (
          formatNumber(value)
        )}
      </span>
      <span className="section-kicker">{label}</span>
    </span>
  );
}

export function MetricsPanel({ metrics }: MetricsPanelProps) {
  const nodesDisplay = metrics.nodesTotal ?? metrics.nodesInserted;
  const edgesDisplay = metrics.edgesTotal ?? metrics.edgesInserted;

  return (
    <div className="flex items-center gap-5">
      <InlineMetric label="节点" value={nodesDisplay} />
      <span className="text-border-default" aria-hidden="true">·</span>
      <InlineMetric label="边" value={edgesDisplay} />
      <span className="text-border-default" aria-hidden="true">·</span>
      <InlineMetric label="文件" value={metrics.documentsCount} />
    </div>
  );
}
