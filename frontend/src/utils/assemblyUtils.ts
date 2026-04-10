// src/utils/assemblyUtils.ts
// Assembly type maps, sort helpers, and network filter shared across panel components and TerminalUI.

export const TYPE_LABEL: Record<string, string> = {
  NetworkNode:      'NODE',
  SmartStorageUnit: 'SSU',
  SmartGate:        'GATE',
  SmartTurret:      'TURT',
  Manufacturing:    'MFG',
  Refinery:         'REF',
  Assembly:         'ASM',
};

export const TYPE_PRIORITY: Record<string, number> = {
  NetworkNode:      0,
  Manufacturing:    1,
  Refinery:         2,
  SmartStorageUnit: 3,
  SmartGate:        4,
  SmartTurret:      5,
};

export function statusRank(s: string): number {
  return s === 'ONLINE' ? 0 : s === 'DESTROYED' ? 2 : 1;
}

export const PORTABLE_TYPE_IDS = new Set(['87160', '87161', '87162', '87566']);

export type NetworkFilter = 'exclude_portables' | 'all' | 'only_portables';

export function applyNetworkFilter<T extends { typeId: string }>(
  assemblies: T[],
  filter: NetworkFilter,
): T[] {
  if (filter === 'all') return assemblies;
  if (filter === 'only_portables') return assemblies.filter(a => PORTABLE_TYPE_IDS.has(a.typeId));
  return assemblies.filter(a => !PORTABLE_TYPE_IDS.has(a.typeId));
}
