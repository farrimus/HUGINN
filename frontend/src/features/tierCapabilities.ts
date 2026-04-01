/**
 * frontend/src/features/tierCapabilities.ts
 *
 * Frontend mirror of src/tier_capabilities.py.
 * When you change nav_items or permissions in the Python file, update this too.
 */

interface TierDef {
  label: string;
  canSignal: boolean;
  canAdmin: boolean;
  /** Feature keys this tier can see in the nav bar (admin flags still gate on/off) */
  navItems: string[];
}

export const TIER_CAPABILITIES: Record<string, TierDef> = {
  NONE: {
    label:     'Guest',
    canSignal: false,
    canAdmin:  false,
    navItems:  ['recon', 'route', 'upload'],
  },
  VETTED: {
    label:     'Vetted Pilot',
    canSignal: false,
    canAdmin:  false,
    navItems:  ['recon', 'route', 'upload'],
  },
  TRIBE: {
    label:     'Tribe Member',
    canSignal: true,
    canAdmin:  false,
    navItems:  [
      'recon', 'route', 'upload',
      'network', 'inventory', 'assets', 'nodes',
      'signal', 'board', 'tribe', 'courier', 'watches',
    ],
  },
  OWNER: {
    label:     'Owner',
    canSignal: true,
    canAdmin:  true,
    navItems:  [
      'recon', 'route', 'upload',
      'network', 'inventory', 'assets', 'nodes',
      'signal', 'board', 'tribe', 'courier', 'watches',
    ],
  },
};

function getTier(tier: string): TierDef {
  return TIER_CAPABILITIES[tier] ?? TIER_CAPABILITIES['NONE'];
}

export function canAccess(tier: string, permission: 'canSignal' | 'canAdmin'): boolean {
  return getTier(tier)[permission];
}

/**
 * Returns nav items that are both tier-allowed and admin-enabled.
 * Replaces getActiveNavItems() — call this instead.
 */
export function getActiveNavItemsForTier(
  tier: string,
  featureFlags: Record<string, boolean>,
  features: Record<string, { nav: string | null; command: string }>,
): Array<{ label: string; command: string }> {
  const allowed = new Set(getTier(tier).navItems);
  return Object.entries(features)
    .filter(([key, def]) =>
      def.nav !== null &&
      featureFlags[key] !== false &&
      allowed.has(key)
    )
    .map(([, def]) => ({ label: def.nav!, command: def.command }));
}
