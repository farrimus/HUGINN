import { useSmartObject, Assemblies, type SmartAssemblyResponse } from '@evefrontier/dapp-kit';
import { TerminalUI } from './TerminalUI';
import { GateUI } from './GateUI';
import { TurretUI } from './TurretUI';

/**
 * Dispatches to the correct layout based on assembly type from dapp-kit.
 * Falls back to TerminalUI (SSU) while loading or for unknown types.
 */
export function StructureRouter() {
  const { assembly } = useSmartObject() as { assembly: SmartAssemblyResponse | null };

  if (assembly?.type === Assemblies.SmartGate) return <GateUI />;
  if (assembly?.type === Assemblies.SmartTurret) return <TurretUI />;
  return <TerminalUI />;
}
