// src/utils/baselineBuilder.ts
// Pure function to construct BaselinePanelData from session and enriched assembly state.

import type { BaselinePanelData } from '../types/terminal';
import type { EnrichedAssembly } from '../context/EntityContext';

export function buildBaselineData(
  walletAddress: string | null | undefined,
  assemblyId: string | undefined,
  visitorName: string,
  tier: string,
  location: string,
  enrichedAssembly: EnrichedAssembly | null,
): BaselinePanelData {
  const en = enrichedAssembly;
  const nn = en?.network_node;
  return {
    crudVersion: 'HUGINN - Version',
    signature: walletAddress || '[REDACTED]',
    shellName: visitorName || '[REDACTED]',
    accessLevel: tier,
    assemblySignature: assemblyId || '[REDACTED]',
    location,
    ownerCharacterName: en?.owner?.character_name,
    ownerTribeId: en?.owner?.tribe_id ? String(en.owner.tribe_id) : undefined,
    ownerTribeName: en?.owner?.tribe_name || undefined,
    networkNodeName: nn?.name,
    fuelPercent: nn ? `${nn.fuel_percent.toFixed(0)}%` : undefined,
    fuelQuantity: nn?.fuel_quantity,
    fuelEffectiveMax: nn?.fuel_effective_max,
    fuelDaysRemaining: nn ? `${(nn.fuel_hours_remaining / 24).toFixed(1)}d` : undefined,
    fuelBurning: nn ? nn.fuel_hours_remaining > 0 : undefined,
  };
}
