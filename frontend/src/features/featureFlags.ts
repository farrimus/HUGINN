// Feature and tool flag configuration — drives /admin panel, nav bar, and command guards.

export interface FeatureDef {
  label: string;       // shown in /admin feature list
  nav: string | null;  // nav bar button label, null = no nav button
  command: string;     // slash command this feature maps to
  defaultOn: boolean;
}

export const FEATURES: Record<string, FeatureDef> = {
  recon:     { label: 'RECON',       nav: 'RECON',      command: '/recon',     defaultOn: true  },
  route:     { label: 'ROUTE',       nav: 'ROUTE',      command: '/route',     defaultOn: true  },
  upload:    { label: 'UPLOAD',      nav: 'UPLOAD',     command: '/upload',    defaultOn: true  },
  network:   { label: 'NETWORK',     nav: 'NETWORK',    command: '/network',   defaultOn: false },
  inventory: { label: 'INVENTORY',   nav: 'INVENTORY',  command: '/inventory', defaultOn: false },
  assets:    { label: 'ASSETS',      nav: 'ASSETS',     command: '/assets',    defaultOn: false },
  nodes:     { label: 'NODES SCAN',  nav: null,         command: '/nodes',     defaultOn: false },
  signal:    { label: 'HUGINN NEWS', nav: 'HUGINN',     command: '/signal',    defaultOn: false },
  board:     { label: 'TRIBE BOARD', nav: 'TRIBE',      command: '/board',     defaultOn: false },
  tribe:     { label: 'TRIBE ROLL',  nav: null,         command: '/tribe',     defaultOn: false },
  courier:   { label: 'COURIER',     nav: null,         command: '/courier',   defaultOn: false },
  watches:   { label: 'WATCHES',     nav: null,         command: '/watches',   defaultOn: false },
};

export type FeatureFlags = Record<string, boolean>;

// ---------------------------------------------------------------------------
// Tool registry — server-driven. Frontend maintains labels + a static fallback.
// ---------------------------------------------------------------------------

export interface ToolRegistryEntry {
  name: string;
  category: string;
  default_enabled: boolean;
}

// Human-readable labels for known tools. Auto-formats unknown names as fallback.
const TOOL_LABELS: Record<string, string> = {
  search_memory:            'Search Memory',
  get_memory_summary:       'Memory Summary',
  assess_threat:            'Assess Threat',
  get_system_intel:         'System Intel',
  get_pilot_profile:        'Pilot Profile',
  radius_search:            'Recon Scan',
  plan_route:               'Plan Route',
  recon_scan:               'Full Recon',
  manage_watcher:           'Manage Watches',
  manage_courier:           'Manage Courier',
  manage_tribe:             'Manage Tribe',
  tribe_presence:           'Tribe Presence',
  log_intel:                'Log Intel',
  query_intel:              'Query Intel',
  lookup_item_type:         'Item Lookup',
  calculate_build_options:  'Build Calculator',
  record_field_observation: 'Field Observation',
  query_system_knowledge:   'System Knowledge',
};

export function formatToolLabel(name: string): string {
  if (TOOL_LABELS[name]) return TOOL_LABELS[name];
  return name.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

// Static fallback — used when /admin/tool-registry is unreachable.
// Matches server defaults. New tools added server-side don't need an entry here.
export const TOOL_DEFAULTS: Record<string, boolean> = {
  search_memory:            true,
  get_memory_summary:       true,
  assess_threat:            true,
  get_system_intel:         true,
  get_pilot_profile:        true,
  radius_search:            true,
  plan_route:               true,
  recon_scan:               true,
  manage_watcher:           false,
  manage_courier:           false,
  manage_tribe:             false,
  log_intel:                true,
  query_intel:              true,
  lookup_item_type:         true,
  calculate_build_options:  true,
  record_field_observation: true,
  query_system_knowledge:   true,
};

export type ToolFlags = Record<string, boolean>;

export function defaultFeatureFlags(): FeatureFlags {
  return Object.fromEntries(Object.entries(FEATURES).map(([k, v]) => [k, v.defaultOn]));
}

export function defaultToolFlags(): ToolFlags {
  return { ...TOOL_DEFAULTS };
}

export function loadFeatureFlags(assemblyId: string): FeatureFlags {
  try {
    const raw = localStorage.getItem(`features_${assemblyId}`);
    if (raw) return { ...defaultFeatureFlags(), ...JSON.parse(raw) };
  } catch { /* ignore */ }
  return defaultFeatureFlags();
}

export function saveFeatureFlags(assemblyId: string, flags: FeatureFlags): void {
  localStorage.setItem(`features_${assemblyId}`, JSON.stringify(flags));
}

export function loadToolFlags(assemblyId: string): ToolFlags {
  try {
    const raw = localStorage.getItem(`tools_${assemblyId}`);
    if (raw) return { ...defaultToolFlags(), ...JSON.parse(raw) };
  } catch { /* ignore */ }
  return defaultToolFlags();
}

export function saveToolFlags(assemblyId: string, flags: ToolFlags): void {
  localStorage.setItem(`tools_${assemblyId}`, JSON.stringify(flags));
}

export function getDisabledTools(flags: ToolFlags): string[] {
  return Object.entries(flags).filter(([, v]) => !v).map(([k]) => k);
}

export function getActiveNavItems(flags: FeatureFlags): Array<{ label: string; command: string }> {
  return Object.entries(FEATURES)
    .filter(([k, v]) => flags[k] && v.nav !== null)
    .map(([, v]) => ({ label: v.nav!, command: v.command }));
}

// ---------------------------------------------------------------------------
// Global admin config cache (server is authoritative, localStorage is cache)
// ---------------------------------------------------------------------------

const ADMIN_CONFIG_CACHE_KEY = 'admin_config';

export function loadCachedAdminConfig(): { features: FeatureFlags; tools: ToolFlags } {
  try {
    const raw = localStorage.getItem(ADMIN_CONFIG_CACHE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      return {
        features: { ...defaultFeatureFlags(), ...(parsed.features || {}) },
        tools:    { ...defaultToolFlags(),    ...(parsed.tools    || {}) },
      };
    }
  } catch { /* ignore */ }
  return { features: defaultFeatureFlags(), tools: defaultToolFlags() };
}

export function saveCachedAdminConfig(config: { features: FeatureFlags; tools: ToolFlags }): void {
  localStorage.setItem(ADMIN_CONFIG_CACHE_KEY, JSON.stringify(config));
}
