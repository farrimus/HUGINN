import { useState, useRef, useEffect } from 'react';
import {
  useConnection,
  useSmartObject,
  useSponsoredTransaction,
  useNotification,
  Assemblies,
  SponsoredTransactionActions,
  Severity,
  type SmartAssemblyResponse,
  type AssemblyType,
} from '@evefrontier/dapp-kit';
import { useToolOutput } from '../hooks/useToolOutput';
import { useCompanionStream } from '../hooks/useCompanionStream';
import { useEntityContext } from '../context/EntityContext';
import { InfoPanel } from './InfoPanel';
import { AdminPanel } from './AdminPanel';
import {
  getDisabledTools, getActiveNavItems, FeatureFlags, ToolFlags, ToolRegistryEntry,
  loadCachedAdminConfig, saveCachedAdminConfig, defaultFeatureFlags, defaultToolFlags,
} from '../features/featureFlags';
import type { ChatMessage } from '../types/terminal';
import '../styles/terminal.css';
import '../styles/gate.css';

const API_BASE_URL = window.location.origin;

interface TerminalLog {
  text: string;
  type: 'info' | 'user' | 'ai' | 'error' | 'warning' | 'command' | 'admin';
  timestamp: number;
  action?: string;
  id?: string;
  adminFeatureFlags?: FeatureFlags;
  adminToolFlags?: ToolFlags;
}

/**
 * Gate UI — landscape 782×686.
 *
 * No header bar — all identity info lives in the InfoPanel baseline.
 * Gate actions (ONLINE/OFFLINE/LINK/UNLINK) are slash commands shown via /help,
 * rendered as clickable links in the chat log exactly like other commands.
 * This keeps the layout as two clean regions: InfoPanel + chat.
 */
