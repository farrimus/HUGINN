// src/hooks/useSponsoredTx.ts
//
// Wraps useSponsoredTransaction + useNotification into a runTx helper shared by
// GateUI and TurretUI. Handles blockchain dispatch and success/error notifications.
// onLog is passed per-call (not at hook init) so components can pass their own log
// function without hook ordering constraints.
//
// Usage:
//   const { runTx, txPending } = useSponsoredTx({ assembly, isReady });
//   await runTx(action, label, addLog);

import {
  useSponsoredTransaction,
  useNotification,
  Assemblies,
  SponsoredTransactionActions,
  Severity,
  getTxUrl,
  type SmartAssemblyResponse,
  type AssemblyType,
} from '@evefrontier/dapp-kit';
import { useEntityContext } from '../context/EntityContext';

type LogFn = (text: string, kind?: 'info' | 'error') => void;

interface UseSponsoredTxOpts {
  assembly: SmartAssemblyResponse | null;
  isReady: boolean;
}

export function useSponsoredTx({ assembly, isReady }: UseSponsoredTxOpts) {
  const { mutateAsync: sendTx, isPending: txPending } = useSponsoredTransaction();
  const { notify } = useNotification();
  const { tenant } = useEntityContext();

  const runTx = async (
    action: SponsoredTransactionActions,
    label: string,
    onLog: LogFn,
    metadata?: { name?: string },
  ): Promise<void> => {
    if (!assembly || txPending || !isReady) return;
    try {
      const result = await sendTx({
        txAction: action,
        assembly: assembly as AssemblyType<Assemblies>,
        tenant,
        metadata,
      });
      notify({ type: Severity.Success, txHash: getTxUrl('sui:testnet', result.digest) });
      onLog(`${label} confirmed. Tx: ${result.digest.slice(0, 12)}...`);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      notify({ type: Severity.Error, message: msg });
      onLog(`Error: ${msg}`, 'error');
    }
  };

  return { runTx, txPending };
}
