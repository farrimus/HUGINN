// src/components/NetworkMapPanel.tsx

import { NetworkMapData } from '../types/terminal';
import { DIVIDER } from '../constants/dividers';
import { renderPanelLines } from '../utils/renderPanelLines';

interface NetworkMapPanelProps {
  data: NetworkMapData;
  onPrintToTerminal?: () => void;
}

export function NetworkMapPanel({ data, onPrintToTerminal }: NetworkMapPanelProps) {
  const { fuel, energy, connectedAssemblies } = data;

  const fuelStr = fuel.isBurning
    ? `FUEL: ${fuel.fuelPercent.toFixed(0)}%`
    : `FUEL: NOT BURNING`;

  const curEn = parseInt(energy.currentEnergyProduction, 10) || 0;
  const maxEn = parseInt(energy.maxEnergyProduction, 10) || 0;
  const energyStr = maxEn > 0
    ? `ENERGY: ${curEn.toLocaleString()} / ${maxEn.toLocaleString()} kW`
    : `ENERGY: —`;

  // Sort: current first → ONLINE alpha → OFFLINE alpha
  const sorted = [...connectedAssemblies].sort((a, b) => {
    if (a.id === data.currentAssemblyId) return -1;
    if (b.id === data.currentAssemblyId) return 1;
    const aOn = a.status === 'ONLINE' ? 0 : 1;
    const bOn = b.status === 'ONLINE' ? 0 : 1;
    if (aOn !== bOn) return aOn - bOn;
    return a.name.localeCompare(b.name);
  });

  // 11 content lines: 1 header + up to 10 structure rows
  const shown = sorted.slice(0, 10);
  const rest  = sorted.length - shown.length;

  const asmLines = shown.map(a => {
    const isCurrent = a.id === data.currentAssemblyId;
    const isOffline = a.status !== 'ONLINE';
    const prefix    = isOffline ? '~' : ' ';
    const badge     = isCurrent ? ' [THIS]' : '';
    const displayName = (isCurrent && data.currentAssemblyName) ? data.currentAssemblyName : a.name;
    const name   = (prefix + displayName).slice(0, 24).padEnd(24);
    const group  = (a.groupName || a.assemblyType).slice(0, 18).padEnd(18);
    const status = a.status.slice(0, 7).padEnd(7);
    return `  ${name}${group}${status}${badge}`;
  });

  if (rest > 0) {
    asmLines.push(`  ... and ${rest} more`);
  }

  const header = `NODE: ${data.nodeName} [${data.nodeStatus}]   ${fuelStr}   ${energyStr}`;

  const lines = [
    DIVIDER,
    header,
    ...asmLines,
    DIVIDER,
  ];

  return (
    <>
      {renderPanelLines(lines)}
      {onPrintToTerminal && connectedAssemblies.length > 0 && (
        <span
          onClick={onPrintToTerminal}
          style={{ cursor: 'pointer', textDecoration: 'underline', display: 'block', paddingTop: '4px' }}
        >
          {'  [ PRINT FULL LIST ]'}
        </span>
      )}
    </>
  );
}
