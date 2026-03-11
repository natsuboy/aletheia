import { useState, useRef, useCallback, useEffect } from 'react';
import { Upload, FileCheck, X } from 'lucide-react';
import { toast } from 'sonner';

interface UploadZoneProps {
  onSubmit: (file: File, projectName: string) => Promise<void>;
  loading?: boolean;
  uploadPercent?: number;
}

const MAX_FILE_SIZE = 500 * 1024 * 1024;

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function stemName(filename: string): string {
  return filename.replace(/\.scip$/i, '');
}

export function UploadZone({ onSubmit, loading = false, uploadPercent }: UploadZoneProps) {
  const [file, setFile] = useState<File | null>(null);
  const [projectName, setProjectName] = useState('');
  const [dragOver, setDragOver] = useState(false);
  const [nameFocused, setNameFocused] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const nameRef = useRef<HTMLInputElement>(null);

  const handleFile = useCallback((f: File) => {
    if (!/\.scip$/i.test(f.name)) { toast.error('只支持 .scip 文件'); return; }
    if (f.size > MAX_FILE_SIZE) { toast.error(`文件过大 (${formatFileSize(f.size)})，上限 500MB`); return; }
    setFile(f);
    setProjectName((prev) => prev || stemName(f.name));
  }, []);

  // 文件选中后自动 focus 项目名输入框
  useEffect(() => {
    if (file) nameRef.current?.focus();
  }, [file]);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const f = e.dataTransfer.files[0];
    if (f) handleFile(f);
  }, [handleFile]);

  const handleClear = (e: React.MouseEvent) => {
    e.stopPropagation();
    setFile(null);
    setProjectName('');
    if (inputRef.current) inputRef.current.value = '';
  };

  const handleSubmit = async () => {
    if (!file || !projectName.trim() || loading) return;
    await onSubmit(file, projectName.trim());
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') handleSubmit();
  };

  return (
    <div className="space-y-4">
      {/* Drop zone */}
      <div
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={(e) => { if (!e.currentTarget.contains(e.relatedTarget as Node)) setDragOver(false); }}
        onDrop={handleDrop}
        onClick={() => !file && !loading && inputRef.current?.click()}
        role="button"
        tabIndex={0}
        aria-label="拖拽或点击上传 SCIP 文件"
        onKeyDown={(e) => { if ((e.key === 'Enter' || e.key === ' ') && !file) inputRef.current?.click(); }}
        className={`relative flex flex-col items-center justify-center gap-3 py-14 rounded-xl border-2 border-dashed transition-all duration-200 select-none ${
          loading
            ? 'border-border-subtle bg-elevated cursor-default'
            : dragOver
              ? 'border-accent bg-accent/5 scale-[1.01] cursor-copy'
              : file
                ? 'border-accent-secondary/40 bg-elevated cursor-default'
                : 'border-border-default hover:border-accent/60 bg-elevated cursor-pointer'
        }`}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".scip"
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) handleFile(f);
            e.target.value = '';
          }}
        />

        {/* Clear button */}
        {file && !loading && (
          <button
            onClick={handleClear}
            className="absolute top-3 right-3 p-1 rounded-md text-text-muted hover:text-text-primary hover:bg-hover transition-colors"
            aria-label="移除文件"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        )}

        {/* Icon */}
        {file ? (
          <FileCheck className="w-8 h-8 text-accent-secondary" />
        ) : (
          <Upload className={`w-8 h-8 transition-colors ${dragOver ? 'text-accent' : 'text-text-muted'}`} />
        )}

        {/* Copy */}
        {file ? (
          <div className="text-center space-y-0.5">
            <p className="text-sm font-medium text-text-primary truncate max-w-[280px]">{file.name}</p>
            <p className="text-xs text-text-muted">{formatFileSize(file.size)}</p>
          </div>
        ) : (
          <div className="text-center space-y-1">
            <p className="text-sm text-text-secondary">拖拽 `.scip` 文件到此处</p>
            <p className="text-xs text-text-muted">或点击选择文件</p>
          </div>
        )}

        {/* 上传进度占位：仅当服务端未返回百分比时显示 */}
        {loading && uploadPercent == null && (
          <p className="text-xs font-mono text-text-muted">上传中...</p>
        )}
      </div>

      {/* Project name — ghost style */}
      <div className="relative">
        <input
          ref={nameRef}
          type="text"
          placeholder="项目名称"
          value={projectName}
          onChange={(e) => setProjectName(e.target.value)}
          onKeyDown={handleKeyDown}
          onFocus={() => setNameFocused(true)}
          onBlur={() => setNameFocused(false)}
          disabled={loading}
          className="w-full bg-transparent border-0 border-b text-base text-text-primary placeholder:text-text-muted focus:outline-none pb-1.5 pr-28 disabled:opacity-50 transition-colors"
          style={{ borderColor: nameFocused ? 'var(--color-accent)' : 'var(--color-border-default)' }}
        />
        {/* Submit button */}
        <button
          onClick={handleSubmit}
          disabled={loading || !file || !projectName.trim()}
          className="absolute right-0 bottom-1.5 flex items-center gap-1.5 px-3 py-1 text-xs font-medium text-text-secondary hover:text-text-primary disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          {loading ? (
            <span className="font-mono text-accent">
              {uploadPercent != null ? `${uploadPercent}%` : '...'}
            </span>
          ) : (
            <>
              继续
              <kbd className="px-1 py-0.5 text-xs bg-elevated border border-border-default rounded font-mono">↵</kbd>
            </>
          )}
        </button>
      </div>
    </div>
  );
}
