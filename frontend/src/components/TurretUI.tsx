import { useState, useRef, useEffect } from 'react';
import {
  useConnection,
  useSmartObject,
  useSponsoredTransaction,
  useNotification,
  Assemblies,
  SponsoredTransactionActions,
  Severity,
  parseStatus,
  State,
  abbreviateAddress,
  getTxUrl,
  type SmartAssemblyResponse,
  type DetailedSmartCharacterResponse,
  type AssemblyType,
} from '@evefrontier/dapp-kit';
import { useCompanionStream } from '../hooks/useCompanionStream';
import { useEntityContext } from '../context/EntityContext';
import '../styles/turret.css';

interface ResponseLine {
  text: string;
  kind: 'ai' | 'info' | 'error';
  timestamp: number;
}

/**
 * Turret UI — portrait 281×886.
 * Button-driven panel: ONLINE/OFFLINE (on-chain via useSponsoredTransaction)
 * + AI query buttons (companion stream). No InfoPanel — too narrow.
 */
export function TurretUI() {
  const { isConnected, walletAddress, handleConnect, hasEveVault } = useConnection();
  const { assembly, assemblyOwner } = useSmartObject() as {
    assembly: SmartAssemblyResponse | null;
    assemblyOwner: DetailedSmartCharacterResponse | null;
  };
  const { notify } = useNotification();
  const { mutateAsync: sendTx, isPending: txPending } = useSponsoredTransaction();
  const { sendMessage } = useCompanionStream();
  const { enrichedAssembly, tenant } = useEntityContext();

  const assemblyId = assembly?.id;
  const characterName = assemblyOwner?.name;
  const itemId = new URLSearchParams(window.location.search).get('itemId') || '';
  const isReady = isConnected && !!assemblyId;

  const state = enrichedAssembly?.status ?? assembly?.state ?? 'UNKNOWN';
  const isOnline = parseStatus(state) === State.ONLINE || parseStatus(state) === State.ANCHORED;
  const turretName = enrichedAssembly?.name ?? assembly?.name ?? 'TURRET';

  const [responses, setResponses] = useState<ResponseLine[]>([
    { text: 'Turret control ready.', kind: 'info', timestamp: Date.now() },
  ]);
  const [isQuerying, setIsQuerying] = useState(false);
  const responseEndRef = useRef<HTMLDivElement>(null);
  const hasGreeted = useRef(false);

  useEffect(() => {
    responseEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [responses]);

  useEffect(() => {
    if (!isConnected && hasEveVault) handleConnect();
  }, [hasEveVault]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (isReady && !hasGreeted.current) {
      hasGreeted.current = true;
      addResponse(`Unit online. State: ${state}.`, 'info');
    }
  }, [isReady]); // eslint-disable-line react-hooks/exhaustive-deps

  const addResponse = (text: string, kind: ResponseLine['kind'] = 'ai') => {
    setResponses((prev) => [...prev, { text, kind, timestamp: Date.now() }]);
  };

  // Sponsored transaction helper
  const runTx = async (action: SponsoredTransactionActions, label: string) => {
    if (!assembly || txPending || !isReady) return;
    addResponse(`Submitting: ${label}...`, 'info');
    try {
      const result = await sendTx({
        txAction: action,
        assembly: assembly as AssemblyType<Assemblies>,
        tenant: tenant,
      });
      notify({ type: Severity.Success, txHash: getTxUrl('sui:testnet', result.digest) });
      addResponse(`${label} confirmed. Tx: ${result.digest.slice(0, 10)}...`, 'info');
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      notify({ type: Severity.Error, message: msg });
      addResponse(`Error: ${msg}`, 'error');
    }
  };

  // AI query helper — fires a canned message to companion stream
  const runQuery = async (message: string) => {
    if (!isReady || isQuerying) return;
    setIsQuerying(true);
    addResponse(`> ${message}`, 'info');
    let textBuffer = '';
    await sendMessage(
      {
        assembly_id: assemblyId!,
        message,
        history: [],
        owner_address: walletAddress || '',
        character_name: characterName || '',
        item_id: itemId,
        assembly_name: enrichedAssembly?.name ?? assembly?.name ?? '',
        assembly_type: 'SmartTurret',
        assembly_state: state,
        system_name: assembly?.solarSystem?.name || '',
        system_id: assembly?.solarSystem?.id,
        entity_snapshot: { assembly: enrichedAssembly, network: null, inventory: null },
      },
      {
        onTextChunk: (text) => { textBuffer += text; },
        onToolResult: () => {},
        onDone: () => {
          if (textBuffer) addResponse(textBuffer, 'ai');
          setIsQuerying(false);
        },
        onError: (err) => {
          addResponse(`Error: ${err.message}`, 'error');
          setIsQuerying(false);
        },
      }
    );
  };

  const stateBadgeClass = isOnline ? 'online' : 'offline';

  return (
    <div className="turret-ui">
      {/* Header */}
      <div className="turret-header">
        <h1>{turretName}</h1>
        <span className={`turret-state-badge ${stateBadgeClass}`}>
          {state.toUpperCase()}
        </span>
      </div>

      {/* Status strip */}
      <div className="turret-status-strip">
        <div className="status-item">
          <span className="status-label">SYSTEM</span>
          <span className="status-value">
            {assembly?.solarSystem?.name || '---'}
          </span>
        </div>
        <div className="status-item">
          <span className="status-label">WALLET</span>
          <span className="status-value">
            {isConnected && walletAddress ? abbreviateAddress(walletAddress, 8) : 'NONE'}
          </span>
        </div>
      </div>

      {/* Action buttons */}
      <div className="turret-buttons">
        <button
          className={`turret-btn primary ${txPending ? 'tx-pending' : ''}`}
          onClick={() => runTx(SponsoredTransactionActions.BRING_ONLINE, 'BRING ONLINE')}
          disabled={!isReady || txPending}
        >
          {txPending ? 'PROCESSING...' : '[ BRING ONLINE ]'}
        </button>

        <button
          className={`turret-btn danger ${txPending ? 'tx-pending' : ''}`}
          onClick={() => runTx(SponsoredTransactionActions.BRING_OFFLINE, 'BRING OFFLINE')}
          disabled={!isReady || txPending}
        >
          {txPending ? 'PROCESSING...' : '[ BRING OFFLINE ]'}
        </button>

        <button
          className="turret-btn"
          onClick={() => runQuery('Scan vicinity for hostiles and assess immediate threat level.')}
          disabled={!isReady || isQuerying}
        >
          [ SCAN VICINITY ]
        </button>

        <button
          className="turret-btn"
          onClick={() => runQuery('What is the current threat status in this system? Recent kills, known hostiles.')}
          disabled={!isReady || isQuerying}
        >
          [ THREAT STATUS ]
        </button>

        <button
          className="turret-btn"
          onClick={() => runQuery('Summarize recent activity in this system. Any contacts to report?')}
          disabled={!isReady || isQuerying}
        >
          [ REPORT CONTACTS ]
        </button>

        <button
          className="turret-btn"
          onClick={() => runQuery('Give me a system intel briefing: star class, planets, gate count, kill activity.')}
          disabled={!isReady || isQuerying}
        >
          [ SYSTEM INTEL ]
        </button>
      </div>

      {/* Loading indicator */}
      {isQuerying && <div className="turret-loading">QUERYING...</div>}

      {/* AI response area */}
      <div className="turret-response">
        {responses.map((r, idx) => (
          <div key={idx} className={`response-line ${r.kind}`}>
            <span className="response-timestamp">
              {new Date(r.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false })}
            </span>
            {r.text}
          </div>
        ))}
        <div ref={responseEndRef} />
      </div>

      {/* Wallet status bar */}
      <div className="turret-wallet-bar">
        <span>{assemblyId ? assemblyId.slice(0, 12) + '...' : 'No assembly'}</span>
        <span className={isConnected ? 'connected' : ''}>
          {isConnected ? 'VAULT OK' : 'NO VAULT'}
        </span>
      </div>
    </div>
  );
}
