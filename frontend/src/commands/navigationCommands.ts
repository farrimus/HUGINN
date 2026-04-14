// src/commands/navigationCommands.ts — /system, /home, /route, /intel

import type { CommandContext } from './types';
import { buildBaselineData } from '../utils/baselineBuilder';

export async function handleNavigationCommands(
  ctx: CommandContext,
  command: string,
  parts: string[],
): Promise<void> {
  const {
    addLog, setLogs, displayToolOutput,
    walletAddress, assemblyId, assembly, enrichedAssembly,
    currentSystem, setCurrentSystem,
    visitorName, tier, API_BASE_URL,
  } = ctx;

  if (command === '/system') {
    const systemName = parts.slice(1).join(' ').trim();
    if (!systemName) { addLog('Usage: /system <system name>', 'warning'); return; }
    try {
      const res = await fetch(`${API_BASE_URL}/galaxy/system/${encodeURIComponent(systemName)}`);
      if (res.status === 404) { addLog(`Unknown system: "${systemName}"`, 'error'); return; }
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      const canonical = data.name as string;
      displayToolOutput('baseline', buildBaselineData(walletAddress, assemblyId, visitorName, tier, canonical, enrichedAssembly));
      setCurrentSystem(canonical);
      addLog(`Location set: ${canonical}`, 'info');
      if (assemblyId) {
        localStorage.setItem(`sys_${assemblyId}`, canonical);
        fetch(`${API_BASE_URL}/structure/${assemblyId}/location/manual`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ system_name: canonical }),
        }).catch((e) => console.warn('Failed to persist system to profile:', e));
      }
    } catch (err) { addLog(`System lookup failed: ${err instanceof Error ? err.message : String(err)}`, 'error'); }

  } else if (command === '/home') {
    displayToolOutput('baseline', buildBaselineData(
      walletAddress, assemblyId, visitorName, tier,
      assembly?.solarSystem?.name || currentSystem || '[REDACTED]',
      enrichedAssembly,
    ));

  } else if (command === '/route') {
    const destination = parts.slice(1).join(' ').trim();
    if (!destination) {
      setLogs(prev => [...prev, { text: '', type: 'form' as const, timestamp: Date.now(), id: `tripcalc-${Date.now()}` }]);
      return;
    }
    try {
      addLog(`Plotting route to ${destination}...`, 'info');
      const res = await fetch(`${API_BASE_URL}/route`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ destination, origin: currentSystem || undefined }),
      });
      if (res.status === 404 || res.status === 400) {
        const err = await res.json();
        addLog(err.detail || `No route found to "${destination}".`, 'error');
        return;
      }
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const routeData = await res.json();
      displayToolOutput('route_planned', routeData);
      addLog(`Route: ${routeData.jumps} jump${routeData.jumps !== 1 ? 's' : ''} to ${destination}.`, 'info');
    } catch (err) { addLog(`Route failed: ${err instanceof Error ? err.message : String(err)}`, 'error'); }

  } else if (command === '/intel') {
    const target = parts.slice(1).join(' ').trim() || currentSystem;
    if (!target) { addLog('Usage: /intel <system name>  (or set location with /system first)', 'warning'); return; }
    try {
      addLog(`Scanning ${target}...`, 'info');
      const res = await fetch(`${API_BASE_URL}/galaxy/system/${encodeURIComponent(target)}/intel`);
      if (res.status === 404) { addLog(`Unknown system: "${target}"`, 'error'); return; }
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      displayToolOutput('system_intel', await res.json());
      addLog('System intel loaded.', 'info');
    } catch (err) { addLog(`Intel scan failed: ${err instanceof Error ? err.message : String(err)}`, 'error'); }
  }
}
