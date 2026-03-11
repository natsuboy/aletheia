import { ReactNode, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useProjectStore, useGraphStore } from '@/stores';
import { Header } from './Header';

interface MainLayoutProps {
  children: ReactNode;
}

export function MainLayout({ children }: MainLayoutProps) {
  const navigate = useNavigate();
  const location = useLocation();
  const { currentProject } = useProjectStore();
  const { selectNode, selectedNode } = useGraphStore();

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Escape: 关闭 NodeDetailPanel / 取消节点选择
      if (e.key === 'Escape' && selectedNode) {
        e.preventDefault();
        selectNode(null);
        return;
      }

      if (!(e.metaKey || e.ctrlKey)) return;
      if (e.key === '1') { e.preventDefault(); navigate('/'); }
      if (e.key === '2' && currentProject) { e.preventDefault(); navigate(`/project/${currentProject.id}/graph`); }
      if (e.key === '3' && currentProject) { e.preventDefault(); navigate(`/project/${currentProject.id}/chat`); }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [navigate, currentProject, selectedNode, selectNode]);

  return (
    <div className="min-h-screen bg-void flex flex-col">
      <Header />
      <main key={location.pathname} className="flex-1 overflow-hidden animate-fade-in">
        {children}
      </main>
    </div>
  );
}
