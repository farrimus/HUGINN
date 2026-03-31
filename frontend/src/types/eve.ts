/**
 * EVE Frontier game data types — TypeScript interfaces.
 *
 * Three sources:
 *   World API  — REST responses from world-api-{tenant}.*.evefrontier.com
 *   Blockchain — On-chain Move struct data via Sui GraphQL
 *   Derived    — Computed/transformed by our backend or dapp-kit utilities
 *
 * For GraphQL query response wrappers see: @evefrontier/dapp-kit/graphql/types
 * For raw on-chain types (RawSuiObjectData, RawCharacterData) see the same.
 * This file adds the *domain* layer on top — what you actually work with in UI code.
 */

// ===========================================================================
// WORLD API — Primitives
// ===========================================================================

/** Galactic coordinate (large integers, metre-scale). Source: World API */
export interface Location3D {
  x: number;
  y: number;
  z: number;
}

// ===========================================================================
// WORLD API — Solar Systems
// ===========================================================================

/** Lightweight solar system (list endpoints and gate link destinations). */
export interface SolarSystem {
  id: number;
  name: string;
  constellationId: number;
  regionId: number;
  location: Location3D;
}

/** A gate connection from a solar system to a destination. */
export interface GateLink {
  id: number;
  name: string;
  location: Location3D;
  destination: SolarSystem;
}

/** Full solar system with gate connections. Source: /v2/solarsystems/{id} */
export interface DetailedSolarSystem extends SolarSystem {
  gateLinks: GateLink[];
}

// ===========================================================================
// WORLD API — Game Types (item/structure type catalogue)
// ===========================================================================

/**
 * Item or structure type from /v2/types.
 *
 * Known groupName values: "Storage", "Frigate", "Destroyer", "Cruiser",
 * "Combat Battlecruiser", "Plasma Weapon", "Mass Driver Weapon", etc.
 * Known categoryName values: "Deployable", "Ship", "Module", "Charge", etc.
 */
export interface GameType {
  id: number;
  name: string;
  description: string;
  mass?: number;
  radius?: number;
  volume?: number;
  portionSize?: number;
  groupName?: string;
  groupId?: number;
  categoryName?: string;
  categoryId?: number;
  iconUrl?: string;
  attributes: Record<string, unknown>;
}

// ===========================================================================
// WORLD API — Ships
// ===========================================================================

export interface ShipSlots {
  high: number;
  medium: number;
  low: number;
}

export interface ShipHealth {
  shield: number;
  armor: number;
  structure: number;
}

export interface ShipHeat {
  heatCapacity: number;
  conductance: number;
}

export interface ShipPhysics {
  mass: number;
  maximumVelocity: number;
  inertiaModifier: number;
  heat: ShipHeat;
}

export interface DamageLayer {
  emDamage: number;
  thermalDamage: number;
  kineticDamage: number;
  explosiveDamage: number;
}

export interface ShipResistances {
  shield: DamageLayer;
  armor: DamageLayer;
  structure: DamageLayer;
}

export interface ShipCapacitor {
  capacity: number;
  rechargeRate: number;
}

/** Full ship type from /v2/ships/{id}. */
export interface Ship {
  id: number;
  name: string;
  classId: number;
  className: string;
  description: string;
  slots: ShipSlots;
  health: ShipHealth;
  physics: ShipPhysics;
  damageResistances: ShipResistances;
  fuelCapacity: number;
  cpuOutput: number;
  powergridOutput: number;
  capacitor: ShipCapacitor;
}

// ===========================================================================
// WORLD API — Jumps (character location history)
// ===========================================================================

/** Ship instance reference inside a Jump. */
export interface ShipRef {
  instanceId: number;
  typeId: number;
}

/**
 * Gate jump record from /v2/characters/me/jumps.
 *
 * The latest jump's `destination` is the player's current system.
 * Requires BearerAuth (player JWT). `id` is a UNIX millisecond timestamp.
 */
export interface Jump {
  id: number;
  time: string;
  origin: SolarSystem;
  destination: SolarSystem;
  ship: ShipRef;
}

// ===========================================================================
// WORLD API — Tribes & Constellations
// ===========================================================================

/** Player or NPC corporation from /v2/tribes. */
export interface Tribe {
  id: number;
  name: string;
  nameShort: string;
  description: string;
  taxRate: number;
  tribeUrl: string;
}

