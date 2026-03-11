import { Toaster as Sonner } from 'sonner';

export function Toaster() {
  return (
    <Sonner
      theme="dark"
      toastOptions={{
        style: {
          background: 'var(--color-elevated)',
          border: '1px solid var(--color-border-default)',
          color: 'var(--color-text-primary)',
        },
      }}
    />
  );
}
