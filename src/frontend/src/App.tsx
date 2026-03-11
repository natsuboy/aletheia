import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from '@/components/ui/sonner';
import { ErrorBoundary } from '@/components/ui/ErrorBoundary';
import { ProjectSelector } from '@/components/ProjectSelector';
import { ExplorerLayout } from '@/components/layout/ExplorerLayout';
import { IngestionDashboard } from '@/components/ingest/IngestionDashboard';
import { ProjectWorkspace } from '@/components/workspace/ProjectWorkspace';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<ErrorBoundary><ProjectSelector /></ErrorBoundary>} />
        <Route path="/project/:projectId/loading" element={<ErrorBoundary><IngestionDashboard /></ErrorBoundary>} />
        <Route path="/project/:projectId" element={<ErrorBoundary><ProjectWorkspace /></ErrorBoundary>} />
        <Route path="/project/:projectId/legacy" element={<ErrorBoundary><ExplorerLayout /></ErrorBoundary>} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      <Toaster />
    </BrowserRouter>
  );
}
