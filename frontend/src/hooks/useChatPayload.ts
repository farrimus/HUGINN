// src/hooks/useChatPayload.ts
//
// Returns buildPayload() — a factory for CompanionStreamPayload that pre-fills assembly
// context (id, name, type, state, system, wallet address, item id).
// Callers supply message + per-call overrides (history, debug, disabled_tools,
// entity_snapshot, tenant, character_name).

import { useConnection, useSmartObject, type SmartAssemblyResponse } from '@evefrontier/dapp-kit';
import { useEntityContext } from '../context/EntityContext';
import type { CompanionStreamPayload } from './useCompanionStream';

interface UseChatPayloadOpts {
  /** Resolved character name (varies per UI — visitor name, owner name, abbreviation). */
  characterName?: string | null;
  /** Tenant override (e.g. sessionTenant || tenant in TerminalUI). Falls back to EntityContext tenant. */
  tenant?: string;
  /** Fallback system name when assembly.solarSystem is null. */
  systemFallback?: string;
}

export function useChatPayload({
  characterName,
  tenant: tenantOverride,
  systemFallback = '',
}: UseChatPayloadOpts = {}) {
  const { walletAddress } = useConnection();
  const { assembly } = useSmartObject() as { assembly: SmartAssemblyResponse | null };
  const { enrichedAssembly, tenant: ctxTenant } = useEntityContext();

  const assemblyId = assembly?.id;
  const itemId = new URLSearchParams(window.location.search).get('itemId') || '';

  const buildPayload = (
    message: string,
    overrides: Partial<CompanionStreamPayload> = {},
  ): CompanionStreamPayload => ({
    assembly_id: assemblyId ?? '',
    message,
    history: [],
    owner_address: walletAddress || '',
    character_name: characterName ?? '',
    item_id: itemId,
    assembly_name: enrichedAssembly?.name ?? assembly?.name ?? '',
    assembly_type: enrichedAssembly?.assembly_type ?? (assembly as any)?.typeDetails?.name ?? '',
    assembly_state: enrichedAssembly?.status ?? assembly?.state ?? '',
    system_name: assembly?.solarSystem?.name || systemFallback,
    system_id: assembly?.solarSystem?.id,
    tenant: tenantOverride ?? ctxTenant,
    ...overrides,
  });

  return { buildPayload };
}
