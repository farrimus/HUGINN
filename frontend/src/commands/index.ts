// src/commands/index.ts
//
// createDispatcher(ctx) — returns the handleCommand function for TerminalUI.
// Routes slash commands to their handler modules. Non-command input falls through
// to the caller (TerminalUI sends it to handleChatMessage instead).

import type { CommandContext } from './types';
import { handleConnectionCommands } from './connectionCommands';
import { handleNavigationCommands } from './navigationCommands';
import { handleNetworkCommands } from './networkCommands';
import { handleWatcherCommands } from './watcherCommands';
import { handleSocialCommands } from './socialCommands';
import { handleAdminCommands } from './adminCommands';

export function createDispatcher(ctx: CommandContext) {
  return async (input: string): Promise<void> => {
    const parts   = input.trim().split(/\s+/);
    const command = parts[0].toLowerCase();

    if (['/connect', '/disconnect', '/help'].includes(command))
      return handleConnectionCommands(ctx, command);

    if (['/system', '/home', '/route', '/intel'].includes(command))
      return handleNavigationCommands(ctx, command, parts);

    if (['/network', '/nodes', '/inventory', '/assets', '/signal'].includes(command))
      return handleNetworkCommands(ctx, command, parts);

    if (['/watches', '/unwatch'].includes(command))
      return handleWatcherCommands(ctx, command, parts);

    if (['/courier', '/claim-courier', '/tribe', '/board'].includes(command))
      return handleSocialCommands(ctx, command, parts);

    if (['/admin', '/recon', '/upload', '/debug'].includes(command))
      return handleAdminCommands(ctx, command);

    ctx.addLog(`Unknown command: ${command}`, 'error');
  };
}

export type { CommandContext };
