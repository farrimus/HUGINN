import { useState, useRef, useEffect } from 'react';
import {
  SponsoredTransactionActions,
  parseStatus,
  State,
  abbreviateAddress,
} from '@evefrontier/dapp-kit';
import { useCompanionStream } from '../hooks/useCompanionStream';
import { useEntityContext } from '../context/EntityContext';
import { useWalletReady } from '../hooks/useWalletReady';
import { useSponsoredTx } from '../hooks/useSponsoredTx';
import { useChatPayload } from '../hooks/useChatPayload';
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
  const {
    isConnected, walletAddress, handleConnect, hasEveVault,
    assembly, assemblyOwner, assemblyId, isReady,
  } = useWalletReady();
  const { sendMessage } = useCompanionStream();
  const { enrichedAssembly } = useEntityContext();

  const characterName = assemblyOwner?.name;
  const { runTx, txPending } = useSponsoredTx({ assembly, isReady });
  const { buildPayload } = useChatPayload({ characterName });

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

  // AI query helper — fires a canned message to companion stream
  const runQuery = async (message: string) => {
    if (!isReady || isQuerying) return;
    setIsQuerying(true);
    addResponse(`> ${message}`, 'info');
    let textBuffer = '';
    await sendMessage(
      buildPayload(message, {
        assembly_type: 'SmartTurret',
        assembly_state: state,
        entity_snapshot: { assembly: enrichedAssembly, network: null, inventory: null },
      }),
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
          onClick={() => { addResponse('Submitting: BRING ONLINE...', 'info'); runTx(SponsoredTransactionActions.BRING_ONLINE, 'BRING ONLINE', addResponse); }}
          disabled={!isReady || txPending}
        >
          {txPending ? 'PROCESSING...' : '[ BRING ONLINE ]'}
        </button>

        <button
          className={`turret-btn danger ${txPending ? 'tx-pending' : ''}`}
          onClick={() => { addResponse('Submitting: BRING OFFLINE...', 'info'); runTx(SponsoredTransactionActions.BRING_OFFLINE, 'BRING OFFLINE', addResponse); }}
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
