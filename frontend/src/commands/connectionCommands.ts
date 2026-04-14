// src/commands/connectionCommands.ts — /connect, /disconnect, /help

import type { CommandContext } from './types';
import type { HelpGroup } from '../types/terminal';
import { canAccess } from '../features/tierCapabilities';

export function handleConnectionCommands(ctx: CommandContext, command: string): void {
  const {
    isConnected, handleConnect, handleDisconnect,
    featureFlags, tier, toolRegistry,
    addLog, setLogs,
  } = ctx;

  if (command === '/connect') {
    if (isConnected) { addLog('Already connected.', 'warning'); }
    else { handleConnect(); addLog('Initiating wallet connection...', 'command'); }

  } else if (command === '/disconnect') {
    if (!isConnected) { addLog('Not connected.', 'warning'); }
    else { handleDisconnect(); addLog('Wallet disconnected.', 'info'); }

  } else if (command === '/help') {
    const on = (key: string) => featureFlags[key] !== false;
    void toolRegistry; // available for future expansion

    const helpGroups: HelpGroup[] = [
      {
        label: 'CONNECTION',
        cmds: [{ text: '/connect', action: '/connect' }, { text: '/disconnect', action: '/disconnect' }],
      },
      {
        label: 'NAVIGATION',
        cmds: [
          { text: '/system <name>', action: '/system' },
          ...(on('recon')  ? [{ text: '/recon',       action: '/recon' }]  : []),
          ...(on('route')  ? [{ text: '/route [dest]', action: '/route' }] : []),
          { text: '/home', action: '/home' },
        ],
      },
      ...(on('network') || on('nodes') || on('inventory') || on('assets') || on('signal') || on('upload') ? [{
        label: 'INTEL',
        cmds: [
          ...(on('network')   ? [{ text: '/network [all|portables]', action: '/network' }]   : []),
          ...(on('nodes')     ? [{ text: '/nodes',                   action: '/nodes' }]     : []),
          ...(on('inventory') ? [{ text: '/inventory',               action: '/inventory' }] : []),
          ...(on('assets')    ? [{ text: '/assets',                  action: '/assets' }]    : []),
          ...(on('signal')    ? [{ text: '/signal',                  action: '/signal' }]    : []),
          ...(on('upload')    ? [{ text: '/upload',                  action: '/upload' }]    : []),
        ],
      }] : []),
      ...(on('watches') ? [{
        label: 'WATCHER',
        cmds: [{ text: '/watches', action: '/watches' }, { text: '/unwatch <rule_id>', action: '/unwatch' }],
      }] : []),
      ...(on('courier') || on('tribe') || on('board') ? [{
        label: 'SOCIAL',
        cmds: [
          ...(on('courier') ? [{ text: '/courier', action: '/courier' }, { text: '/claim-courier <id>', action: '/claim-courier' }] : []),
          ...(on('tribe')   ? [{ text: '/tribe',   action: '/tribe' }]   : []),
          ...(on('board')   ? [{ text: '/board',   action: '/board' }]   : []),
        ],
      }] : []),
      ...(canAccess(tier, 'canAdmin') ? [{ label: 'ADMIN', cmds: [{ text: '/admin', action: '/admin' }] }] : []),
    ];
    setLogs(prev => [...prev, { text: '', type: 'help' as const, timestamp: Date.now(), helpGroups }]);
    addLog('Anything else goes to HUGINN.', 'info');
  }
}
