// hooks/useSession.ts
//
// Handles all session initialization for a terminal session:
//   1. Admin config + tool registry fetch (once on mount)
//   2. Session registration with backend (when wallet + name + assembly ready)
//   3. Character name + tribe ID resolution from chain
//   4. Tribe presence ping (once when wallet + tribeId known)

import { useState, useEffect } from 'react';
import {
  executeGraphQLQuery,
  GET_WALLET_CHARACTERS,
  parseCharacterFromJson,
  abbreviateAddress,
} from '@evefrontier/dapp-kit';
import {
  FeatureFlags, ToolFlags, ToolRegistryEntry,
  loadCachedAdminConfig, saveCachedAdminConfig, defaultFeatureFlags, defaultToolFlags,
} from '../features/featureFlags';
import { TENANT_PACKAGE_MAP } from '../context/EntityContext';

const API_BASE_URL = window.location.origin;

export interface SessionState {
  featureFlags: FeatureFlags;
  setFeatureFlags: React.Dispatch<React.SetStateAction<FeatureFlags>>;
  toolFlags: ToolFlags;
  setToolFlags: React.Dispatch<React.SetStateAction<ToolFlags>>;
  toolRegistry: ToolRegistryEntry[];
  tier: string;
  shipProfile: Record<string, unknown> | null;
  sessionTenant: string;
  sessionRegistered: boolean;
  visitorName: string;
  tribeId: number | null;
  characterId: number | null;
}

export function useSession(
  walletAddress: string | null | undefined,
  assemblyId: string | undefined,
  tenant: string,
  currentLocation: string,
  resolvedCharacterName?: string,
): SessionState {
  const [featureFlags, setFeatureFlags] = useState<FeatureFlags>(
    () => loadCachedAdminConfig().features
  );
  const [toolFlags, setToolFlags] = useState<ToolFlags>(
    () => loadCachedAdminConfig().tools
  );
  const [toolRegistry, setToolRegistry] = useState<ToolRegistryEntry[]>([]);
  const [tier, setTier] = useState<string>('NONE');
  const [shipProfile, setShipProfile] = useState<Record<string, unknown> | null>(null);
  const [sessionTenant, setSessionTenant] = useState<string>('');
  const [sessionRegistered, setSessionRegistered] = useState<boolean>(false);
  const [visitorName, setVisitorName] = useState<string>('');
  const [tribeId, setTribeId] = useState<number | null>(null);
  const [characterId, setCharacterId] = useState<number | null>(null);

  // 1. Admin config + tool registry (once on mount)
  useEffect(() => {
    Promise.all([
      fetch(`${API_BASE_URL}/admin/config`).then(r => r.ok ? r.json() : null),
      fetch(`${API_BASE_URL}/admin/tool-registry`).then(r => r.ok ? r.json() : []),
    ]).then(([configData, registry]) => {
      if (Array.isArray(registry) && registry.length > 0) {
        setToolRegistry(registry);
        const toolDefaults = Object.fromEntries(registry.map((t: ToolRegistryEntry) => [t.name, t.default_enabled]));
        const merged = {
          features: { ...defaultFeatureFlags(), ...(configData?.features || {}) },
          tools:    { ...toolDefaults,           ...(configData?.tools    || {}) },
        };
        setFeatureFlags(merged.features);
        setToolFlags(merged.tools);
        saveCachedAdminConfig(merged);
      } else if (configData) {
        const merged = {
          features: { ...defaultFeatureFlags(), ...(configData.features || {}) },
          tools:    { ...defaultToolFlags(),    ...(configData.tools    || {}) },
        };
        setFeatureFlags(merged.features);
        setToolFlags(merged.tools);
        saveCachedAdminConfig(merged);
      }
    }).catch(() => { /* keep cached state on failure */ });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 2. Session registration — fires on wallet + assembly + visitorName only.
  // Tier is resolved server-side on first contact only (passport model).
  // characterId / tribeId enrichment is sent separately via effect 5 (PATCH).
  useEffect(() => {
    if (!walletAddress || !assemblyId) return;
    fetch(`${API_BASE_URL}/session/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        wallet_address: walletAddress,
        character_name: visitorName || abbreviateAddress(walletAddress),
        assembly_id: assemblyId,
        tenant: (sessionTenant || tenant),
      }),
    })
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (data?.tier) setTier(data.tier);
        if (data?.ship_profile) setShipProfile(data.ship_profile);
        if (data?.tenant) setSessionTenant(data.tenant);
        setSessionRegistered(true);
      })
      .catch(() => {
        setSessionRegistered(true); // fail-open: unlock terminal even if backend is down
      });
  }, [walletAddress, assemblyId, visitorName]); // eslint-disable-line react-hooks/exhaustive-deps

  // 3. Character name + tribe ID from chain
  // Skipped when resolvedCharacterName is provided by the caller (e.g. from EntityContext).
  useEffect(() => {
    if (resolvedCharacterName) {
      setVisitorName(resolvedCharacterName);
      return;
    }
    if (!walletAddress || !tenant) return;
    const pkgId = TENANT_PACKAGE_MAP[tenant];
    if (!pkgId) return;
    const profileType = `${pkgId}::character::PlayerProfile`;
    let cancelled = false;
    executeGraphQLQuery(GET_WALLET_CHARACTERS, {
      owner: walletAddress,
      characterPlayerProfileType: profileType,
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    }).then((result: any) => {
      if (cancelled) return;
      const charJson = result?.data?.address?.objects?.nodes?.[0]
        ?.contents?.extract?.asAddress?.asObject?.asMoveObject?.contents?.json;
      const char = parseCharacterFromJson(charJson);
      if (char?.name) setVisitorName(char.name);
      else setVisitorName(abbreviateAddress(walletAddress));
      if (char?.tribeId && char.tribeId > 0) setTribeId(char.tribeId);
      if (char?.characterId && char.characterId > 0) setCharacterId(char.characterId);
    }).catch(() => {
      if (!cancelled) setVisitorName(abbreviateAddress(walletAddress));
    });
    return () => { cancelled = true; };
  }, [walletAddress, tenant, resolvedCharacterName]); // eslint-disable-line react-hooks/exhaustive-deps

  // 5. Session enrichment — sends characterId / tribeId via PATCH once resolved.
  // Waits for sessionRegistered so the session exists before patching.
  useEffect(() => {
    if (!walletAddress || !sessionRegistered || (!characterId && !tribeId)) return;
    fetch(`${API_BASE_URL}/session/${walletAddress}`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
        'X-Wallet-Address': walletAddress,
      },
      body: JSON.stringify({
        ...(characterId ? { character_id: characterId } : {}),
        ...(tribeId   ? { tribe_id:     tribeId   } : {}),
      }),
    }).catch(() => {}); // best-effort — session still works without enrichment
  }, [walletAddress, sessionRegistered, characterId, tribeId]); // eslint-disable-line react-hooks/exhaustive-deps

  // 4. Tribe presence ping — once when wallet + tribeId first known
  useEffect(() => {
    if (!walletAddress || !tribeId) return;
    fetch(`${API_BASE_URL}/tribe/presence`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Wallet-Address': walletAddress },
      body: JSON.stringify({ tribe_id: tribeId, location: currentLocation || 'unknown', status: 'active' }),
    }).catch(() => {});
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [walletAddress, tribeId]);

  return {
    featureFlags, setFeatureFlags,
    toolFlags, setToolFlags,
    toolRegistry,
    tier,
    shipProfile,
    sessionTenant,
    sessionRegistered,
    visitorName,
    tribeId,
    characterId,
  };
}