/** Constellation from /v2/constellations/{id}. */
export interface Constellation {
  id: number;
  name: string;
  regionId: number;
  location: Location3D;
  solarSystems: SolarSystem[];
}

// ===========================================================================
// WORLD API — Paginated list wrapper
// ===========================================================================

/** Generic paginated response envelope from World API list endpoints. */
export interface WorldApiPage<T> {
  data: T[];
  metadata: {
    total: number;
    offset?: number;
    limit?: number;
  };
}

// ===========================================================================
// BLOCKCHAIN — Move struct types (via Sui GraphQL JSON)
// ===========================================================================

/**
 * Deterministic game-derived key for any on-chain object.
 * Appears as `key` on assemblies, characters, etc.
 */
export interface TenantItemId {
  item_id: string;
  tenant: string;  // "utopia" | "stillness"
}

/** Status enum discriminant. `@variant` is the string tag. */
export interface AssemblyStatusVariant {
  "@variant": "ONLINE" | "OFFLINE" | string;
}

/** Status wrapper object on a structure. */
export interface AssemblyStatusData {
  assembly_id?: string;
  item_id?: string;
  type_id?: string;
  status: AssemblyStatusVariant;
}

/** Metadata attached to assemblies and characters. */
export interface AssemblyMetadata {
  assembly_id: string;
  name: string;
  description: string;
  url: string;
}

/** On-chain location (hashed — not a raw 3D coordinate). */
export interface AssemblyLocation {
  location_hash: string;
  structure_id: string;
}

/**
 * Fuel data for Network Nodes.
 * All numeric values are u64 serialised as strings on-chain.
 */
export interface AssemblyFuel {
  max_capacity: string;
  burn_rate_in_ms: string;
  type_id: string;
  unit_volume: string;
  quantity: string;
  is_burning: boolean;
  previous_cycle_elapsed_time: string;
  burn_start_time: string;
  last_updated: string;
}

/** Energy source data for Network Nodes (all u64 as strings). */
export interface AssemblyEnergySource {
  max_energy_production: string;
  current_energy_production: string;
  total_reserved_energy: string;
}

/**
 * Domain-level assembly/structure object.
 *
 * This is the *processed* form — parse RawSuiObjectData and cast to this.
 * Optional fields are type-specific:
 *   linked_gate_id       → SmartGate only
 *   energy_source_id     → NetworkNode only
 *   fuel, energy_source  → NetworkNode only
 *   connected_assembly_ids → NetworkNode only
 *   inventory_keys       → StorageUnit
 */
export interface Assembly {
  id: string;                              // Sui object ID (0x...)
  type_id: string;                         // u64 game type as string
  extension?: unknown;
  key?: TenantItemId;
  inventory_keys?: string[];
  linked_gate_id?: string;
  energy_source_id?: string;
  location?: AssemblyLocation;
  metadata?: AssemblyMetadata;
  owner_cap_id?: string;
  status?: AssemblyStatusData;
  fuel?: AssemblyFuel;
  energy_source?: AssemblyEnergySource;
  connected_assembly_ids?: string[];
}

/**
 * Raw on-chain Character object (Move struct).
 *
 * The character object holds OwnerCaps for all assemblies the player owns.
 * Note: this mirrors RawCharacterData from @evefrontier/dapp-kit/graphql/types
 * but as a domain type rather than a GraphQL response shape.
 */
export interface Character {
  id: string;               // Sui object ID (0x...)
  key: TenantItemId;
  tribe_id: number;
  character_address: string;  // Sui wallet address (0x...)
  metadata: AssemblyMetadata;
  owner_cap_id: string;
}

/**
 * Processed/transformed character — human-friendly, post-transform.
 *
 * Source: dapp-kit transformToCharacter() or backend /character endpoint.
 * `character_id` is the integer game ID (parsed from TenantItemId.item_id).
 */
export interface CharacterInfo {
  id: string;           // Sui object ID
  address: string;      // wallet address
  name: string;
  tribeId: number;
  characterId: number;  // game integer ID
}

/**
 * OwnerCap — authorises control of one assembly.
 *
 * The OwnerCap lives on the Character object (not the wallet directly).
 * `authorized_object_id` == the Assembly's Sui object ID.
 */
export interface OwnerCap {
  id: string;
  authorized_object_id: string;
}

// ===========================================================================
// DERIVED — Our backend response types
// ===========================================================================

/** Response from GET /location/current (planned endpoint). */
export interface CurrentLocation {
  system_name: string;
  system_id: number;
  location: Location3D;
}
