// src/commands/types.ts
//
// CommandContext — all state and callbacks needed by TerminalUI command handlers.
// Built once per render in TerminalUI and passed to createDispatcher().

import type { MutableRefObject, Dispatch, SetStateAction } from 'react';
import type { SmartAssemblyResponse } from '@evefrontier/dapp-kit';
import type {
  TerminalLog, ToolType, ToolOutputData,
} from '../types/terminal';
import type {
  EnrichedAssembly, NetworkData, InventoryData, CharacterAssemblies,
} from '../context/EntityContext';
import type { FeatureFlags, ToolFlags, ToolRegistryEntry } from '../features/featureFlags';

export interface CommandContext {
  // Logging
  addLog: (text: string, type?: TerminalLog['type'], action?: string) => void;
  setLogs: Dispatch<SetStateAction<TerminalLog[]>>;

  // Feature flag guard — returns true + warns if the feature is disabled
  isOff: (key: string) => boolean;

  // Tool output panel
  displayToolOutput: (type: ToolType, data: ToolOutputData) => void;
  currentToolType: ToolType | null;
  currentData: ToolOutputData | null;

  // Wallet / assembly identity
  walletAddress: string | null | undefined;
  assemblyId: string | undefined;
  isConnected: boolean;
  handleConnect: () => void;
  handleDisconnect: () => void;
  assembly: SmartAssemblyResponse | null;

  // Entity context
  enrichedAssembly: EnrichedAssembly | null;
  networkData: NetworkData | null;
  inventoryData: InventoryData | null;
  characterAssemblies: CharacterAssemblies | null;
  tenant: string;
  sessionTenant: string | null | undefined;

  // Session
  featureFlags: FeatureFlags;
  setFeatureFlags: (f: FeatureFlags) => void;
  toolFlags: ToolFlags;
  setToolFlags: (f: ToolFlags) => void;
  tier: string;
  visitorName: string | null | undefined;
  tribeId: number | null | undefined;
  toolRegistry: ToolRegistryEntry[];

  // Navigation state
  currentSystem: string;
  setCurrentSystem: (s: string) => void;

  // Debug
  setDebugMode: (d: boolean) => void;

  // Refs
  activeBoardLogIdRef: MutableRefObject<string | null>;

  // Backend base URL
  API_BASE_URL: string;
}
