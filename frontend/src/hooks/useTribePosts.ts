// src/hooks/useTribePosts.ts
//
// SSE connection to /tribe-posts/{tribeId}/stream.
// No auth header required — board stream is public.
// Reconnects automatically on drop (5s delay).

import { useEffect, useRef, useCallback } from 'react';
import { TribePost } from '../types/terminal';

export type TribePostEvent =
  | { type: 'snapshot'; posts: TribePost[] }
  | { type: 'new_post'; post: TribePost }
  | { type: 'post_deleted'; post_id: string };

export function useTribePosts(
  tribeId: number | null,
  onEvent: (event: TribePostEvent) => void,
): void {
  const onEventRef = useRef(onEvent);
  onEventRef.current = onEvent;

  const connect = useCallback(async (id: number, signal: AbortSignal): Promise<void> => {
    try {
      const response = await fetch(`/tribe-posts/${id}/stream`, { signal });
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
              const event = JSON.parse(line.slice(6)) as TribePostEvent;
              onEventRef.current(event);
            } catch {
              // malformed event — ignore
            }
          }
        }
      }
    } catch (err: unknown) {
      if (err instanceof Error && err.name === 'AbortError') return;
      await new Promise<void>(r => setTimeout(r, 5000));
      if (!signal.aborted) {
        connect(id, signal);
      }
    }
  }, []);

  useEffect(() => {
    if (!tribeId) return;
    const ctrl = new AbortController();
    connect(tribeId, ctrl.signal);
    return () => ctrl.abort();
  }, [tribeId, connect]);
}
