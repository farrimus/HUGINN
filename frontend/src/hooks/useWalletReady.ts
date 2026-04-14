// src/hooks/useWalletReady.ts
//
// Consolidates the repeated wallet + assembly bootstrap present in every UI component.
// Returns connection state, the current assembly + owner, derived IDs, and a base
// isReady flag (isConnected && !!assemblyId).
// Callers may apply additional conditions (e.g. && sessionRegistered in TerminalUI).

import {
  useConnection,
  useSmartObject,
  type SmartAssemblyResponse,
  type DetailedSmartCharacterResponse,
} from '@evefrontier/dapp-kit';

export interface WalletReadyResult {
  isConnected: boolean;
  walletAddress: string | null | undefined;
  handleConnect: () => void;
  handleDisconnect: () => void;
  hasEveVault: boolean;
  assembly: SmartAssemblyResponse | null;
  assemblyOwner: DetailedSmartCharacterResponse | null;
  assemblyId: string | undefined;
  itemId: string;
  /** isConnected && !!assemblyId — override if extra conditions are needed. */
  isReady: boolean;
}

export function useWalletReady(): WalletReadyResult {
  const { isConnected, walletAddress, handleConnect, handleDisconnect, hasEveVault } =
    useConnection();
  const { assembly, assemblyOwner } = useSmartObject() as {
    assembly: SmartAssemblyResponse | null;
    assemblyOwner: DetailedSmartCharacterResponse | null;
  };
  const assemblyId = assembly?.id;
  const itemId = new URLSearchParams(window.location.search).get('itemId') || '';
  const isReady = isConnected && !!assemblyId;

  return {
    isConnected,
    walletAddress,
    handleConnect,
    handleDisconnect,
    hasEveVault,
    assembly,
    assemblyOwner,
    assemblyId,
    itemId,
    isReady,
  };
}
