// src/utils/printNode.ts
//
// Fetches a network node from the backend and returns a formatted terminal string.
// Sorts assemblies: ONLINE first, then alphabetical within each group.
// Uses dapp-kit parseStatus for consistent status normalisation.
// Throws on HTTP error so the caller can log the failure.

import { parseStatus, State } from '@evefrontier/dapp-kit';

const pad = (s: string, len: number) => s.slice(0, len).padEnd(len);

export async function fetchAndFormatNode(
  nodeId: string,
  tenant: string,
  apiBaseUrl: string,
): Promise<string> {
  const res = await fetch(`${apiBaseUrl}/entity/network/${nodeId}?tenant=${tenant}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const net = await res.json();

  const fuelStr = net.fuel.is_burning
    ? `FUEL: ${net.fuel.fuel_percent.toFixed(0)}%`
    : 'FUEL: NOT BURNING';

  const sorted = [...(net.connected_assemblies ?? [])].sort((a: any, b: any) => {
    const aOn = parseStatus(a.status) === State.ONLINE ? 0 : 1;
    const bOn = parseStatus(b.status) === State.ONLINE ? 0 : 1;
    return aOn !== bOn ? aOn - bOn : a.name.localeCompare(b.name);
  });

  const asmLines = sorted.map((a: any) => {
    const isOff = parseStatus(a.status) !== State.ONLINE;
    return `  ${pad((isOff ? '~' : ' ') + a.name, 24)}${pad(a.group_name || a.assembly_type, 18)}${a.status}`;
  });

  const lines = [
    `NETWORK — ${net.name} [${net.status}]   ${fuelStr}   (${sorted.length} structures)`,
    ...asmLines,
  ];
  return '[PRINT]: ' + lines.join('\n');
}
