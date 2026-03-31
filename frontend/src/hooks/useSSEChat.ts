import { useCallback, useEffect, useRef } from 'react';

interface SSEMessage {
  text?: string;
  tool?: string;
  tool_result?: {
    tool_name: string;
    data: any;
  };
  visual?: string;
}

interface UseSSEChatOptions {
  serverToken: string;
  onMessage?: (msg: SSEMessage) => void;
  onError?: (err: Error) => void;
  onConnected?: () => void;
}

/**
 * Hook to manage SSE connection to /chat endpoint
 * Uses fetch + ReadableStream (supports custom headers for auth)
 * Automatically reconnects on error with 5s backoff
 */
export function useSSEChat(options: UseSSEChatOptions) {
  const { serverToken, onMessage, onError, onConnected } = options;
  const readerRef = useRef<ReadableStreamDefaultReader<Uint8Array> | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const mountedRef = useRef(true);
  const callbacksRef = useRef({ onMessage, onError, onConnected });

  const connect = useCallback(() => {
    if (readerRef.current) {
      return;
    }

    try {
      const url = new URL('/chat', window.location.origin);

      fetch(url.toString(), {
        headers: { 'X-Server-Token': serverToken }
      })
        .then(res => {
          if (!mountedRef.current) return;

          if (!res.ok) {
            const error = new Error(`HTTP ${res.status}`);
            callbacksRef.current.onError?.(error);
            return;
          }

          console.log('Connected to SSE /chat endpoint');
          callbacksRef.current.onConnected?.();

          // Stream the response
          const reader = res.body?.getReader();
          if (!reader) {
            const error = new Error('No response body');
            callbacksRef.current.onError?.(error);
            return;
          }

          readerRef.current = reader;
          const decoder = new TextDecoder();
          let buffer = '';

          const read = () => {
            reader.read().then(({ done, value }) => {
              if (!mountedRef.current) return;

              if (done) {
                callbacksRef.current.onError?.(new Error('Stream closed'));
                readerRef.current = null;
                return;
              }

              buffer += decoder.decode(value, { stream: true });
              const lines = buffer.split('\n');
              buffer = lines.pop() || '';

              for (const line of lines) {
                const trimmed = line.trim();
                if (trimmed.startsWith('data: ')) {
                  try {
                    const data = JSON.parse(trimmed.slice(6));
                    callbacksRef.current.onMessage?.(data);
                  } catch (parseErr) {
                    // Skip unparseable messages
                  }
                }
              }

              read();
            }).catch((err) => {
              if (!mountedRef.current) return;
              console.warn('SSE read error, reconnecting in 5s...');
              readerRef.current = null;
              callbacksRef.current.onError?.(err);
              if (mountedRef.current) {
                reconnectTimeoutRef.current = setTimeout(connect, 5000);
              }
            });
          };

          read();
        })
        .catch(err => {
          if (!mountedRef.current) return;
          console.warn('SSE connection error, reconnecting in 5s...');
          readerRef.current = null;
          callbacksRef.current.onError?.(err);
          if (mountedRef.current) {
            reconnectTimeoutRef.current = setTimeout(connect, 5000);
          }
        });
    } catch (err) {
      if (!mountedRef.current) return;
      const error = err instanceof Error ? err : new Error(String(err));
      callbacksRef.current.onError?.(error);
    }
  }, [serverToken]);

  const disconnect = useCallback(() => {
    if (readerRef.current) {
      readerRef.current.cancel();
      readerRef.current = null;
    }
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
  }, []);

  // Update callback refs whenever callbacks change
  useEffect(() => {
    callbacksRef.current = { onMessage, onError, onConnected };
  }, [onMessage, onError, onConnected]);

  useEffect(() => {
    connect();
    return () => {
      mountedRef.current = false;
      disconnect();
    };
  }, [connect, disconnect]);

  return { isConnected: !!readerRef.current, disconnect };
}
