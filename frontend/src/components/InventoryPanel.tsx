// src/components/InventoryPanel.tsx
// Phase 7 — SSU inventory panel

import { InventoryData } from '../types/terminal';

interface InventoryPanelProps {
  data: InventoryData;
  onPrintToTerminal?: () => void;
}

import { DIVIDER } from '../constants/dividers';

function fmtNum(n: number): string {
  return n.toFixed(0).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
}

function fmtVol(n: number): string {
  return n.toFixed(2);
}

function pad(s: string, len: number): string {
  return s.slice(0, len).padEnd(len);
}

function padR(s: string, len: number): string {
  return s.slice(0, len).padStart(len);
}

export function InventoryPanel({ data, onPrintToTerminal }: InventoryPanelProps) {
  const { assembly_name, used_capacity, max_capacity, capacity_percent, items } = data;

  // Capacity line
  let capLine: string;
  if (max_capacity !== null && max_capacity > 0) {
    const pct = capacity_percent !== null ? ` (${capacity_percent.toFixed(1)}%)` : '';
    capLine = `CAPACITY: ${fmtNum(used_capacity)} / ${fmtNum(max_capacity)} m³${pct}`;
  } else {
    capLine = `CAPACITY: ${fmtNum(used_capacity)} m³ used`;
  }

  // Sort: category asc, then name asc within category
  const sorted = [...items].sort((a, b) => {
    const catCmp = a.category_name.localeCompare(b.category_name);
    return catCmp !== 0 ? catCmp : a.type_name.localeCompare(b.type_name);
  });

  const cap = 50;
  const shown = sorted.slice(0, cap);
  const rest  = sorted.length - cap;

  // Columns: qty 6, name 22, category 14, volume 9 right-aligned
  const itemLines = shown.map(item => {
    const qty  = padR(fmtNum(item.quantity), 6);
    const name = pad(item.type_name, 22);
    const cat  = pad(item.category_name, 14);
    const vol  = padR(fmtVol(item.total_volume) + ' m³', 9);
    return `${qty}x  ${name}${cat}${vol}`;
  });

  if (rest > 0) {
    itemLines.push(`  ... and ${rest} more item types`);
  }

  const totalVol = items.reduce((s, i) => s + i.total_volume, 0);
  const summaryLine = `  TOTAL: ${fmtVol(totalVol)} m³ in ${items.length} item type${items.length !== 1 ? 's' : ''}`;

  const content = items.length === 0
    ? ['  [ EMPTY ]']
    : [...itemLines, '  ---', summaryLine];

  const lines = [
    DIVIDER,
    `INVENTORY — ${assembly_name} (SSU)`,
    capLine,
    '',
    ...content,
    DIVIDER,
  ];

  return (
    <>
      <pre style={{ whiteSpace: 'pre-wrap', wordWrap: 'break-word' }}>
        {lines.join('\n')}
      </pre>
      {onPrintToTerminal && items.length > 0 && (
        <div style={{
          position: 'absolute',
          bottom: 0,
          left: 0,
          right: 0,
          background: 'linear-gradient(to bottom, transparent, #000 40%)',
          paddingTop: '40px',
          paddingBottom: '16px',
          paddingLeft: '16px',
        }}>
          <span
            onClick={onPrintToTerminal}
            style={{ cursor: 'pointer', textDecoration: 'underline' }}
          >
            {'  [ PRINT FULL LIST ]'}
          </span>
        </div>
      )}
    </>
  );
}
