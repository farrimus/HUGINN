// src/components/GateInfoPanel.tsx
// Phase 8 — SmartGate standalone panel

import { GateInfoData } from '../types/terminal';

interface GateInfoPanelProps {
  data: GateInfoData;
}

import { DIVIDER, SUBDIV } from '../constants/dividers';

function truncateName(name: string | null, max = 30): string {
  if (!name) return '';
  return name.length > max ? name.slice(0, max - 3) + '...' : name;
}

export function GateInfoPanel({ data }: GateInfoPanelProps) {
  const { gateName, gateStatus, destinationGate } = data;

  const destLine = destinationGate
    ? `DESTINATION GATE: ${truncateName(destinationGate.name) || destinationGate.id.slice(0, 10) + '...'} [${destinationGate.status ?? 'UNKNOWN'}]`
    : `DESTINATION:         [ NOT LINKED ]`;

  const lines = [
    DIVIDER,
    `SMART GATE — ${truncateName(gateName)} [${gateStatus}]`,
    SUBDIV,
    destLine,
    ...(destinationGate ? ['SYSTEM:              [ GRID REF ENCRYPTED ]'] : []),
    DIVIDER,
  ];

  return (
    <pre style={{ whiteSpace: 'pre-wrap', wordWrap: 'break-word' }}>
      {lines.join('\n')}
    </pre>
  );
}
