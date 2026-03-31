// src/hooks/useWatcherAlerts.ts
//
// Persistent SSE connection to /watcher/alerts/stream.
// Reconnects automatically on drop (5s delay).
// Uses fetch + ReadableStream because EventSource does not support custom headers.

import { useEffect, useRef, useCallback } from 'react';
import { WatcherAlert } from '../types/terminal';

export function useWatcherAlerts(
  walletAddress: string | null,
  onAlert: (alert: WatcherAlert) => void,
) {
  const onAlertRef = useRef(onAlert);
  onAlertRef.current = onAlert;

  const connect = useCallback(async (wallet: string, signal: AbortSignal): Promise<void> => {
    try {
      const response = await fetch('/watcher/alerts/stream', {
        headers: { 'X-Wallet-Address': wallet },
        signal,
      });
      if (!response.ok || !response.body) return;

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() ?? '';
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const alert = JSON.parse(line.slice(6)) as WatcherAlert;
              onAlertRef.current(alert);
            } catch {
              // malformed event — ignore
            }
          }
        }
      }
    } catch (err: unknown) {
      if (err instanceof Error && err.name === 'AbortError') return;
      // Unexpected disconnect — retry after delay
      await new Promise<void>(r => setTimeout(r, 5000));
      if (!signal.aborted) {
        connect(wallet, signal);
      }
    }
  }, []);

  useEffect(() => {
    if (!walletAddress) return;
    const ctrl = new AbortController();
    connect(walletAddress, ctrl.signal);
    return () => ctrl.abort();
  }, [walletAddress, connect]);
}
