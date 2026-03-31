/**
 * Ship and fuel catalog — mirrors src/ship_profile.py.
 * Keep in sync with the backend when values change.
 */

export interface FuelDef {
  quality: number;
  mass_kg: number;
  volume_m3: number;
  category: 'basic' | 'advanced';
}

export interface ShipDef {
  class_name: string;
  fuel_category: 'basic' | 'advanced';
  mass: number;
  specific_heat: number;
  fuel_capacity: number;
}

export const FUELS: Record<string, FuelDef> = {
  'D1':     { quality: 0.10, mass_kg: 20, volume_m3: 0.28, category: 'basic' },
  'D2':     { quality: 0.15, mass_kg: 30, volume_m3: 0.28, category: 'basic' },
  'SOF-40': { quality: 0.40, mass_kg: 25, volume_m3: 0.28, category: 'advanced' },
  'EU-40':  { quality: 0.40, mass_kg: 25, volume_m3: 0.28, category: 'advanced' },
  'SOF-80': { quality: 0.80, mass_kg: 30, volume_m3: 0.28, category: 'advanced' },
  'EU-90':  { quality: 0.90, mass_kg: 30, volume_m3: 0.28, category: 'advanced' },
};

export const BASE_FUEL_QUALITY: Record<string, number> = {
  basic: 0.10,
  advanced: 0.40,
};

export const SHIPS: Record<string, ShipDef> = {
  // Corvettes / basic fuel
  Carom:   { class_name: 'Corvette',             fuel_category: 'basic',    mass: 7_200_000,     specific_heat: 8.5, fuel_capacity: 3000   },
  Stride:  { class_name: 'Corvette',             fuel_category: 'basic',    mass: 7_900_000,     specific_heat: 8.0, fuel_capacity: 3200   },
  Wend:    { class_name: 'Shuttle',              fuel_category: 'basic',    mass: 6_800_000,     specific_heat: 1.0, fuel_capacity: 200    },
  Reflex:  { class_name: 'Corvette',             fuel_category: 'basic',    mass: 9_750_000,     specific_heat: 3.0, fuel_capacity: 1750   },
  Recurve: { class_name: 'Corvette',             fuel_category: 'basic',    mass: 10_400_000,    specific_heat: 1.0, fuel_capacity: 970    },
  Reiver:  { class_name: 'Corvette',             fuel_category: 'basic',    mass: 10_200_000,    specific_heat: 1.0, fuel_capacity: 1416   },
  // Frigates / advanced fuel
  Lai:     { class_name: 'Frigate',              fuel_category: 'advanced', mass: 18_929_160,    specific_heat: 2.5, fuel_capacity: 2400   },
  USV:     { class_name: 'Frigate',              fuel_category: 'advanced', mass: 30_266_600,    specific_heat: 1.8, fuel_capacity: 2420   },
  Lorha:   { class_name: 'Frigate',              fuel_category: 'advanced', mass: 31_369_320,    specific_heat: 2.5, fuel_capacity: 2508   },
  MCF:     { class_name: 'Frigate',              fuel_category: 'advanced', mass: 52_313_800,    specific_heat: 2.5, fuel_capacity: 6548   },
  HAF:     { class_name: 'Frigate',              fuel_category: 'advanced', mass: 81_883_000,    specific_heat: 2.5, fuel_capacity: 4184   },
  // Destroyer
  Tades:   { class_name: 'Destroyer',            fuel_category: 'advanced', mass: 74_655_504,    specific_heat: 2.5, fuel_capacity: 5972   },
  // Cruiser
  Maul:    { class_name: 'Cruiser',              fuel_category: 'advanced', mass: 548_435_968,   specific_heat: 2.5, fuel_capacity: 24160  },
  // Combat Battlecruiser
  Chumaq:  { class_name: 'Combat Battlecruiser', fuel_category: 'advanced', mass: 1_739_489_520, specific_heat: 3.0, fuel_capacity: 270585 },
};

/** Quality multiplier relative to the ship's minimum fuel type. */
export function qualityFactor(fuelType: string): number {
  const fuel = FUELS[fuelType];
  if (!fuel) return 1.0;
  const base = BASE_FUEL_QUALITY[fuel.category] ?? fuel.quality;
  return base > 0 ? fuel.quality / base : 1.0;
}

/** Fuel options valid for a given ship's fuel_category, ordered by quality. */
export function fuelsForShip(ship: ShipDef): string[] {
  return Object.keys(FUELS).filter(k => FUELS[k].category === ship.fuel_category);
}
