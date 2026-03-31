import { ReactNode } from 'react';
import '../styles/terminal.css';

interface VisualAreaProps {
  children: ReactNode;
}

/**
 * Container for the visual panel area (top 33% of terminal)
 * Provides consistent styling and layout for all panel displays
 */
export function VisualArea({ children }: VisualAreaProps) {
  return (
    <div id="visual-area" style={{
      flex: '0 0 33%',
      padding: '16px',
      borderBottom: '1px solid #5a4a20',
      overflow: 'hidden',
      fontSize: '13px',
      lineHeight: '1.4',
      whiteSpace: 'pre-wrap',
      wordWrap: 'break-word',
    }}>
      {children}
    </div>
  );
}
