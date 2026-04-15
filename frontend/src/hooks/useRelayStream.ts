// src/hooks/useRelayStream.ts
// Streaming hook for the open-channel /companion/relay endpoint.

import { useCallback } from 'react';

export interface RelayStreamPayload {
  message: string;
  history: Array<{ role: string; content: string }>;
  owner_address?: string;
  character_name?: string;
  tenant?: string;
}

export interface RelayStreamCallbacks {
  onTextChunk: (text: string) => void;
  onDone: () => void;
  onError: (err: Error) => void;
}

/**
 * Hook for streaming relay chat via POST /companion/relay.
 * Text-only SSE — no tool_result events.
 */
export function useRelayStream() {
  const sendMessage = useCallback(
    async (payload: RelayStreamPayload, callbacks: RelayStreamCallbacks): Promise<void> => {
      const { onTextChunk, onDone, onError } = callbacks;

      let response: Response;
      try {
        response = await fetch('/companion/relay', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
      } catch (err) {
        onError(err instanceof Error ? err : new Error(String(err)));
        return;
      }

      if (!response.ok) {
        onError(new Error(`HTTP ${response.status}`));
        return;
      }

      const reader = response.body?.getReader();
      if (!reader) {
        onError(new Error('No response body'));
        return;
      }

      const decoder = new TextDecoder();
      let buffer = '';

      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() ?? '';

          for (const line of lines) {
            const trimmed = line.trim();
            if (!trimmed.startsWith('data: ')) continue;

            let data: Record<string, unknown>;
            try {
              data = JSON.parse(trimmed.slice(6));
            } catch {
              continue;
            }

            if (data.text !== undefined) {
              onTextChunk(data.text as string);
            } else if (data.done) {
              onDone();
              return;
            } else if (data.error) {
              onError(new Error(data.error as string));
              return;
            }
          }
        }
      } catch (err) {
        onError(err instanceof Error ? err : new Error(String(err)));
        return;
      }

      onDone();
    },
    []
  );

  return { sendMessage };
}
