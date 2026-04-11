// src/context/EntityContext.tsx
//
// Provides enriched entity data for the current assembly via React Query.
// Four parallel/chained queries:
//   1. enrichedAssembly   — /entity/assembly/{id}
//   2. networkData        — /entity/network/{nodeId}     (after 1)
//   3. inventoryData      — /entity/inventory/{id}       (after 1, SSU only)
//   4. characterAssemblies — Sui GraphQL via dapp-kit getCharacterAndOwnedObjects()
//
// Tenant auto-detection (priority order):
//   1. URL ?tenant= param  — game client always injects this in-game
//   2. Assembly _raw type  — package ID in Move type repr maps to tenant
//   3. GET /config         — backend returns its DEPLOYMENT_ENV
//
// React Query handles deduplication, stale-while-revalidate, cancellation,
// and retry automatically. No manual AbortController or loading flags needed.

import { createContext, useContext, ReactNode } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  useConnection,
  useSmartObject,
  getCharacterAndOwnedObjects,
  getCharacterOwnedObjectsJson,
  parseCharacterFromJson,
  getAssemblyType,
  executeGraphQLQuery,
  GET_WALLET_CHARACTERS,
  type SmartAssemblyResponse,
} from '@evefrontier/dapp-kit';

const STALE_MS = 30_000;

// Package ID → tenant name. Matches dapp-kit TENANT_CONFIG (v0.0.18).
const PACKAGE_TENANT_MAP: Record<string, string> = {
  '0xd12a70c74c1e759445d6f209b01d43d860e97fcf2ef72ccbbd00afd828043f75': 'utopia',
  '0x28b497559d65ab320d9da4613bf2498d5946b2c0ae3597ccfda3072ce127448c': 'stillness',
  '0x353988e063b4683580e3603dbe9e91fefd8f6a06263a646d43fd3a2f3ef6b8c1': 'nebula',
};

// Tenant name → package ID (reverse of PACKAGE_TENANT_MAP).
export const TENANT_PACKAGE_MAP: Record<string, string> = Object.fromEntries(
  Object.entries(PACKAGE_TENANT_MAP).map(([pkg, t]) => [t, pkg])
);

/**
 * Derive tenant from the assembly's on-chain Move type repr.
 * The repr starts with the package ID: "0xd12a...::storage_unit::StorageUnit"
 * Returns null if _raw is unavailable or package ID is unrecognised.
 */
function deriveTeantFromAssembly(asm: SmartAssemblyResponse | null): string | null {
  // _raw.contents.type.repr may not always be populated; use safe cast
  const raw = asm?._raw as { contents?: { type?: { repr?: string } } } | undefined;
  const repr = raw?.contents?.type?.repr;
  if (!repr) return null;
  const pkgId = repr.split('::')[0];
  return PACKAGE_TENANT_MAP[pkgId] ?? null;
}

// ---------------------------------------------------------------------------
// Types for backend /entity/* responses
// ---------------------------------------------------------------------------

export type AssemblyType =
  | 'SmartStorageUnit'
  | 'SmartGate'
  | 'SmartTurret'
  | 'NetworkNode'
  | 'Manufacturing'
  | 'Refinery'
  | 'Unknown';

export interface EnrichedAssembly {
  id: string;
  assembly_type: AssemblyType;
  type_id: string;
  name: string;
  status: string;
  key?: unknown;
  owner?: {
    character_name: string;
    tribe_id: number;
    tribe_name?: string;
    character_id: string | number;
  };
  network_node?: {
    id: string;
    name: string;
    status: string;
    fuel_percent: number;
    fuel_quantity: number;
    fuel_effective_max: number;
    fuel_hours_remaining: number;
    energy_used: string;
    energy_max: string;
  };
  destination_gate?: {
    id: string;
    name: string | null;
    status: string | null;
  };
}

export interface NetworkData {
  id: string;
  name: string;
  status: string;
  fuel: {
    quantity: string;
    max_capacity: string;
    fuel_percent: number;
    hours_remaining: number;
    burn_rate_units_per_hr: number;
    is_burning: boolean;
  };
  energy: {
    current_energy_production: string;
    max_energy_production: string;
    total_reserved_energy: string;
    energy_percent: number;
  };
  connected_assemblies: Array<{
    id: string;
    name: string;
    assembly_type: string;
    status: string;
    type_id: string;
    key: unknown;
    group_name: string;
    category_name: string;
  }>;
  truncated: boolean;
}

export interface InventoryItem {
  type_id: string;
  type_name: string;
  category_name: string;
  quantity: number;
  volume_per_unit: number;
  total_volume: number;
}

export interface InventoryData {
  assembly_id: string;
  assembly_name: string;
  used_capacity: number;
  max_capacity: number | null;
  capacity_percent: number | null;
  items: InventoryItem[];
}

