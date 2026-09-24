import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react';

interface ToastItem {
  id: number;
  message: string;
  kind: 'error' | 'success';
}

interface ToastContextValue {
  showError: (message: string) => void;
  showSuccess: (message: string) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

// The QueryClient in main.tsx is constructed at module scope, before React (and
// thus this provider) mounts, so its QueryCache/MutationCache onError callbacks
// can't call useToast() directly. This module-level bridge lets them reach the
// mounted provider without restructuring QueryClient construction into a component.
let toastBridge: ((message: string, kind: ToastItem['kind']) => void) | null = null;

/** Safe to call before ToastProvider has mounted (e.g. a query that fails during
 * initial render) — silently no-ops rather than throwing, since this is a
 * best-effort UX affordance, not a critical path. */
export function notifyError(message: string) {
  toastBridge?.(message, 'error');
}

/**
 * Minimal, dependency-free toast system — used as the global fallback for
 * TanStack Query's QueryCache/MutationCache onError (see main.tsx), so a
 * failed fetch/mutation is never silently invisible to the user even on
 * pages that don't check `isError` themselves. See
 * audits/error_handling_audit.md Finding A10.
 */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const nextId = useRef(0);

  const dismiss = useCallback((id: number) => {
    setItems((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const push = useCallback(
    (message: string, kind: ToastItem['kind']) => {
      const id = nextId.current++;
      setItems((prev) => [...prev, { id, message, kind }]);
      setTimeout(() => dismiss(id), 6000);
    },
    [dismiss],
  );

  const value: ToastContextValue = {
    showError: (message: string) => push(message, 'error'),
    showSuccess: (message: string) => push(message, 'success'),
  };

  useEffect(() => {
    toastBridge = push;
    return () => {
      toastBridge = null;
    };
  }, [push]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="pointer-events-none fixed bottom-4 right-4 z-50 flex flex-col gap-2">
        {items.map((t) => (
          <div
            key={t.id}
            role="alert"
            className={`pointer-events-auto max-w-sm rounded-md px-4 py-3 text-sm shadow-lg ${
              t.kind === 'error'
                ? 'bg-red-50 text-red-800 ring-1 ring-red-200'
                : 'bg-emerald-50 text-emerald-800 ring-1 ring-emerald-200'
            }`}
          >
            <div className="flex items-start justify-between gap-3">
              <span>{t.message}</span>
              <button
                type="button"
                onClick={() => dismiss(t.id)}
                className="shrink-0 text-xs opacity-60 hover:opacity-100"
                aria-label="Dismiss"
              >
                ✕
              </button>
            </div>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    throw new Error('useToast() must be used inside <ToastProvider>');
  }
  return ctx;
}
