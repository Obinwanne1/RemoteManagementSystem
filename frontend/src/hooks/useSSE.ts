import { useEffect, useRef, useCallback } from 'react';

interface SSEOptions {
  onMessage?: (type: string, data: unknown) => void;
  onConnect?: () => void;
  onError?: () => void;
  enabled?: boolean;
}

export function useSSE(token: string | null, options: SSEOptions = {}) {
  const { onMessage, onConnect, onError, enabled = true } = options;
  const esRef = useRef<EventSource | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const connect = useCallback(() => {
    if (!token || !enabled) return;

    const url = `/api/events/stream?token=${encodeURIComponent(token)}`;
    const es = new EventSource(url);
    esRef.current = es;

    es.onmessage = (e) => {
      try {
        const payload = JSON.parse(e.data) as { type: string; data: unknown };
        if (payload.type === 'connected') {
          onConnect?.();
        } else {
          onMessage?.(payload.type, payload.data);
        }
      } catch {
        // malformed SSE frame — ignore
      }
    };

    es.onerror = () => {
      onError?.();
      es.close();
      esRef.current = null;
      // Reconnect after 5s — EventSource normally handles this automatically
      // but we close manually on error so we need to re-open
      reconnectTimer.current = setTimeout(connect, 5_000);
    };
  }, [token, enabled, onMessage, onConnect, onError]);

  useEffect(() => {
    connect();
    return () => {
      esRef.current?.close();
      esRef.current = null;
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
    };
  }, [connect]);
}
