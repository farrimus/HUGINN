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

export interface ToolDef {
  name: string;
  label: string;
  defaultOn: boolean;
}

export const TOOLS: ToolDef[] = [
  { name: 'search_memory',      label: 'Search Memory',   defaultOn: true  },
  { name: 'get_memory_summary', label: 'Memory Summary',  defaultOn: true  },
  { name: 'assess_threat',      label: 'Assess Threat',   defaultOn: true  },
  { name: 'get_system_intel',   label: 'System Intel',    defaultOn: true  },
  { name: 'get_pilot_profile',  label: 'Pilot Profile',   defaultOn: true  },
  { name: 'radius_search',      label: 'Recon Scan',      defaultOn: true  },
  { name: 'plan_route',         label: 'Plan Route',      defaultOn: true  },
  { name: 'manage_watcher',     label: 'Manage Watches',  defaultOn: false },
  { name: 'manage_courier',     label: 'Manage Courier',  defaultOn: false },
  { name: 'manage_tribe',       label: 'Manage Tribe',    defaultOn: false },
  { name: 'log_intel',          label: 'Log Intel',       defaultOn: true  },
  { name: 'query_intel',        label: 'Query Intel',     defaultOn: true  },
  { name: 'lookup_item_type',   label: 'Item Lookup',     defaultOn: true  },
];

export type ToolFlags = Record<string, boolean>;

function defaultFeatureFlags(): FeatureFlags {
  return Object.fromEntries(Object.entries(FEATURES).map(([k, v]) => [k, v.defaultOn]));
}

function defaultToolFlags(): ToolFlags {
  return Object.fromEntries(TOOLS.map(t => [t.name, t.defaultOn]));
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
