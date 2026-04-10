// src/components/AssetMapPanel.tsx

import { AssetMapData } from '../types/terminal';
import { DIVIDER } from '../constants/dividers';
import { TYPE_LABEL, TYPE_PRIORITY, statusRank } from '../utils/assemblyUtils';
import { pad } from '../utils/formatters';

interface AssetMapPanelProps {
  data: AssetMapData;
  onPrintToTerminal?: () => void;
}

type Assembly = AssetMapData['assemblies'][number];

// Compact detail string — keep short, used in 42-char column
function detail(a: Assembly): string {
  if (a.is_current) return '[HERE]';
  if (a.assembly_type === 'NetworkNode' && a.fuel_percent !== undefined) {
    if (a.fuel_burning && a.fuel_hours) {
      const h = a.fuel_hours > 999 ? '999h+' : `${a.fuel_hours}h`;
      return `${a.fuel_percent}% ${h}`;
    }
    return `${a.fuel_percent}%`;
  }
  if (a.item_type_count !== undefined) return `${a.item_type_count} types`;
  if (a.is_linked === true) return 'LINKED';
  return '';
}

// Build a single column entry — slice to 42, padEnd to 42 for left col
function entry(a: Assembly): string {
  const label  = pad(TYPE_LABEL[a.assembly_type] ?? a.assembly_type.slice(0, 4).toUpperCase(), 4);
  const isOff  = a.status !== 'ONLINE';
  const name   = pad((isOff ? '~' : ' ') + a.name, 14);
  const status = a.status;
  const det    = detail(a);
  return `  ${label}  ${name}  ${status}${det ? '  ' + det : ''}`;
}

const MAX_ROWS = 7; // 7 rows × 2 cols = up to 14 assemblies in panel

export function AssetMapPanel({ data, onPrintToTerminal }: AssetMapPanelProps) {
  const { characterName, assemblies } = data;

  const total     = assemblies.length;
  const online    = assemblies.filter(a => a.status === 'ONLINE').length;
  const offline   = assemblies.filter(a => a.status !== 'ONLINE' && a.status !== 'DESTROYED').length;
  const destroyed = assemblies.filter(a => a.status === 'DESTROYED').length;

  const sorted = [...assemblies].sort((a, b) => {
    if (a.is_current && !b.is_current) return -1;
    if (!a.is_current && b.is_current) return 1;
    const tp = (TYPE_PRIORITY[a.assembly_type] ?? 9) - (TYPE_PRIORITY[b.assembly_type] ?? 9);
    if (tp !== 0) return tp;
    const sp = statusRank(a.status) - statusRank(b.status);
    if (sp !== 0) return sp;
    return a.name.localeCompare(b.name);
  });

  // Pair into [left, right?] rows
  const pairs: Array<[Assembly, Assembly | undefined]> = [];
  for (let i = 0; i < sorted.length; i += 2) {
    pairs.push([sorted[i], sorted[i + 1]]);
  }

  const visible   = pairs.slice(0, MAX_ROWS);
  const shown     = visible.reduce((n, [, b]) => n + (b ? 2 : 1), visible.length);
  const remaining = total - shown;

  // Header: name left, stats right, 84 chars total
  const nameStr  = (characterName || '[UNKNOWN]').slice(0, 30);
  const prefix   = `ASSETS — ${nameStr}`;
  const statsStr = `${total} total  ${online} online  ${offline} off  ${destroyed} dest`;
  const gap      = Math.max(2, 84 - prefix.length - statsStr.length);
  const header   = prefix + ' '.repeat(gap) + statsStr;

  const rows = visible.map(([left, right]) => {
    const l = entry(left).slice(0, 42).padEnd(42);
    const r = right ? entry(right).slice(0, 42).trimEnd() : '';
    return (l + r).trimEnd();
  });

  const lines: string[] = [DIVIDER, header, ...rows];
  if (remaining > 0) lines.push(`  ... ${remaining} more`);
  lines.push(DIVIDER);

  return (
    <>
      <pre style={{ whiteSpace: 'pre-wrap', wordWrap: 'break-word' }}>
        {lines.join('\n')}
      </pre>
      {onPrintToTerminal && total > 0 && (
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
