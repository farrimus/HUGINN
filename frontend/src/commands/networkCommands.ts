// src/commands/networkCommands.ts — /network, /nodes, /inventory, /assets, /signal

import type { CommandContext } from './types';
import type { HuginnNewsData } from '../types/terminal';
import { canAccess } from '../features/tierCapabilities';
import { type NetworkFilter, applyNetworkFilter } from '../utils/assemblyUtils';

export async function handleNetworkCommands(
  ctx: CommandContext,
  command: string,
  parts: string[],
): Promise<void> {
  const {
    addLog, isOff, displayToolOutput,
    walletAddress, assemblyId, enrichedAssembly,
    networkData, inventoryData, characterAssemblies,
    tenant, sessionTenant, tier, API_BASE_URL,
  } = ctx;

  if (command === '/network') {
    if (isOff('network')) return;
    if (!networkData) { addLog('Network data not available.', 'warning'); return; }

    const flag = parts[1]?.toLowerCase();
    const filter: NetworkFilter =
      flag === 'all'       ? 'all' :
      flag === 'portables' ? 'only_portables' :
                             'exclude_portables';

    const allAssemblies = (networkData.connected_assemblies ?? []).map(a => ({
      id: a.id, name: a.name, assemblyType: a.assembly_type, status: a.status,
      typeId: a.type_id, key: a.key, groupName: a.group_name, categoryName: a.category_name,
    }));
    const filtered = applyNetworkFilter(allAssemblies, filter);

    displayToolOutput('network_map', {
      nodeId:              networkData.id,
      nodeName:            networkData.name,
      nodeStatus:          networkData.status,
      currentAssemblyId:   assemblyId || '',
      currentAssemblyName: enrichedAssembly?.name ?? assemblyId?.slice(0, 10) ?? '',
      fuel: {
        quantity:           networkData.fuel.quantity,
        maxCapacity:        networkData.fuel.max_capacity,
        fuelPercent:        networkData.fuel.fuel_percent,
        hoursRemaining:     networkData.fuel.hours_remaining,
        burnRateUnitsPerHr: networkData.fuel.burn_rate_units_per_hr,
        isBurning:          networkData.fuel.is_burning,
      },
      energy: {
        currentEnergyProduction: networkData.energy.current_energy_production,
        maxEnergyProduction:     networkData.energy.max_energy_production,
        totalReservedEnergy:     networkData.energy.total_reserved_energy,
        energyPercent:           networkData.energy.energy_percent,
      },
      connectedAssemblies: filtered,
      truncated: networkData.truncated,
    });
    const total = allAssemblies.length;
    const shown = filtered.length;
    const suffix = filter === 'all' ? '' : filter === 'only_portables'
      ? ` (portables only: ${shown}/${total})`
      : ` (${shown}/${total} — /network all to include portables)`;
    addLog(`Network map loaded.${suffix}`, 'info');

  } else if (command === '/nodes') {
    if (isOff('nodes')) return;
    try {
      addLog('Scanning for network nodes...', 'info');
      const res = await fetch(`${API_BASE_URL}/entity/nodes?tenant=${sessionTenant || tenant}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const raw = await res.json();
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const nodes = (raw.nodes ?? []).map((n: any) => ({
        id: n.id, name: n.name, status: n.status, fuelPercent: n.fuel_percent,
        hoursRemaining: n.hours_remaining, isBurning: n.is_burning,
        connectedCount: n.connected_count, systemName: n.system_name,
      }));
      displayToolOutput('nodes_list', { nodes, count: nodes.length });
      addLog(`${nodes.length} network node${nodes.length !== 1 ? 's' : ''} found.`, 'info');
    } catch (err) { addLog(`Nodes scan failed: ${err instanceof Error ? err.message : String(err)}`, 'error'); }

  } else if (command === '/inventory') {
    if (isOff('inventory')) return;
    if (!inventoryData) { addLog('Inventory data not available. Structure may not be a SSU.', 'warning'); return; }
    displayToolOutput('inventory', inventoryData);
    addLog('Inventory loaded.', 'info');

  } else if (command === '/assets') {
    if (isOff('assets')) return;
    if (!characterAssemblies) { addLog('Asset data not available. Wallet may not be connected.', 'warning'); return; }
    displayToolOutput('asset_map', { characterName: characterAssemblies.character_name, assemblies: characterAssemblies.assemblies });
    addLog('Asset map loaded.', 'info');

  } else if (command === '/signal') {
    if (isOff('signal')) return;
    if (!canAccess(tier, 'canSignal')) { addLog('Signal access restricted to OWNER and TRIBE.', 'warning'); return; }
    if (!walletAddress || !assemblyId) { addLog('Wallet not connected.', 'warning'); return; }
    try {
      addLog('Receiving signal...', 'info');
      const res = await fetch(
        `${API_BASE_URL}/news/latest?assembly_id=${encodeURIComponent(assemblyId)}`,
        { headers: { 'X-Wallet-Address': walletAddress } },
      );
      if (res.status === 403) { addLog('Signal access denied.', 'error'); return; }
      if (res.status === 404) { addLog('[ NO TRANSMISSION ON FILE ]', 'info'); return; }
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      displayToolOutput('huginn_news', await res.json() as HuginnNewsData);
      addLog('Signal received.', 'info');
    } catch (err) { addLog(`Signal failed: ${err instanceof Error ? err.message : String(err)}`, 'error'); }
  }
}