export interface CharacterAssemblies {
  character_name: string;
  assemblies: CharacterAssembly[];
}

export interface CharacterAssembly {
  assembly_id: string;
  name: string;
  assembly_type: string;
  status: string;
  is_current: boolean;
  // NetworkNode enrichment
  fuel_percent?: number;
  fuel_hours?: number;
  fuel_burning?: boolean;
  connected_count?: number;
  // Storage enrichment
  item_type_count?: number;
  // SmartGate enrichment
  is_linked?: boolean;
}

// ---------------------------------------------------------------------------
// Context value shape
// ---------------------------------------------------------------------------

interface EntityContextValue {
  enrichedAssembly: EnrichedAssembly | null;
  networkData: NetworkData | null;
  inventoryData: InventoryData | null;
  characterAssemblies: CharacterAssemblies | null;
  isLoadingAssembly: boolean;
  isLoadingNetwork: boolean;
  isLoadingInventory: boolean;
  isLoadingAssets: boolean;
  tenant: string;
  refetch: () => void;
}

const EntityContext = createContext<EntityContextValue>({
  enrichedAssembly:     null,
  networkData:          null,
  inventoryData:        null,
  characterAssemblies:  null,
  isLoadingAssembly:    false,
  isLoadingNetwork:     false,
  isLoadingInventory:   false,
  isLoadingAssets:      false,
  tenant:               'utopia',
  refetch:              () => {},
});

// ---------------------------------------------------------------------------
// Fetch helper
// ---------------------------------------------------------------------------

