// src/commands/printFormatters.ts
//
// printRouteToChat   — formats a route result for display in the terminal log
// printToTerminal    — formats the current tool panel data as plain text

import type { CommandContext } from './types';
import type { RouteData, HuginnNewsData, BuildOptionsData, NetworkMapData } from '../types/terminal';
import { SUBDIV } from '../constants/dividers';
import { fmtNum, fmtVol, pad, padR } from '../utils/formatters';
import { TYPE_LABEL, TYPE_PRIORITY, statusRank } from '../utils/assemblyUtils';
import { fmtBuildStep } from '../components/ToolOutputFormatter';

// ---------------------------------------------------------------------------
// Route formatter
// ---------------------------------------------------------------------------

export function printRouteToChat(route: RouteData, ctx: CommandContext): void {
  const { addLog, setLogs } = ctx;

  const origin = route.path[0] ?? '?';
  const dest   = route.path[route.path.length - 1] ?? '?';

  const hopLines: string[] = [];
  if (route.hops && route.hops.length > 0) {
    hopLines.push(`  ${String(1).padStart(3)}. ${origin.padEnd(24)} ORIGIN`);
    route.hops.forEach((hop, i) => {
      const num     = String(i + 2).padStart(3);
      const name    = hop.to.padEnd(24);
      const typeTag = hop.type === 'gate' ? 'GATE' : 'JUMP';
      const dist    = hop.type === 'direct' ? `  ${hop.distance_ly.toFixed(1)} LY` : '';
      const hot     = hop.dest_temp >= 70 ? `  [${hop.dest_temp}°]` : '';
      hopLines.push(`  ${num}. ${name} ${typeTag}${dist}${hot}`);
    });
  } else {
    route.path.forEach((name, i) => {
      const num     = String(i + 1).padStart(3);
      const typeTag = i === 0 ? 'ORIGIN' : 'GATE';
      hopLines.push(`  ${num}. ${name.padEnd(24)} ${typeTag}`);
    });
  }

  const fuelLine = route.fuel_used > 0 || route.fuel_remaining > 0
    ? `Fuel: ${route.fuel_used.toFixed(1)}u used  |  ${route.fuel_remaining.toFixed(1)}u remaining`
    : null;

  const lines = [
    `[ROUTE] ${origin} → ${dest}  —  ${route.jumps} jump${route.jumps !== 1 ? 's' : ''}${route.total_ly > 0 ? `  ${route.total_ly.toFixed(1)} LY` : ''}`,
    SUBDIV,
    ...hopLines,
    SUBDIV,
    ...(fuelLine ? [fuelLine] : []),
    ...(route.hot_systems.length > 0 ? [`Hot: ${route.hot_systems.join(', ')}`] : []),
    ...(route.warnings.length > 0 ? route.warnings.map(w => `  ! ${w}`) : []),
  ];
  addLog(lines.join('\n'), 'info');

  // Build linked copy version (system names → in-game showinfo links)
  const COPY_SEP = '─'.repeat(43);
  const nameToId = new Map<string, number>();
  route.path.forEach((name, i) => {
    if (route.path_ids?.[i]) nameToId.set(name, route.path_ids[i]);
  });
  const link = (name: string) => {
    const id = nameToId.get(name);
    return id ? `<a href="showinfo:5//${id}">${name}</a>` : name;
  };

  // Find hop where cumulative fuel use first exceeds available fuel
  const fuelQuantity = route.fuel_used + route.fuel_remaining;
  let refuelHopIndex = -1;
  if (fuelQuantity > 0 && route.fuel_remaining < 0 && route.hops && route.total_ly > 0) {
    const fuelRate = route.fuel_used / route.total_ly;
    let cumulative = 0;
    for (let i = 0; i < route.hops.length; i++) {
      cumulative += route.hops[i].distance_ly * fuelRate;
      if (cumulative > fuelQuantity) { refuelHopIndex = i; break; }
    }
  }

  const linkedHopLines: string[] = [];
  if (route.hops && route.hops.length > 0) {
    linkedHopLines.push(`  ${String(1).padStart(3)}. ${link(origin)}  ORIGIN`);
    route.hops.forEach((hop, i) => {
      const num     = String(i + 2).padStart(3);
      const typeTag = hop.type === 'gate' ? 'GATE' : 'JUMP';
      const dist    = hop.type === 'direct' ? `  ${hop.distance_ly.toFixed(1)} LY` : '';
      const hot     = route.hot_systems.includes(hop.to) ? '  HOT' : '';
      const refuel  = i === refuelHopIndex ? '  REFUEL' : '';
      linkedHopLines.push(`  ${num}. ${link(hop.to)}  ${typeTag}${dist}${hot}${refuel}`);
    });
  } else {
    route.path.forEach((name, i) => {
      const num     = String(i + 1).padStart(3);
      const typeTag = i === 0 ? 'ORIGIN' : 'GATE';
      linkedHopLines.push(`  ${num}. ${link(name)}  ${typeTag}`);
    });
  }
  const linkedLines = [
    `[ROUTE] ${link(origin)} → ${link(dest)}  —  ${route.jumps} jump${route.jumps !== 1 ? 's' : ''}${route.total_ly > 0 ? `  ${route.total_ly.toFixed(1)} LY` : ''}`,
    COPY_SEP,
    ...linkedHopLines,
    COPY_SEP,
    ...(fuelLine ? [fuelLine] : []),
    ...(route.hot_systems.length > 0 ? [`Hot systems: ${route.hot_systems.join(', ')}`] : []),
  ];
  setLogs(prev => [...prev, {
    text: '',
    type: 'info' as const,
    timestamp: Date.now(),
    copyText: linkedLines.join('\n'),
  }]);
}

