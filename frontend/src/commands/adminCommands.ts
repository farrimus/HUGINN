// src/commands/adminCommands.ts — /admin, /recon, /upload, /debug

import type { CommandContext } from './types';
import { canAccess } from '../features/tierCapabilities';

export function handleAdminCommands(ctx: CommandContext, command: string): void {
  const {
    addLog, setLogs, isOff,
    tier, featureFlags, toolFlags,
    setDebugMode,
  } = ctx;

  if (command === '/admin') {
    if (!canAccess(tier, 'canAdmin')) { addLog('Admin access restricted to OWNER.', 'warning'); return; }
    setLogs(prev => [...prev, {
      text: '',
      type: 'admin' as const,
      timestamp: Date.now(),
      id: `admin-${Date.now()}`,
      adminFeatureFlags: { ...featureFlags },
      adminToolFlags: { ...toolFlags },
    }]);

  } else if (command === '/recon') {
    if (isOff('recon')) return;
    setLogs(prev => [...prev, { text: '', type: 'recon' as const, timestamp: Date.now(), id: `recon-${Date.now()}` }]);

  } else if (command === '/upload') {
    setLogs(prev => [...prev, { text: '', type: 'upload' as const, timestamp: Date.now(), id: `upload-${Date.now()}` }]);

  } else if (command === '/debug') {
    setDebugMode(true);
    addLog('Debug mode active. Session will be dumped after each message.', 'info');
  }
}
