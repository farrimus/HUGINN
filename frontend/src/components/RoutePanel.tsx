// src/components/RoutePanel.tsx

import { useState } from 'react';
import { RouteData } from '../types/terminal';

import { DIVIDER, SUBDIV } from '../constants/dividers';

function copyText(text: string): boolean {
  try {
    const el = document.createElement('textarea');
    el.value = text;
    el.style.cssText = 'position:fixed;top:0;left:0;opacity:0;pointer-events:none';
    document.body.appendChild(el);
    el.focus();
    el.select();
    const ok = document.execCommand('copy');
    document.body.removeChild(el);
    return ok;
  } catch {
    return false;
  }
}

interface RoutePanelProps {
  data: RouteData;
}

export function RoutePanel({ data }: RoutePanelProps) {
  const [copyLabel, setCopyLabel] = useState('COPY ROUTE');

  const origin = data.path[0] ?? '?';
  const dest   = data.path[data.path.length - 1] ?? '?';

  const lyPart      = data.total_ly > 0 ? `${data.total_ly.toFixed(1)} LY` : null;
  const fuelUsed    = data.fuel_used > 0 ? `${data.fuel_used.toFixed(1)}u used` : null;


  const gateJumps   = data.hops ? data.hops.filter(h => h.type === 'gate').length : 0;
  const driveJumps  = data.hops ? data.hops.filter(h => h.type === 'direct').length : 0;

  const jumpBreakdown = data.hops && data.hops.length > 0
    ? [
        gateJumps  > 0 ? `${gateJumps} gate`  : null,
        driveJumps > 0 ? `${driveJumps} jump-drive` : null,
      ].filter(Boolean).join('  ')
    : null;

  const hasRefuel = data.warnings.some(w => /refuel|re-fuel/i.test(w));

  const lines = [
    DIVIDER,
    `ROUTE — ${origin} → ${dest}`,
    SUBDIV,
    `Jumps   : ${data.jumps}`,
    lyPart        ? `Distance: ${lyPart}` : null,
    jumpBreakdown ? `Type    : ${jumpBreakdown}` : null,
    fuelUsed      ? `Fuel    : ${fuelUsed}` : null,
    hasRefuel     ? 'Refuel required en route' : null,
    DIVIDER,
  ].filter((l): l is string => l !== null);

  function handleCopy() {
    const nameToId = new Map<string, number>();
    data.path.forEach((name, i) => {
      if (data.path_ids?.[i]) nameToId.set(name, data.path_ids[i]);
    });
    const link = (name: string) => {
      const id = nameToId.get(name);
      return id ? `<a href="showinfo:5//${id}">${name}</a>` : name;
    };

    const SEP = '─'.repeat(43);
    const origin = data.path[0] ?? '?';
    const dest   = data.path[data.path.length - 1] ?? '?';

    // Find first hop where cumulative fuel use exceeds what we're carrying
    const fuelQuantity = data.fuel_used + data.fuel_remaining; // = ship's starting fuel
    let refuelHopIndex = -1;
    if (fuelQuantity > 0 && data.fuel_remaining < 0 && data.hops && data.total_ly > 0) {
      const fuelRate = data.fuel_used / data.total_ly;
      let cumulative = 0;
      for (let i = 0; i < data.hops.length; i++) {
        cumulative += data.hops[i].distance_ly * fuelRate;
        if (cumulative > fuelQuantity) { refuelHopIndex = i; break; }
      }
    }

    const hopLines: string[] = [];
    if (data.hops && data.hops.length > 0) {
      hopLines.push(`  ${String(1).padStart(3)}. ${link(origin)}  ORIGIN`);
      data.hops.forEach((hop, i) => {
        const num     = String(i + 2).padStart(3);
        const typeTag = hop.type === 'gate' ? 'GATE' : 'JUMP';
        const dist    = hop.distance_ly > 0 ? `  ${hop.distance_ly.toFixed(1)} LY` : '';
        const hot     = data.hot_systems.includes(hop.to) ? '  HOT' : '';
        const refuel  = i === refuelHopIndex ? '  REFUEL' : '';
        hopLines.push(`  ${num}. ${link(hop.to)}  ${typeTag}${dist}${hot}${refuel}`);
      });
    } else {
      data.path.forEach((name, i) => {
        const num     = String(i + 1).padStart(3);
        const typeTag = i === 0 ? 'ORIGIN' : 'GATE';
        hopLines.push(`  ${num}. ${link(name)}  ${typeTag}`);
      });
    }

    const fuelLine = data.fuel_used > 0 || data.fuel_remaining > 0
      ? `Fuel: ${data.fuel_used.toFixed(1)}u used  |  ${data.fuel_remaining.toFixed(1)}u remaining`
      : null;

    const lines = [
      `[ROUTE] ${link(origin)} → ${link(dest)}  —  ${data.jumps} jump${data.jumps !== 1 ? 's' : ''}${data.total_ly > 0 ? `  ${data.total_ly.toFixed(1)} LY` : ''}`,
      SEP,
      ...hopLines,
      SEP,
      ...(fuelLine ? [fuelLine] : []),
      ...(data.hot_systems.length > 0 ? [`Hot systems: ${data.hot_systems.join(', ')}`] : []),
    ];

    const ok = copyText(lines.join('\n'));
    setCopyLabel(ok ? 'COPIED' : 'FAILED');
    setTimeout(() => setCopyLabel('COPY ROUTE'), 2000);
  }

  return (
    <div>
      <pre style={{ whiteSpace: 'pre-wrap', wordWrap: 'break-word' }}>
        {lines.join('\n')}
      </pre>
      {data.path_ids && data.path_ids.length > 0 && (
        <button
          onClick={handleCopy}
          style={{
            marginTop: '6px',
            background: 'transparent',
            border: '1px solid #e87d0d',
            color: '#e87d0d',
            fontFamily: 'inherit',
            fontSize: '0.75rem',
            padding: '2px 10px',
            cursor: 'pointer',
            letterSpacing: '0.05em',
          }}
        >
          {copyLabel}
        </button>
      )}
    </div>
  );
}