// ---------------------------------------------------------------------------
// Print-to-terminal (converts current panel data to chat log text)
// ---------------------------------------------------------------------------

export function printToTerminal(ctx: CommandContext): void {
  const {
    addLog, currentToolType, currentData,
    inventoryData, characterAssemblies, assemblyId, enrichedAssembly,
  } = ctx;

  if (currentToolType === 'inventory' && inventoryData) {
    const { assembly_name, used_capacity, max_capacity, capacity_percent, items } = inventoryData;
    const capStr = max_capacity && max_capacity > 0
      ? `${fmtNum(used_capacity)} / ${fmtNum(max_capacity)} m³${capacity_percent !== null ? ` (${capacity_percent.toFixed(1)}%)` : ''}`
      : `${fmtNum(used_capacity)} m³ used`;
    const sorted = [...items].sort((a, b) => {
      const c = a.category_name.localeCompare(b.category_name);
      return c !== 0 ? c : a.type_name.localeCompare(b.type_name);
    });
    const itemLines = sorted.map(item =>
      `  ${padR(fmtNum(item.quantity), 6)}x  ${pad(item.type_name, 24)}${pad(item.category_name, 16)}${padR(fmtVol(item.total_volume) + ' m³', 12)}`
    );
    const totalVol = items.reduce((s, i) => s + i.total_volume, 0);
    addLog('[PRINT]: ' + [
      `INVENTORY — ${assembly_name}  |  ${capStr}`,
      ...itemLines,
      `  TOTAL: ${items.length} item type${items.length !== 1 ? 's' : ''}, ${fmtVol(totalVol)} m³`,
    ].join('\n'), 'info');

  } else if (currentToolType === 'network_map' && currentData) {
    const netData = currentData as NetworkMapData;
    const { nodeName: name, nodeStatus: status, fuel, energy } = netData;
    const fuelStr = fuel.isBurning
      ? `FUEL: ${fuel.fuelPercent.toFixed(0)}%  ~${(fuel.hoursRemaining / 24).toFixed(1)}d`
      : 'FUEL: NOT BURNING';
    const maxEn = parseInt(energy.maxEnergyProduction, 10) || 0;
    const curEn = parseInt(energy.currentEnergyProduction, 10) || 0;
    const enStr = maxEn > 0
      ? `ENERGY: ${fmtNum(curEn)} / ${fmtNum(maxEn)} kW`
      : 'ENERGY: [ NO DATA ]';
    const sorted = [...(netData.connectedAssemblies ?? [])].sort((a, b) => {
      if (a.id === assemblyId) return -1;
      if (b.id === assemblyId) return 1;
      const aOn = a.status === 'ONLINE' ? 0 : 1;
      const bOn = b.status === 'ONLINE' ? 0 : 1;
      return aOn !== bOn ? aOn - bOn : a.name.localeCompare(b.name);
    });
    const asmLines = sorted.map(a => {
      const off = a.status !== 'ONLINE';
      const badge = a.id === assemblyId ? ' [THIS]' : (off ? ' [!]' : '');
      const displayName = (a.id === assemblyId && enrichedAssembly?.name) ? enrichedAssembly.name : a.name;
      return `  ${pad((off ? '~' : ' ') + displayName, 24)}${pad(a.groupName || a.assemblyType, 18)}${a.status}${badge}`;
    });
    addLog('[PRINT]: ' + [
      `NETWORK — ${name} [${status}]  |  ${fuelStr}  |  ${enStr}`,
      `  (${sorted.length} connected structure${sorted.length !== 1 ? 's' : ''})`,
      ...asmLines,
    ].join('\n'), 'info');

  } else if (currentToolType === 'huginn_news' && currentData) {
    addLog((currentData as HuginnNewsData).text, 'info');

  } else if (currentToolType === 'asset_map' && characterAssemblies) {
    const sorted = [...characterAssemblies.assemblies].sort((a, b) => {
      if (a.is_current && !b.is_current) return -1;
      if (!a.is_current && b.is_current) return 1;
      const tp = (TYPE_PRIORITY[a.assembly_type] ?? 9) - (TYPE_PRIORITY[b.assembly_type] ?? 9);
      if (tp !== 0) return tp;
      const r = statusRank(a.status) - statusRank(b.status);
      return r !== 0 ? r : a.name.localeCompare(b.name);
    });
    addLog('[PRINT]: ' + [
      `ASSETS — ${characterAssemblies.character_name} (${sorted.length} structure${sorted.length !== 1 ? 's' : ''})`,
      ...sorted.map(a => {
        const label  = pad(TYPE_LABEL[a.assembly_type] ?? a.assembly_type.slice(0, 4).toUpperCase(), 4);
        const name   = pad(a.name, 22);
        const st     = pad(a.status, 9);
        const parts: string[] = [];
        if (a.assembly_type === 'NetworkNode') {
          if (a.fuel_percent !== undefined) parts.push(`${a.fuel_percent}% fuel`);
          if (a.fuel_burning && a.fuel_hours) parts.push(`${a.fuel_hours}h`);
          if (a.connected_count !== undefined) parts.push(`${a.connected_count} linked`);
        } else if (a.assembly_type === 'SmartGate') {
          if (a.is_linked !== undefined) parts.push(a.is_linked ? 'LINKED' : 'UNLINKED');
        } else if (a.item_type_count !== undefined) {
          parts.push(`${a.item_type_count} item type${a.item_type_count !== 1 ? 's' : ''}`);
        }
        if (a.is_current) parts.push('[HERE]');
        const off = a.status !== 'ONLINE';
        return `  ${off ? '~' : ' '}${label}  ${name}  ${st}  ${parts.join('  ')}`.trimEnd();
      }),
    ].join('\n'), 'info');

  } else if (currentToolType === 'build_options' && currentData) {
    const bd = currentData as BuildOptionsData;
    const steps = bd.buildOrder ?? [];
    if (steps.length === 0) return;
    addLog('[BUILD ORDER]\n' + steps.map(fmtBuildStep).join('\n'), 'info');
  }
}