export function GateUI() {
  const { isConnected, walletAddress, handleConnect, handleDisconnect, hasEveVault } = useConnection();
  const { assembly } = useSmartObject() as {
    assembly: SmartAssemblyResponse | null;
  };
  const { notify } = useNotification();
  const { mutateAsync: sendTx, isPending: txPending } = useSponsoredTransaction();
  const { currentToolType, currentData, isAnimating, display: displayToolOutput, finishAnimation } = useToolOutput();
  const { sendMessage } = useCompanionStream();
  const { enrichedAssembly, networkData, characterAssemblies, tenant } = useEntityContext();

  const assemblyId = assembly?.id;
  // Use visitor's character name from EntityContext (same source as TerminalUI's visitorName).
  // assemblyOwner?.name falls back to wallet address in dapp-kit when name is unresolved —
  // characterAssemblies?.character_name returns '' instead, so we fall back to truncated wallet.
  const characterName = characterAssemblies?.character_name || walletAddress?.slice(0, 10) || null;
  const itemId = new URLSearchParams(window.location.search).get('itemId') || '';
  const isReady = isConnected && !!assemblyId;

  // Gate link state from dapp-kit
  const gateAssembly = assembly as AssemblyType<Assemblies.SmartGate> | null;
  const destinationId = gateAssembly?.gate?.destinationId;
  const isLinked = !!destinationId;

  const [logs, setLogs] = useState<TerminalLog[]>([
    { text: 'GATE CONTROL initializing...', type: 'info', timestamp: Date.now() },
  ]);
  const [inputValue, setInputValue] = useState('');
  const [isFocused, setIsFocused] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);
  const [tier, setTier] = useState<string>('NONE');
  const [featureFlags, setFeatureFlags] = useState<FeatureFlags>(
    () => loadCachedAdminConfig().features
  );
  const [toolFlags, setToolFlags] = useState<ToolFlags>(
    () => loadCachedAdminConfig().tools
  );
  const [toolRegistry, setToolRegistry] = useState<ToolRegistryEntry[]>([]);
  const terminalEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const hasGreeted = useRef(false);

  const addLog = (text: string, type: TerminalLog['type'] = 'info', action?: string) => {
    setLogs((prev) => [...prev, { text, type, timestamp: Date.now(), action }]);
  };

  useEffect(() => {
    terminalEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  // Baseline panel — identity + fuel from network node
  useEffect(() => {
    const status = enrichedAssembly?.status ?? assembly?.state ?? '[REDACTED]';
    const location = assembly?.solarSystem?.name || '[REDACTED]';
    const en = enrichedAssembly;
    const nn = en?.network_node;

    displayToolOutput('baseline', {
      crudVersion: 'HUGINN - Gate Control',
      signature: walletAddress || '[REDACTED]',
      shellName: characterName || '[REDACTED]',
      accessLevel: status,
      assemblySignature: assemblyId || '[REDACTED]',
      location,
      ownerCharacterName: en?.owner?.character_name,
      ownerTribeId: en?.owner?.tribe_id ? String(en.owner.tribe_id) : undefined,
      ownerTribeName: en?.owner?.tribe_name || undefined,
      networkNodeName: nn?.name,
      fuelPercent: nn ? `${nn.fuel_percent.toFixed(0)}%` : undefined,
      fuelDaysRemaining: nn ? `${(nn.fuel_hours_remaining / 24).toFixed(1)}d` : undefined,
      fuelBurning: nn ? nn.fuel_hours_remaining > 0 : undefined,
    });
  }, [
    walletAddress, assemblyId, characterName,
    assembly?.state, assembly?.solarSystem?.name,
    enrichedAssembly, displayToolOutput,
  ]);

  useEffect(() => {
    if (!isConnected && hasEveVault) handleConnect();
  }, [hasEveVault]); // eslint-disable-line react-hooks/exhaustive-deps

  // Session register — resolves tier (OWNER / TRIBE / GUEST)
  useEffect(() => {
    if (!walletAddress || !assemblyId) return;
    fetch(`${API_BASE_URL}/session/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ wallet_address: walletAddress, assembly_id: assemblyId, character_name: walletAddress.slice(0, 10) }),
    })
      .then(r => r.ok ? r.json() : null)
      .then(data => { if (data?.tier) setTier(data.tier); })
      .catch(() => {});
  }, [walletAddress, assemblyId]);

  useEffect(() => {
    if (!itemId) addLog('No itemId in URL — gate cannot be identified.', 'warning');
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    Promise.all([
      fetch(`${API_BASE_URL}/admin/config`).then(r => r.ok ? r.json() : null),
      fetch(`${API_BASE_URL}/admin/tool-registry`).then(r => r.ok ? r.json() : []),
    ]).then(([configData, registry]) => {
      if (Array.isArray(registry) && registry.length > 0) {
        setToolRegistry(registry);
        const toolDefaults = Object.fromEntries(registry.map((t: ToolRegistryEntry) => [t.name, t.default_enabled]));
        const merged = {
          features: { ...defaultFeatureFlags(), ...(configData?.features || {}) },
          tools:    { ...toolDefaults,           ...(configData?.tools    || {}) },
        };
        setFeatureFlags(merged.features);
        setToolFlags(merged.tools);
        saveCachedAdminConfig(merged);
      } else if (configData) {
        const merged = {
          features: { ...defaultFeatureFlags(), ...(configData.features || {}) },
          tools:    { ...defaultToolFlags(),    ...(configData.tools    || {}) },
        };
        setFeatureFlags(merged.features);
        setToolFlags(merged.tools);
        saveCachedAdminConfig(merged);
      }
    }).catch(() => { /* keep cached state on failure */ });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (isReady && !hasGreeted.current) {
      hasGreeted.current = true;
      const linkMsg = isLinked ? `Linked → ${destinationId?.slice(0, 14)}...` : 'Unlinked.';
      addLog(`[HUGINN]: Gate systems online. ${linkMsg} Type /help for commands.`, 'ai');
    }
  }, [isReady, isLinked]); // eslint-disable-line react-hooks/exhaustive-deps

  // --- Sponsored transaction helpers ---

  const runTx = async (action: SponsoredTransactionActions, label: string, metadata?: { name?: string }) => {
    if (!assembly || txPending || !isReady) return;
    try {
      const result = await sendTx({
        txAction: action,
        assembly: assembly as AssemblyType<Assemblies>,
        tenant: tenant,
        metadata,
      });
      notify({ type: Severity.Success, txHash: result.digest });
      addLog(`${label} confirmed. ${result.digest.slice(0, 12)}...`, 'info');
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      notify({ type: Severity.Error, message: msg });
      addLog(`Error: ${msg}`, 'error');
    }
  };

  // --- Command handler ---

  const handleCommand = async (input: string) => {
    const parts = input.trim().split(/\s+/);
    const command = parts[0].toLowerCase();

    if (command === '/admin') {
      if (tier !== 'OWNER') {
        addLog('Admin access restricted to OWNER.', 'warning');
        return;
      }
      const adminId = `admin-${Date.now()}`;
      setLogs(prev => [...prev, {
        text: '',
        type: 'admin' as const,
        timestamp: Date.now(),
        id: adminId,
        adminFeatureFlags: { ...featureFlags },
        adminToolFlags: { ...toolFlags },
      }]);
      return;
    } else if (command === '/online') {
      if (!isReady || txPending) { addLog('Not ready.', 'warning'); return; }
      addLog('Submitting: BRING ONLINE...', 'info');
      await runTx(SponsoredTransactionActions.BRING_ONLINE, 'BRING ONLINE');

    } else if (command === '/offline') {
      if (!isReady || txPending) { addLog('Not ready.', 'warning'); return; }
      addLog('Submitting: BRING OFFLINE...', 'info');
      await runTx(SponsoredTransactionActions.BRING_OFFLINE, 'BRING OFFLINE');

    } else if (command === '/link') {
      if (!isReady || txPending) { addLog('Not ready.', 'warning'); return; }
      // Optional target gate ID as argument: /link 0x...
      const target = parts[1];
      addLog('Submitting: LINK GATE...', 'info');
      await runTx(
        SponsoredTransactionActions.LINK_SMART_GATE,
        'LINK GATE',
        target ? { name: target } : undefined,
      );

    } else if (command === '/unlink') {
      if (!isReady || txPending) { addLog('Not ready.', 'warning'); return; }
      if (!isLinked) { addLog('Gate is not linked.', 'warning'); return; }
      addLog('Submitting: UNLINK GATE...', 'info');
      await runTx(SponsoredTransactionActions.UNLINK_SMART_GATE, 'UNLINK GATE');

    } else if (command === '/connect') {
      isConnected ? addLog('Already connected.', 'warning') : handleConnect();

    } else if (command === '/disconnect') {
      isConnected
        ? (handleDisconnect(), addLog('Wallet disconnected.', 'info'))
        : addLog('Not connected.', 'warning');

    } else if (command === '/gate') {
      if (enrichedAssembly?.assembly_type === 'SmartGate') {
        displayToolOutput('gate_info', {
          gateId: enrichedAssembly.id,
          gateName: enrichedAssembly.name,
          gateStatus: enrichedAssembly.status,
          destinationGate: enrichedAssembly.destination_gate
            ? { id: enrichedAssembly.destination_gate.id, name: enrichedAssembly.destination_gate.name ?? null, status: enrichedAssembly.destination_gate.status ?? null }
            : null,
        });
        addLog('Gate info loaded.', 'info');
      } else {
        addLog('Gate data not yet loaded.', 'warning');
      }

    } else if (command === '/network') {
      if (!networkData) { addLog('Network data not available.', 'warning'); return; }
      displayToolOutput('network_map', {
        nodeId: networkData.id,
        nodeName: networkData.name,
        nodeStatus: networkData.status,
        currentAssemblyId: assemblyId || '',
        currentAssemblyName: enrichedAssembly?.name ?? assemblyId?.slice(0, 10) ?? '',
        fuel: {
          quantity: networkData.fuel.quantity,
          maxCapacity: networkData.fuel.max_capacity,
          fuelPercent: networkData.fuel.fuel_percent,
          hoursRemaining: networkData.fuel.hours_remaining,
          burnRateUnitsPerHr: networkData.fuel.burn_rate_units_per_hr,
          isBurning: networkData.fuel.is_burning,
        },
        energy: {
          currentEnergyProduction: networkData.energy.current_energy_production,
          maxEnergyProduction: networkData.energy.max_energy_production,
          totalReservedEnergy: networkData.energy.total_reserved_energy,
          energyPercent: networkData.energy.energy_percent,
        },
        connectedAssemblies: (networkData.connected_assemblies ?? []).map(a => ({
          id:           a.id,
          name:         a.name,
          assemblyType: a.assembly_type,
          status:       a.status,
          typeId:       a.type_id,
          key:          a.key,
          groupName:    a.group_name,
          categoryName: a.category_name,
        })),
        truncated: networkData.truncated,
      });
      addLog('Network map loaded.', 'info');

    } else if (command === '/assets') {
      if (!characterAssemblies) { addLog('Asset data not available.', 'warning'); return; }
      displayToolOutput('asset_map', { characterName: characterAssemblies.character_name, assemblies: characterAssemblies.assemblies });
      addLog('Asset map loaded.', 'info');

    } else if (command === '/nodes') {
      try {
        addLog('Scanning for network nodes...', 'info');
        const t = tenant;
        const res = await fetch(`${API_BASE_URL}/entity/nodes?tenant=${t}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const raw = await res.json();
        const nodes = (raw.nodes ?? []).map((n: any) => ({
          id:             n.id,
          name:           n.name,
          status:         n.status,
          fuelPercent:    n.fuel_percent,
          hoursRemaining: n.hours_remaining,
          isBurning:      n.is_burning,
          connectedCount: n.connected_count,
          systemName:     n.system_name,
        }));
        displayToolOutput('nodes_list', { nodes, count: nodes.length });
        addLog(`${nodes.length} network node${nodes.length !== 1 ? 's' : ''} found.`, 'info');
      } catch (err) {
        addLog(`Nodes scan failed: ${err instanceof Error ? err.message : String(err)}`, 'error');
      }

    } else if (command === '/home') {
      const en = enrichedAssembly;
      const nn = en?.network_node;
      displayToolOutput('baseline', {
        crudVersion: 'HUGINN - Gate Control',
        signature: walletAddress || '[REDACTED]',
        shellName: characterName || '[REDACTED]',
        accessLevel: en?.status ?? assembly?.state ?? '[REDACTED]',
        assemblySignature: assemblyId || '[REDACTED]',
        location: assembly?.solarSystem?.name || '[REDACTED]',
        ownerCharacterName: en?.owner?.character_name,
        ownerTribeId: en?.owner?.tribe_id ? String(en.owner.tribe_id) : undefined,
        ownerTribeName: en?.owner?.tribe_name || undefined,
        networkNodeName: nn?.name,
        fuelPercent: nn ? `${nn.fuel_percent.toFixed(0)}%` : undefined,
        fuelDaysRemaining: nn ? `${(nn.fuel_hours_remaining / 24).toFixed(1)}d` : undefined,
        fuelBurning: nn ? nn.fuel_hours_remaining > 0 : undefined,
      });

    } else if (command === '/help') {
      const t = Date.now();
      addLog('Gate commands:', 'info');
      // Gate actions — on-chain transactions
      const txCmds = [
        { text: '/online              bring gate online', action: '/online' },
        { text: '/offline             take gate offline', action: '/offline' },
        { text: '/link [gate-id]      link to destination gate', action: '/link' },
        { text: '/unlink              unlink gate', action: '/unlink' },
      ];
      // Info commands
      const infoCmds = [
        { text: '/gate                gate link info panel', action: '/gate' },
        { text: '/network             network node + fuel', action: '/network' },
        { text: '/assets              your structures', action: '/assets' },
        { text: '/home                baseline panel', action: '/home' },
        { text: '/connect             connect wallet', action: '/connect' },
        { text: '/disconnect          disconnect wallet', action: '/disconnect' },
      ];
      setLogs((prev) => [
        ...prev,
        { text: '  — actions —', type: 'info', timestamp: t },
        ...txCmds.map(({ text, action }) => ({ text: `  ${text}`, type: 'command' as const, timestamp: t, action })),
        { text: '  — info —', type: 'info', timestamp: t },
        ...infoCmds.map(({ text, action }) => ({ text: `  ${text}`, type: 'command' as const, timestamp: t, action })),
      ]);
      addLog('Everything else is sent to HUGINN.', 'info');

    } else {
      addLog(`Unknown command: ${command}`, 'error');
    }
  };

  // --- Chat ---

  const handleChatMessage = async (userInput: string) => {
    if (!isReady) { addLog('Wallet not connected or gate not identified.', 'warning'); return; }
    addLog(`[You]: ${userInput}`, 'user');
    setIsLoading(true);
    let textBuffer = '';
    await sendMessage(
      {
        assembly_id: assemblyId!,
        message: userInput,
        history: chatHistory,
        owner_address: walletAddress || '',
        character_name: characterName || '',
        item_id: itemId,
        assembly_name: enrichedAssembly?.name ?? assembly?.name ?? '',
        assembly_type: 'SmartGate',
        assembly_state: enrichedAssembly?.status ?? assembly?.state ?? '',
        system_name: assembly?.solarSystem?.name || '',
        system_id: assembly?.solarSystem?.id,
        disabled_tools: getDisabledTools(toolFlags),
        tenant: tenant,
      },
      {
        onTextChunk: (text) => { textBuffer += text; },
        onToolResult: (toolName, data) => { displayToolOutput(toolName, data); },
        onDone: () => {
          if (textBuffer) {
            addLog(`[HUGINN]: ${textBuffer}`, 'ai');
            setChatHistory((prev) => [
              ...prev,
              { role: 'user', content: userInput },
              { role: 'assistant', content: textBuffer },
            ]);
          }
          setIsLoading(false);
        },
        onError: (err) => {
          addLog(`Error: ${err.message}`, 'error');
          setIsLoading(false);
        },
      }
    );
  };

  const handlePrintNode = async (nodeId: string): Promise<void> => {
    try {
      const t = tenant;
      const res = await fetch(`${API_BASE_URL}/entity/network/${nodeId}?tenant=${t}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const net = await res.json();
      const pad = (s: string, len: number) => s.slice(0, len).padEnd(len);
      const fuelStr = net.fuel.is_burning
        ? `FUEL: ${net.fuel.fuel_percent.toFixed(0)}%`
        : 'FUEL: NOT BURNING';
      const sorted = [...(net.connected_assemblies ?? [])].sort((a: any, b: any) => {
        const aOn = a.status === 'ONLINE' ? 0 : 1;
        const bOn = b.status === 'ONLINE' ? 0 : 1;
        return aOn !== bOn ? aOn - bOn : a.name.localeCompare(b.name);
      });
      const asmLines = sorted.map((a: any) => {
        const isOff = a.status !== 'ONLINE';
        return `  ${pad((isOff ? '~' : ' ') + a.name, 24)}${pad(a.group_name || a.assembly_type, 18)}${a.status}`;
      });
      const lines = [
        `NETWORK — ${net.name} [${net.status}]   ${fuelStr}   (${sorted.length} structures)`,
        ...asmLines,
      ];
      addLog('[PRINT]: ' + lines.join('\n'), 'info');
    } catch (err) {
      addLog(`Print failed: ${err instanceof Error ? err.message : String(err)}`, 'error');
    }
  };

  const doSubmit = async () => {
    if (!inputValue.trim() || isLoading) return;
    const input = inputValue.trim();
    setInputValue('');
    if (input.startsWith('/')) await handleCommand(input);
    else await handleChatMessage(input);
  };

  return (
    <div className="gate-ui">
      {/* InfoPanel fills the top — no header stealing space */}
      <InfoPanel
        currentToolType={currentToolType}
        currentData={currentData}
        isAnimating={isAnimating}
        onAnimationEnd={finishAnimation}
        onPrintNode={handlePrintNode}
        onNavCommand={handleCommand}
        activeNavItems={getActiveNavItems(featureFlags)}
      />

      {/* Chat log */}
      <div className="terminal-output">
        {logs.map((log, idx) => (
          <div key={log.id ?? idx} className={`terminal-line line-${log.type}`}>
            {log.type === 'admin' ? (
              <AdminPanel
                featureFlags={log.adminFeatureFlags ?? featureFlags}
                toolFlags={log.adminToolFlags ?? toolFlags}
                walletAddress={walletAddress || ''}
                apiBase={API_BASE_URL}
                currentEnv={tenant}
                toolRegistry={toolRegistry}
                onApply={(newFeatures, newTools) => {
                  setFeatureFlags(newFeatures);
                  setToolFlags(newTools);
                  saveCachedAdminConfig({ features: newFeatures, tools: newTools });
                  fetch(`${API_BASE_URL}/admin/config`, {
                    method: 'PATCH',
                    headers: {
                      'Content-Type': 'application/json',
                      'X-Wallet-Address': walletAddress || '',
                    },
                    body: JSON.stringify({ features: newFeatures, tools: newTools }),
                  }).catch(() => console.warn('[ADMIN] Config save to server failed'));
                  const id = log.id;
                  setLogs(prev => prev.map(l =>
                    l.id === id ? { ...l, type: 'info' as const, text: '[ADMIN] Settings applied.' } : l
                  ));
                }}
              />
            ) : (
              <>
                <span className="timestamp">
                  [{new Date(log.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false })}]
                </span>
                <span className="content">
                  {log.action
                    ? <span className="terminal-cmd-link" onClick={() => handleCommand(log.action!)}>{log.text}</span>
                    : log.text}
                </span>
              </>
            )}
          </div>
        ))}
        <div ref={terminalEndRef} />
      </div>

      {/* Input */}
      <form onSubmit={(e) => { e.preventDefault(); doSubmit(); }} className="terminal-input-area">
        <div className="input-wrapper">
          <span className="prompt">{'> '}</span>
          <div className="input-field-wrapper" onClick={() => inputRef.current?.focus()}>
            <div className="fake-input" aria-hidden="true">
              {inputValue
                ? <span className="fake-input-text">{inputValue}</span>
                : <span className="fake-input-placeholder">{isReady ? 'Speak...' : 'Waiting for wallet...'}</span>}
              {isFocused && !isLoading && <span className="cursor-blink">_</span>}
            </div>
            <input
              ref={inputRef}
              type="text"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); doSubmit(); } }}
              onFocus={() => setIsFocused(true)}
              onBlur={() => setIsFocused(false)}
              disabled={isLoading}
              autoFocus
              className="hidden-input"
            />
          </div>
          <button type="submit" disabled={isLoading || !inputValue.trim()} className="submit-btn">
            {isLoading ? '...' : 'Send'}
          </button>
        </div>
      </form>

      {isLoading && <div className="loading-indicator">HUGINN is processing...</div>}
    </div>
  );
}
