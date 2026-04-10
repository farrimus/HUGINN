// src/components/NodesListPanel.tsx

import { NodesListData, NodesListEntry } from '../types/terminal';
import { PanelHr } from './PanelHr';

interface NodesListPanelProps {
  data: NodesListData;
  onPrint: (nodeId: string) => void;
}

function fuelStr(n: NodesListEntry): string {
  if (!n.isBurning) return 'NOT BURNING';
  return `${n.fuelPercent.toFixed(0)}%`;
}

export function NodesListPanel({ data, onPrint }: NodesListPanelProps) {
  const { nodes } = data;

  const header = `NETWORK NODES (${nodes.length})`;

  return (
    <div className="panel-lines">
      <PanelHr />
      <div className="panel-text-line">{header}</div>
      {nodes.map(n => {
        const id      = n.id.slice(2, 10).toUpperCase().padEnd(10);
        const system  = (n.systemName || '—').slice(0, 16).padEnd(16);
        const count   = `${n.connectedCount} str`.padEnd(8);
        const fuel    = `FUEL: ${fuelStr(n)}`.padEnd(12);
        const status  = n.status.slice(0, 7).padEnd(7);
        const row     = `  ${id}${system}${count}${fuel}${status}`;
        return (
          <div key={n.id} className="panel-text-line">
            {row}
            <span
              onClick={() => onPrint(n.id)}
              style={{ cursor: 'pointer', textDecoration: 'underline' }}
            >{' [PRINT]'}</span>
          </div>
        );
      })}
      <PanelHr />
    </div>
  );
}
