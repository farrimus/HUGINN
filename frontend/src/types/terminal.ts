// src/types/terminal.ts

/**
 * All tool output types and baseline panel data
 */

export interface BaselinePanelData {
  crudVersion: string;
  signature: string;
  shellName: string;
  accessLevel: string;
  assemblySignature: string;
  location: string;
  // Optional enrichment (Phase 5) — absent while loading, panel degrades gracefully
  gameTypeName?: string;
  gameTypeCategory?: string;
  ownerCharacterName?: string;
  ownerTribeId?: string;
  ownerTribeName?: string;
  networkNodeName?: string;
  fuelPercent?: string;
  fuelQuantity?: number;
  fuelEffectiveMax?: number;
  fuelDaysRemaining?: string;
  fuelBurning?: boolean;
  enrichmentLoading?: boolean;
}

export interface SystemIntelData {
  systemId?: number;
  system: string;
  starClass: string;
  minTemp: string;
  planets: string;
  lagrangePoints?: string;
  hzPlanets?: string;
  kills24h: string;
  gates: string;
}

export interface ThreatAssessmentData {
  level: string;
  topAggressor: string;
  dominantShip: string;
  escalation: string;
}

export interface PilotProfileData {
  // These string fields come from the EVE World API and may contain date/timestamp strings
  visits: string;
  firstVisit: string;
  lastVisit: string;
  tier: string;
}

export interface MemorySearchData {
  query: string;
  results: string[];
}

export interface MemorySummaryData {
  attacks: string;
  contacts: string;
  docking: string;
}

// ---------------------------------------------------------------------------
// Entity panel data types (Phases 5–9)
// ---------------------------------------------------------------------------

export interface NetworkMapData {
  nodeId: string;
  nodeName: string;
  nodeStatus: string;
  currentAssemblyId: string;
  currentAssemblyName: string;
  fuel: {
    quantity: string;
    maxCapacity: string;
    fuelPercent: number;
    hoursRemaining: number;
    burnRateUnitsPerHr: number;
    isBurning: boolean;
  };
  energy: {
    currentEnergyProduction: string;
    maxEnergyProduction: string;
    totalReservedEnergy: string;
    energyPercent: number;
  };
  connectedAssemblies: Array<{
    id: string;
    name: string;
    assemblyType: string;
    status: string;
    typeId: string;
    key: unknown;
    groupName: string;
    categoryName: string;
  }>;
  truncated: boolean;
}

export interface NodesListEntry {
  id: string;
  name: string;
  status: string;
  fuelPercent: number;
  hoursRemaining: number;
  isBurning: boolean;
  connectedCount: number;
  systemName: string;
}

export interface NodesListData {
  nodes: NodesListEntry[];
  count: number;
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

export interface GateInfoData {
  gateId: string;
  gateName: string;
  gateStatus: string;
  destinationGate: {
    id: string;
    name: string | null;
    status: string | null;
  } | null;
}

export interface RouteHop {
  from: string;
  to: string;
  type: 'gate' | 'direct';
  distance_ly: number;
  dest_temp: number;
  dest_planets: number;
}

export interface RouteData {
  path: string[];
  path_ids: number[];
  jumps: number;
  jump_types: string[];
  total_ly: number;
  fuel_used: number;
  fuel_remaining: number;
  hot_systems: string[];
  warnings: string[];
  hops?: RouteHop[];
  origin_temp?: number;
  alternative?: RouteData | null;
  cost_mode?: string;
}

export interface AssetMapData {
  characterName: string;
  assemblies: Array<{
    assembly_id: string;
    name: string;
    assembly_type: string;
    status: string;
    is_current: boolean;
    fuel_percent?: number;
    fuel_hours?: number;
    fuel_burning?: boolean;
    connected_count?: number;
    item_type_count?: number;
    is_linked?: boolean;
  }>;
}

export interface WatchRule {
  id: string;
  wallet_address: string;
  ssu_id: string;
  ssu_name: string | null;
  item_filter: string | null;
  threshold: number;
  scope: string;
  last_checked: string | null;
  last_alert: string | null;
  active: boolean;
}

export interface CourierContract {
  id: string;
  poster_wallet: string;
  poster_name: string;
  item_description: string;
  from_location: string;
  to_location: string;
  reward_description: string;
  status: 'open' | 'claimed' | 'in_transit' | 'delivered' | 'cancelled';
  claimed_by_wallet: string | null;
  claimed_by_name: string | null;
  claimed_at: string | null;
  delivered_at: string | null;
  created_at: string;
  expires_at: string | null;
}

export interface TribePresenceMember {
  wallet_address: string;
  character_name: string;
  location: string;
  status: string;
  last_ping: string;
}

export interface TribePost {
  id: string;
  tribe_id: number;
  poster_wallet: string;
  poster_name: string;
  message: string;
  created_at: string;
}

export interface HuginnNewsData {
  text: string;
  generated_at: string;
}

export interface BuildOptionsData {
  canBuildNow: string[];
  almostBuildable: Array<{
    name: string;
    shortfalls: Record<string, number>;
    pctReady: number;
  }>;
  fieldDeployables: string[];
  hasNetwork: boolean;
  lagrangePoints: number;
  networkNodeStatus: string;
  networkNodeShortfalls: Record<string, number>;
  targetName?: string;
  targetMaterials?: Record<string, number>;
  targetBuildable?: boolean;
  buildOrder?: Array<{
    step: number;
    name: string;
    status: 'can_build' | 'need_materials' | 'blocked';
    note: string;
    shortfalls: Record<string, number>;
    pctReady: number;
  }>;
}

export interface WatcherAlert {
  rule_id: string;
  ssu_id: string;
  ssu_name: string;
  item_filter: string | null;
  threshold: number;
  current_count: number;
  timestamp: string;
}

export type ToolOutputData =
  | BaselinePanelData
  | SystemIntelData
  | ThreatAssessmentData
  | PilotProfileData
  | MemorySearchData
  | MemorySummaryData
  | NetworkMapData
  | InventoryData
  | GateInfoData
  | AssetMapData
  | RouteData
  | HuginnNewsData
  | NodesListData
  | BuildOptionsData;

export type ToolType =
  | 'baseline'
  | 'system_intel'
  | 'threat_assessment'
  | 'pilot_profile'
  | 'memory_search'
  | 'memory_summary'
  | 'network_map'
  | 'inventory'
  | 'gate_info'
  | 'asset_map'
  | 'route_planned'
  | 'huginn_news'
  | 'nodes_list'
  | 'build_options';

export interface ToolResult {
  toolName: ToolType;
  data: ToolOutputData;
}

export interface SSEMessage {
  text?: string;
  tool?: ToolType;
  tool_result?: ToolResult;
  visual?: string;
}

export interface CharacterData {
  wallet: string;
  character: {
    id: number;
    name: string;
  };
  owned_structures: {
    [key: string]: string[];
  };
  total_structures: number;
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}
