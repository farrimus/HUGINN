// src/hooks/useToolOutput.ts

import { useState, useCallback } from 'react';
import { ToolType, ToolOutputData } from '../types/terminal';

interface ToolOutputState {
  current: { toolType: ToolType | null; data: ToolOutputData | null };
  isAnimating: boolean;
  queue: Array<{ toolType: ToolType; data: ToolOutputData }>;
}

const initialState: ToolOutputState = {
  current: { toolType: null, data: null },
  isAnimating: false,
  queue: [],
};

/**
 * Manages current tool output display state with proper queue handling
 *
 * Uses atomic state updates to prevent race conditions:
 * - Single setState manages all state changes atomically
 * - Array-based queue preserves multiple queued items
 * - No nested setState calls or closure dependencies
 */
export function useToolOutput() {
  const [state, setState] = useState<ToolOutputState>(initialState);

  const display = useCallback((toolType: ToolType, data: ToolOutputData) => {
    setState((prev) => {
      if (prev.isAnimating) {
        // Add to queue while animating (preserves all items)
        return {
          ...prev,
          queue: [...prev.queue, { toolType, data }],
        };
      }
      // Not animating, start immediately
      return {
        current: { toolType, data },
        isAnimating: true,
        queue: [],
      };
    });
  }, []);

  const finishAnimation = useCallback(() => {
    setState((prev) => {
      if (prev.queue.length > 0) {
        // Dequeue first item and start its animation
        const next = prev.queue[0];
        return {
          current: next,
          isAnimating: true,
          queue: prev.queue.slice(1),
        };
      }
      // Queue empty, stop animating
      return {
        ...prev,
        isAnimating: false,
      };
    });
  }, []);

  const clearQueue = useCallback(() => {
    setState((prev) => ({
      ...prev,
      queue: [],
    }));
  }, []);

  // Set content directly without triggering slide animation.
  // Used when content should appear silently (e.g. revealed from under splash screen).
  const setDirect = useCallback((toolType: ToolType, data: ToolOutputData) => {
    setState({
      current: { toolType, data },
      isAnimating: false,
      queue: [],
    });
  }, []);

  return {
    currentToolType: state.current.toolType,
    currentData: state.current.data,
    isAnimating: state.isAnimating,
    queueLength: state.queue.length,
    display,
    finishAnimation,
    clearQueue,
    setDirect,
  };
}