async function fetchJson<T>(path: string): Promise<T> {
  const resp = await fetch(path);
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
  return resp.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// EntityProvider
// ---------------------------------------------------------------------------

export function EntityProvider({ children }: { children: ReactNode }) {
  const { isConnected, walletAddress } = useConnection();
  const { assembly } = useSmartObject() as { assembly: SmartAssemblyResponse | null };

  const assemblyId = assembly?.id ?? null;

  // --- Tenant resolution (priority: URL param > assembly type > /config) ---

  const urlTenant = new URLSearchParams(window.location.search).get('tenant')?.trim() || null;

  // Fetch /config only when URL param is absent (one-time, never stale)
  const configQuery = useQuery<{ tenant: string }>({
    queryKey: ['config'],
    queryFn:  () => fetchJson('/config'),
    enabled:  !urlTenant,
    staleTime: Infinity,
    retry: 1,
  });

  const assemblyTenant = deriveTeantFromAssembly(assembly);
  const tenant = urlTenant ?? assemblyTenant ?? configQuery.data?.tenant ?? '';

  // --- Entity queries ---

  // 1. Enriched assembly (depends on assemblyId + tenant)
  const assemblyQuery = useQuery<EnrichedAssembly>({
    queryKey: ['entity', 'assembly', assemblyId, tenant],
    queryFn:  () => fetchJson(`/entity/assembly/${assemblyId}?tenant=${tenant}`),
    enabled:  !!assemblyId,
    staleTime: STALE_MS,
    retry: 1,
  });

  // 2. Network node (depends on assembly having a network_node)
  const networkNodeId = assemblyQuery.data?.network_node?.id ?? null;
  const networkQuery = useQuery<NetworkData>({
    queryKey: ['entity', 'network', networkNodeId, tenant],
    queryFn:  () => fetchJson(`/entity/network/${networkNodeId}?tenant=${tenant}`),
    enabled:  !!networkNodeId,
    staleTime: STALE_MS,
    retry: 1,
  });

  // 3. Inventory (SSU only, depends on assembly type)
  const isSSU = assemblyQuery.data?.assembly_type === 'SmartStorageUnit';
  const inventoryQuery = useQuery<InventoryData>({
    queryKey: ['entity', 'inventory', assemblyId, tenant],
    queryFn:  () => fetchJson(`/entity/inventory/${assemblyId}?tenant=${tenant}`),
    enabled:  !!assemblyId && isSSU,
    staleTime: STALE_MS,
    retry: 1,
  });

  // 4. Character's assemblies — fetched directly from Sui GraphQL via dapp-kit.
  // Character name uses a tenant-aware query (getWalletCharacters hardcodes VITE_EVE_WORLD_PACKAGE_ID).
  // Owned assemblies use getCharacterAndOwnedObjects; may return empty on non-default tenant.
  const pkgId = TENANT_PACKAGE_MAP[tenant] ?? null;
  const characterProfileType = pkgId ? `${pkgId}::character::PlayerProfile` : null;

  const assetsQuery = useQuery<CharacterAssemblies>({
    queryKey: ['entity', 'character', walletAddress, assemblyId, tenant],
    queryFn:  async (): Promise<CharacterAssemblies> => {
      // Tenant-aware character name lookup
      const charNameResult = await executeGraphQLQuery(GET_WALLET_CHARACTERS, {
        owner: walletAddress!,
        characterPlayerProfileType: characterProfileType!,
      });
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const charNameJson = (charNameResult as any)?.data?.address?.objects?.nodes?.[0]
        ?.contents?.extract?.asAddress?.asObject?.asMoveObject?.contents?.json;
      const charInfo = parseCharacterFromJson(charNameJson);

      // Owned assemblies: getCharacterAndOwnedObjects uses VITE_EVE_WORLD_PACKAGE_ID;
      // will return empty on tenants that differ from the build-time env var.
      const result = await getCharacterAndOwnedObjects(walletAddress!);
      const ownedJsons = getCharacterOwnedObjectsJson(result.data) ?? [];
      const assemblies: CharacterAssembly[] = [];

      for (const asmJson of ownedJsons) {
        if (!asmJson) continue;
        const asmId = typeof asmJson.id === 'string' ? asmJson.id : '';
        if (!asmId) continue;

        const meta = asmJson.metadata as Record<string, unknown> | undefined;
        const statusObj = (asmJson.status as Record<string, unknown> | undefined)
          ?.status as Record<string, unknown> | undefined;
        const variant = statusObj?.['@variant'] as string | undefined;

        // NetworkNode: extract fuel + connected count
        const fuelRaw = asmJson.fuel as Record<string, unknown> | null | undefined;
        let fuel_percent: number | undefined;
        let fuel_hours: number | undefined;
        let fuel_burning: boolean | undefined;
        let connected_count: number | undefined;
        if (fuelRaw && typeof fuelRaw === 'object') {
          const qty    = Number(fuelRaw.quantity ?? 0);
          const max    = Number(fuelRaw.max_capacity ?? 0);
          const rateMs = Number(fuelRaw.burn_rate_in_ms ?? 0);
          fuel_burning = Boolean(fuelRaw.is_burning);
          fuel_percent = max > 0 ? Math.round((qty / max) * 100) : 0;
          if (fuel_burning && rateMs > 0 && qty > 0) {
            fuel_hours = Math.round(qty / (3_600_000 / rateMs));
          } else {
            fuel_hours = 0;
          }
          const connIds = asmJson.connected_assembly_ids;
          connected_count = Array.isArray(connIds) ? connIds.length : 0;
        }

        // Storage: distinct item type count from inventory_keys
        const invKeys = asmJson.inventory_keys;
        const item_type_count = Array.isArray(invKeys) ? invKeys.length : undefined;

        // SmartGate: field is present (null or string) only on Gate objects.
        // null = unlinked, string = linked. Absent on all other types.
        const lgRaw = asmJson.linked_gate_id;
        const is_linked = 'linked_gate_id' in asmJson
          ? (typeof lgRaw === 'string' && lgRaw.length > 0)
          : undefined;

        // Infer assembly type from json field presence (typeRepr not available via getCharacterOwnedObjectsJson)
        const inferredType = 'linked_gate_id' in asmJson ? 'SmartGate'
          : 'fuel' in asmJson ? 'NetworkNode'
          : 'inventory_keys' in asmJson ? 'SmartStorageUnit'
          : getAssemblyType('');

        assemblies.push({
          assembly_id:   asmId,
          name:          typeof meta?.name === 'string' ? meta.name : asmId.slice(0, 10),
          assembly_type: inferredType,
          status:        variant?.toUpperCase() ?? 'UNKNOWN',
          is_current:    asmId === assemblyId,
          fuel_percent,
          fuel_hours,
          fuel_burning,
          connected_count,
          item_type_count,
          is_linked,
        });
      }

      return { character_name: charInfo?.name ?? '', assemblies };
    },
    enabled:  isConnected && !!walletAddress && !!assemblyId && !!characterProfileType,
    staleTime: STALE_MS,
    retry: 1,
  });

  const value: EntityContextValue = {
    enrichedAssembly:    assemblyQuery.data    ?? null,
    networkData:         networkQuery.data     ?? null,
    inventoryData:       inventoryQuery.data   ?? null,
    characterAssemblies: assetsQuery.data      ?? null,
    isLoadingAssembly:   assemblyQuery.isLoading,
    isLoadingNetwork:    networkQuery.isLoading,
    isLoadingInventory:  inventoryQuery.isLoading,
    isLoadingAssets:     assetsQuery.isLoading,
    tenant,
    refetch: () => { assemblyQuery.refetch(); },
  };

  return (
    <EntityContext.Provider value={value}>
      {children}
    </EntityContext.Provider>
  );
}

export function useEntityContext(): EntityContextValue {
  return useContext(EntityContext);
}
