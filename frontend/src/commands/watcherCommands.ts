// src/commands/watcherCommands.ts — /watches, /unwatch

import type { CommandContext } from './types';
import type { WatchRule } from '../types/terminal';

export async function handleWatcherCommands(
  ctx: CommandContext,
  command: string,
  parts: string[],
): Promise<void> {
  const { addLog, setLogs, isOff, walletAddress, API_BASE_URL } = ctx;

  if (command === '/watches') {
    if (isOff('watches')) return;
    if (!walletAddress) { addLog('Wallet not connected.', 'warning'); return; }
    try {
      const res = await fetch(`${API_BASE_URL}/watcher/${walletAddress}`, { headers: { 'X-Wallet-Address': walletAddress } });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const rules = ((await res.json()).rules as WatchRule[]).filter(r => r.active);
      if (rules.length === 0) { addLog('No active watch rules. Use /watch <ssu_id> to add one.', 'info'); return; }
      addLog(`Watch rules (${rules.length}):`, 'info');
      const t = Date.now();
      rules.forEach(r => {
        const filter  = r.item_filter ? ` [${r.item_filter}]` : ' [all items]';
        const name    = r.ssu_name || r.ssu_id.slice(0, 16);
        const checked = r.last_checked ? ` checked ${r.last_checked.slice(11, 16)}z` : '';
        setLogs(prev => [...prev, {
          text: `  ${r.id.slice(0, 8)}  ${name}${filter}  threshold=${r.threshold}${checked}`,
          type: 'command' as const,
          timestamp: t,
          action: `/unwatch ${r.id}`,
        }]);
      });
    } catch (err) { addLog(`Failed to load watches: ${err instanceof Error ? err.message : String(err)}`, 'error'); }

  } else if (command === '/unwatch') {
    if (isOff('watches')) return;
    const ruleId = parts[1];
    if (!ruleId) { addLog('Usage: /unwatch <rule_id>', 'warning'); return; }
    if (!walletAddress) { addLog('Wallet not connected.', 'warning'); return; }
    try {
      const res = await fetch(`${API_BASE_URL}/watcher/${walletAddress}/${ruleId}`, { method: 'DELETE', headers: { 'X-Wallet-Address': walletAddress } });
      if (res.status === 404) { addLog(`Rule not found: ${ruleId}`, 'error'); return; }
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      addLog(`Watch rule removed: ${ruleId.slice(0, 8)}`, 'info');
    } catch (err) { addLog(`Unwatch failed: ${err instanceof Error ? err.message : String(err)}`, 'error'); }
  }
}
