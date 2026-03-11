import { Component, type ReactNode } from 'react';
import { AlertTriangle } from 'lucide-react';
import { Button } from './button';

interface Props { children: ReactNode; }
interface State { hasError: boolean; }

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError() { return { hasError: true }; }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex flex-col items-center justify-center h-full gap-4 p-8">
          <AlertTriangle className="h-10 w-10 text-[var(--color-error)]" />
          <p className="text-lg font-medium text-text-primary">页面出现错误</p>
          <p className="text-sm text-text-muted">请尝试刷新页面</p>
          <Button onClick={() => this.setState({ hasError: false })}>重试</Button>
        </div>
      );
    }
    return this.props.children;
  }
}
