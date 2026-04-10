// src/utils/renderPanelLines.tsx
import React from 'react';
import { PanelHr } from '../components/PanelHr';

/**
 * Renders panel text as line-by-line React elements.
 * Lines composed entirely of '═' become edge-to-edge heavy dividers (PanelHr).
 * Lines composed entirely of '─' become edge-to-edge light dividers (PanelHr light).
 * All other lines render as text, preserving whitespace for column alignment.
 *
 * Detection is character-level (not length-based) — adapts to any container width.
 */
export function renderPanelLines(input: string | string[]): React.JSX.Element {
  const lines = Array.isArray(input) ? input : input.split('\n');

  return (
    <div className="panel-lines">
      {lines.map((line, i) => {
        if (line.length > 0 && line.split('').every(c => c === '═'))
          return <PanelHr key={i} />;
        if (line.length > 0 && line.split('').every(c => c === '─'))
          return <PanelHr key={i} light />;
        return (
          <div key={i} className="panel-text-line">
            {line || '\u00A0'}
          </div>
        );
      })}
    </div>
  );
}
