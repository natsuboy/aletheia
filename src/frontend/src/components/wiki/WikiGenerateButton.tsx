import { Loader2, BookOpen, RefreshCw } from 'lucide-react';
import { useWikiStore } from '@/stores/wikiStore';
import { useProjectStore } from '@/stores/projectStore';

interface WikiGenerateButtonProps {
  variant?: 'generate' | 'regenerate';
}

export function WikiGenerateButton({ variant = 'generate' }: WikiGenerateButtonProps) {
  const { currentProject } = useProjectStore();
  const { isGenerating, generateWiki, regenerateWiki } = useWikiStore();

  const handleClick = () => {
    if (!currentProject) return;
    if (variant === 'regenerate') {
      regenerateWiki(currentProject.name);
    } else {
      generateWiki(currentProject.name);
    }
  };

  const isRegen = variant === 'regenerate';
  const Icon = isRegen ? RefreshCw : BookOpen;
  const label = isRegen ? '重新生成 Wiki' : '生成 Wiki';

  return (
    <button
      onClick={handleClick}
      disabled={isGenerating || !currentProject}
      className="flex items-center gap-1.5 px-3 py-1.5 bg-accent text-white text-xs font-medium rounded-lg transition-all hover:bg-accent-dim disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
    >
      {isGenerating ? (
        <>
          <Loader2 className="w-3.5 h-3.5 animate-spin" />
          <span>生成中...</span>
        </>
      ) : (
        <>
          <Icon className="w-3.5 h-3.5" />
          <span>{label}</span>
        </>
      )}
    </button>
  );
}
