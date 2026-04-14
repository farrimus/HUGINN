// src/commands/socialCommands.ts — /courier, /claim-courier, /tribe, /board

import type { CommandContext } from './types';
import type { CourierContract, TribePresenceMember, TribePost } from '../types/terminal';

const TRIBE_NAMES: Record<number, string> = { 1000167: 'WOLF' };

export async function handleSocialCommands(
  ctx: CommandContext,
  command: string,
  parts: string[],
): Promise<void> {
  const {
    addLog, setLogs, isOff,
    walletAddress, tribeId,
    API_BASE_URL, activeBoardLogIdRef,
  } = ctx;

  if (command === '/courier') {
    if (isOff('courier')) return;
    try {
      const res = await fetch(`${API_BASE_URL}/courier`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const contracts = (await res.json()).contracts as CourierContract[];
      if (contracts.length === 0) { addLog('No active courier contracts. Ask HUGINN to post one.', 'info'); return; }
      addLog(`Courier contracts (${contracts.length}):`, 'info');
      const t = Date.now();
      contracts.forEach(c => {
        const status  = c.status.replace('_', ' ').toUpperCase();
        const claimer = c.claimed_by_name ? `  claimer: ${c.claimed_by_name}` : '';
        setLogs(prev => [...prev, {
          text: `  ${c.id.slice(0, 8)}  [${status}]  ${c.item_description}  ${c.from_location} → ${c.to_location}  reward: ${c.reward_description}  by ${c.poster_name}${claimer}`,
          type: 'command' as const,
          timestamp: t,
          action: c.status === 'open' ? `/claim-courier ${c.id}` : undefined,
        }]);
      });
    } catch (err) { addLog(`Failed to load courier board: ${err instanceof Error ? err.message : String(err)}`, 'error'); }

  } else if (command === '/claim-courier') {
    const contractId = parts[1];
    if (!contractId) { addLog('Usage: /claim-courier <contract_id>', 'warning'); return; }
    if (!walletAddress) { addLog('Wallet not connected.', 'warning'); return; }
    try {
      const res = await fetch(`${API_BASE_URL}/courier/${contractId}/claim`, { method: 'PATCH', headers: { 'X-Wallet-Address': walletAddress } });
      if (res.status === 404) { addLog(`Contract not found: ${contractId}`, 'error'); return; }
      if (res.status === 409) { addLog(`Cannot claim: ${(await res.json()).detail}`, 'error'); return; }
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const c = (await res.json()).contract as CourierContract;
      addLog(`Contract claimed: ${c.id.slice(0, 8)}  ${c.item_description}  ${c.from_location} → ${c.to_location}  reward: ${c.reward_description}`, 'info');
    } catch (err) { addLog(`Claim failed: ${err instanceof Error ? err.message : String(err)}`, 'error'); }

  } else if (command === '/tribe') {
    if (isOff('tribe')) return;
    if (!walletAddress) { addLog('Wallet not connected.', 'warning'); return; }
    if (!tribeId) { addLog('No tribe affiliation found. Your character may not belong to a tribe, or tribe data is still loading.', 'warning'); return; }
    try {
      const res = await fetch(`${API_BASE_URL}/tribe/${tribeId}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const members = (await res.json()).members as TribePresenceMember[];
      const tribeName = TRIBE_NAMES[tribeId] ?? `Tribe ${tribeId}`;
      if (members.length === 0) { addLog(`${tribeName} — no members currently online.`, 'info'); return; }
      addLog(`${tribeName} — ${members.length} online:`, 'info');
      const t = Date.now();
      members.forEach(m => setLogs(prev => [...prev, {
        text: `  ${m.character_name.padEnd(20)} [${m.status}]  ${m.location}  ${m.last_ping.slice(11, 16)}z`,
        type: 'command' as const,
        timestamp: t,
      }]));
    } catch (err) { addLog(`Failed to load tribe board: ${err instanceof Error ? err.message : String(err)}`, 'error'); }

  } else if (command === '/board') {
    if (isOff('board')) return;
    if (!walletAddress) { addLog('Wallet not connected.', 'warning'); return; }
    if (!tribeId) { addLog('No tribe affiliation found. Your character may not belong to a tribe, or tribe data is still loading.', 'warning'); return; }
    try {
      const res = await fetch(`${API_BASE_URL}/tribe-posts/${tribeId}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      const boardId = `board-${Date.now()}`;
      activeBoardLogIdRef.current = boardId;
      setLogs(prev => [...prev, {
        text: '',
        type: 'board' as const,
        timestamp: Date.now(),
        id: boardId,
        boardPosts: data.posts as TribePost[],
        boardConfirmDeleteId: null,
        boardShowPostForm: false,
        boardPostDraft: '',
      }]);
    } catch (err) { addLog(`Failed to load board: ${err instanceof Error ? err.message : String(err)}`, 'error'); }
  }
}
