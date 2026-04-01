// src/hooks/useCompanionStream.ts

import { useCallback } from 'react';
import { ToolType, ToolOutputData } from '../types/terminal';

export interface CompanionStreamPayload {
  assembly_id: string;
  message: string;
  history: Array<{ role: string; content: string }>;
  owner_address?: string;
  character_name?: string;
  item_id?: string;
  assembly_name?: string;
  assembly_type?: string;
  assembly_state?: string;
  system_name?: string;
  system_id?: number;
  debug?: boolean;
  disabled_tools?: string[];
  tenant?: string;
}

export interface CompanionStreamCallbacks {
  onTextChunk: (text: string) => void;
  onToolResult: (toolName: ToolType, data: ToolOutputData) => void;
  onDone: () => void;
  onError: (err: Error) => void;
}

/**
 * Hook for streaming companion chat via POST /companion/stream.
 *
 * Parses SSE events and routes them:
 *   {text}        → onTextChunk   (accumulate for final chat message)
 *   {tool_result} → onToolResult  (update visual panel immediately)
 *   {done}        → onDone
 *   {error}       → onError
 */
export function useCompanionStream() {
  const sendMessage = useCallback(
    async (payload: CompanionStreamPayload, callbacks: CompanionStreamCallbacks): Promise<void> => {
      const { onTextChunk, onToolResult, onDone, onError } = callbacks;

      let response: Response;
      try {
        response = await fetch('/companion/stream', {
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
            } else if (data.tool_result) {
              const tr = data.tool_result as { toolName: ToolType; data: ToolOutputData };
              onToolResult(tr.toolName, tr.data);
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
