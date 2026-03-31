import { useState, useCallback } from 'react';

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: number;
  toolUse?: {
    name: string;
    input: Record<string, unknown>;
  };
}

export interface UseStructureChatReturn {
  messages: ChatMessage[];
  isLoading: boolean;
  error: string | null;
  sendMessage: (assemblyId: string, userMessage: string, serverToken: string) => Promise<void>;
}

/**
 * Custom React hook for managing structure chat with SSE streaming
 * Handles real-time AI responses from the backend /structure-chat endpoint
 */
export function useStructureChat(): UseStructureChatReturn {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const sendMessage = useCallback(
    async (assemblyId: string, userMessage: string, serverToken: string): Promise<void> => {
      try {
        setError(null);
        setIsLoading(true);

        // Add user message to chat history
        const userMsgId = `msg-${Date.now()}-user`;
        const userMsg: ChatMessage = {
          id: userMsgId,
          role: 'user',
          content: userMessage,
          timestamp: Date.now(),
        };
        setMessages((prev) => [...prev, userMsg]);

        // Prepare request payload
        const requestPayload = {
          assembly_id: assemblyId,
          message: userMessage,
          history: messages.map((msg) => ({
            role: msg.role,
            content: msg.content,
          })),
        };

        // Initiate SSE stream
        const response = await fetch('/structure-chat', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${serverToken}`,
          },
          body: JSON.stringify(requestPayload),
        });

        if (!response.ok) {
          const errorText = await response.text();
          throw new Error(`HTTP ${response.status}: ${errorText}`);
        }

        // Handle SSE streaming
        if (!response.body) {
          throw new Error('No response body for SSE stream');
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let assistantContent = '';
        const assistantMsgId = `msg-${Date.now()}-assistant`;
        let assistantMsgAdded = false;

        try {
          while (true) {
            const { done, value } = await reader.read();

            if (done) {
              break;
            }

            const chunk = decoder.decode(value, { stream: true });
            const lines = chunk.split('\n');

            for (const line of lines) {
              if (line.startsWith('data: ')) {
                const dataStr = line.slice(6).trim();

                if (!dataStr) {
                  continue;
                }

                try {
                  const data = JSON.parse(dataStr);

                  // Parse streaming content
                  if (data.content) {
                    assistantContent += data.content;

                    // Add or update assistant message in state
                    if (!assistantMsgAdded) {
                      const assistantMsg: ChatMessage = {
                        id: assistantMsgId,
                        role: 'assistant',
                        content: assistantContent,
                        timestamp: Date.now(),
                      };
                      setMessages((prev) => [...prev, assistantMsg]);
                      assistantMsgAdded = true;
                    } else {
                      setMessages((prev) =>
                        prev.map((msg) =>
                          msg.id === assistantMsgId
                            ? { ...msg, content: assistantContent }
                            : msg
                        )
                      );
                    }
                  }

                  // Handle tool use
                  if (data.toolUse) {
                    setMessages((prev) =>
                      prev.map((msg) =>
                        msg.id === assistantMsgId
                          ? {
                              ...msg,
                              toolUse: {
                                name: data.toolUse.name,
                                input: data.toolUse.input,
                              },
                            }
                          : msg
                      )
                    );
                  }

                  // Handle completion
                  if (data.done === true) {
                    break;
                  }
                } catch (parseErr) {
                  console.error('Failed to parse SSE data:', dataStr, parseErr);
                }
              }
            }
          }
        } finally {
          reader.releaseLock();
        }

        setIsLoading(false);
      } catch (err) {
        setIsLoading(false);
        const errorMessage = err instanceof Error ? err.message : 'Unknown error occurred';
        setError(errorMessage);
        console.error('Chat error:', errorMessage);
      }
    },
    [messages]
  );

  return {
    messages,
    isLoading,
    error,
    sendMessage,
  };
}
