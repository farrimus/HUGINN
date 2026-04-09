import { useState, useRef, useEffect, useCallback } from 'react';
import { useConnection, useSmartObject, type SmartAssemblyResponse } from '@evefrontier/dapp-kit';
import { useToolOutput } from '../hooks/useToolOutput';
import { BaselinePanelData, HuginnNewsData, BuildOptionsData } from '../types/terminal';
import { TripCalculatorForm } from './TripCalculatorForm';
import { BUILD_TIME } from '../main';
import { useCompanionStream } from '../hooks/useCompanionStream';
import { EveFeralCodeGen } from './EveFeralCodeGen';
import { useWatcherAlerts } from '../hooks/useWatcherAlerts';
import { useTribePosts, TribePostEvent } from '../hooks/useTribePosts';
import { useEntityContext, type EnrichedAssembly } from '../context/EntityContext';
import { useSession } from '../hooks/useSession';
import { InfoPanel } from './InfoPanel';
import { BoardPanel } from './BoardPanel';
import { LogUploadPanel } from './LogUploadPanel';
import { AdminPanel } from './AdminPanel';
import { ReconForm } from './ReconForm';
import {
  getDisabledTools, FEATURES, FeatureFlags, ToolFlags,
  saveCachedAdminConfig,
} from '../features/featureFlags';
import { canAccess, getActiveNavItemsForTier } from '../features/tierCapabilities';
import type { WatchRule, WatcherAlert, RouteData, CourierContract, TribePresenceMember, TribePost, ChatMessage } from '../types/terminal';
import { SUBDIV } from '../constants/dividers';

const API_BASE_URL = window.location.origin;

interface HelpGroup {
  label: string;
  cmds: Array<{ text: string; action: string }>;
}

interface TerminalLog {
  text: string;
  type: 'info' | 'user' | 'ai' | 'error' | 'warning' | 'command' | 'form' | 'help' | 'board' | 'upload' | 'admin' | 'recon';
  timestamp: number;
  action?: string;
  id?: string;
  helpGroups?: HelpGroup[];
  // Admin panel state
  adminFeatureFlags?: FeatureFlags;
  adminToolFlags?: ToolFlags;
  // Board state (type === 'board' entries only)
  boardPosts?: TribePost[];
  boardConfirmDeleteId?: string | null;
  boardShowPostForm?: boolean;
  boardPostDraft?: string;
  // Inline copy button (route output)
  copyText?: string;
}

function buildBaselineData(
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

/**
 * TerminalUI Component
 * CLI interface for the structure companion chat.
 * Wallet and assembly resolved via dapp-kit. Chat via /companion/chat.
 */
export function TerminalUI() {
  const { isConnected, walletAddress, handleConnect, handleDisconnect, hasEveVault } = useConnection();
  const { assembly } = useSmartObject() as {
    assembly: SmartAssemblyResponse | null;
  };

  const { currentToolType, currentData, isAnimating, display: displayToolOutput, finishAnimation, setDirect } = useToolOutput();
  const { sendMessage } = useCompanionStream();
  const {
    enrichedAssembly,
    networkData,
    inventoryData,
    characterAssemblies,
    tenant,
  } = useEntityContext();

  const assemblyId = assembly?.id;
  const itemId = new URLSearchParams(window.location.search).get('itemId') || '';

  // Splash screen: show once per session, gate baseline animations until it exits
  const splashAlreadyPlayed = sessionStorage.getItem('crud_splash') === '1';
  const [splashDone, setSplashDone] = useState(splashAlreadyPlayed);
  const splashDoneRef = useRef(splashAlreadyPlayed);
  const latestBaselineRef = useRef<BaselinePanelData | null>(null);

  const buildLabel = (() => {
    try {
      const d = new Date(BUILD_TIME);
      return `${d.toISOString().slice(0, 10)} ${d.toISOString().slice(11, 16)}z`;
    } catch { return BUILD_TIME; }
  })();

  const [logs, setLogs] = useState<TerminalLog[]>([
    { text: `HUGINN initializing...  [build ${buildLabel}]`, type: 'info', timestamp: Date.now() },
  ]);
  const [inputValue, setInputValue] = useState('');
  const [isFocused, setIsFocused] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [feralTickMs, setFeralTickMs] = useState(300);
  const windDownRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);
  const [currentSystem, setCurrentSystem] = useState<string>('');
  const [debugMode, setDebugMode] = useState(false);
  const {
    featureFlags, setFeatureFlags,
    toolFlags, setToolFlags,
    toolRegistry,
    tier,
    shipProfile,
    sessionTenant,
    sessionRegistered,
    visitorName,
    tribeId,
  } = useSession(walletAddress, assemblyId, tenant, assembly?.solarSystem?.name || currentSystem);
  const terminalEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const hasGreeted = useRef(false);
  const activeBoardLogIdRef = useRef<string | null>(null);

  const isReady = isConnected && !!assemblyId && sessionRegistered;

  const addLog = (text: string, type: TerminalLog['type'] = 'info', action?: string): void => {
    setLogs((prev) => [...prev, { text, type, timestamp: Date.now(), action }]);
  };

  // Auto-scroll
  useEffect(() => {
    terminalEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs, isStreaming]);

  // Baseline panel — update whenever identity or enrichment changes.
  // During splash: save data to ref but do not animate. After splash exits,
  // handleSplashComplete applies the latest data directly via setDirect.
  useEffect(() => {
    const location = assembly?.solarSystem?.name || currentSystem || '[REDACTED]';
    const baselineData = buildBaselineData(walletAddress, assemblyId, visitorName, tier, location, enrichedAssembly);

    latestBaselineRef.current = baselineData;

    // Splash still active — queue silently, do not animate
    if (!splashDoneRef.current) return;

    displayToolOutput('baseline', baselineData);
  }, [
    walletAddress, assemblyId, visitorName, tier,
    assembly?.solarSystem?.name, currentSystem,
    enrichedAssembly, displayToolOutput,
  ]);

  // Called by SplashScreen when its animation completes and exit begins.
  // Applies latest data silently so InfoPanel is ready when splash clears.
  const handleSplashComplete = useCallback(() => {
    sessionStorage.setItem('crud_splash', '1');
    if (latestBaselineRef.current) {
      setDirect('baseline', latestBaselineRef.current);
    }
    splashDoneRef.current = true;
    // Unmount splash after its 500ms CSS exit transition
    setTimeout(() => setSplashDone(true), 500);
  }, [setDirect]);

  // Restore saved system from localStorage when assembly is known.
  // Feature/tool flags are already loaded synchronously from itemId above.
  useEffect(() => {
    if (!assemblyId || currentSystem) return;
    const saved = localStorage.getItem(`sys_${assemblyId}`);
    if (saved) setCurrentSystem(saved);
  }, [assemblyId]); // eslint-disable-line react-hooks/exhaustive-deps

  // Auto-connect when EVE Vault is available
  useEffect(() => {
    if (!isConnected && hasEveVault) {
      handleConnect();
    }
  }, [hasEveVault]);

  // Warn once if itemId is missing (structure cannot be identified)
  useEffect(() => {
    if (!itemId) {
      const base = window.location.origin + window.location.pathname;
      const t = (sessionTenant || tenant);
      addLog('Structure not identified. No itemId in URL.', 'warning');
      addLog(`Change URL to: ${base}?itemId=<copy from top left corner>&tenant=${t}`, 'warning');
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Tribe board — SSE connection, routes events to the active board log entry
  useTribePosts(tribeId, (event: TribePostEvent) => {
    const boardLogId = activeBoardLogIdRef.current;
    if (!boardLogId) return;
    setLogs(prev => prev.map(l => {
      if (l.id !== boardLogId || l.type !== 'board') return l;
      if (event.type === 'snapshot') {
        return { ...l, boardPosts: event.posts };
      } else if (event.type === 'new_post') {
        const posts = [...(l.boardPosts ?? []), event.post];
        return { ...l, boardPosts: posts.slice(-30) };
      } else if (event.type === 'post_deleted') {
        return { ...l, boardPosts: (l.boardPosts ?? []).filter(p => p.id !== event.post_id) };
      }
      return l;
    }));
  });

  // Watcher alerts — persistent SSE connection, fires when threshold is crossed
  useWatcherAlerts(walletAddress || null, (alert: WatcherAlert) => {
    const filter = alert.item_filter ? ` [${alert.item_filter}]` : '';
    setLogs(prev => [...prev, {
      text: `[WATCH ALERT]: ${alert.ssu_name}${filter} — count ${alert.current_count} is below threshold ${alert.threshold}`,
      type: 'warning' as const,
      timestamp: Date.now(),
    }]);
  });

  // Greet once when ready
  useEffect(() => {
    if (isReady && !hasGreeted.current) {
      hasGreeted.current = true;
      addLog('[HUGINN]: Shell recognized. Signature confirmed. This unit is online.', 'ai');
    }
  }, [isReady]);

  // Focus the input when a printable key is pressed and nothing interactive has focus.
  // This replaces the old onClick-on-container approach, which blocked text selection and dropdowns.
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key.length !== 1) return;         // ignore modifier-only, arrows, etc.
      if (e.ctrlKey || e.metaKey || e.altKey) return; // ignore shortcuts
      const active = document.activeElement;
      if (active && active !== document.body) return;  // something already has focus
      inputRef.current?.focus();
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, []);

  const cancelWindDown = () => {
    if (windDownRef.current) {
      clearTimeout(windDownRef.current);
      windDownRef.current = null;
    }
  };

  const windDown = (ms: number, stepsLeft: number) => {
    if (stepsLeft === 0) {
      setIsStreaming(false);
      setFeralTickMs(300);
      return;
    }
    const next = ms * 2;
    setFeralTickMs(next);
    windDownRef.current = setTimeout(() => windDown(next, stepsLeft - 1), next);
  };

  // Send chat message to /companion/stream (SSE with tool use)
  const handleChatMessage = async (userInput: string): Promise<void> => {
    if (!isReady) {
      addLog('Wallet not connected or structure not identified.', 'warning');
      return;
    }

    cancelWindDown();
    setFeralTickMs(300);
    addLog(`[You]: ${userInput}`, 'user');
    setIsLoading(true);

    let textBuffer = '';
    const streamId = `stream-${Date.now()}`;
    let streamStarted = false;

    await sendMessage(
      {
        assembly_id: assemblyId!,
        message: userInput,
        history: chatHistory,
        debug: debugMode,
        owner_address: walletAddress || '',
        character_name: visitorName || walletAddress?.slice(0, 10) || '',
        item_id: itemId,
        assembly_name: enrichedAssembly?.name ?? assembly?.name ?? '',
        assembly_type: enrichedAssembly?.assembly_type ?? assembly?.typeDetails?.name ?? '',
        assembly_state: enrichedAssembly?.status ?? assembly?.state ?? '',
        system_name: assembly?.solarSystem?.name || currentSystem,
        system_id: assembly?.solarSystem?.id,
        disabled_tools: getDisabledTools(toolFlags),
        tenant: (sessionTenant || tenant),
      },
      {
        onTextChunk: (text) => {
          textBuffer += text;
          if (!streamStarted) {
            streamStarted = true;
            setIsStreaming(true);
            setLogs((prev) => [...prev, { id: streamId, text: `[HUGINN]: ${text}`, type: 'ai', timestamp: Date.now() }]);
          } else {
            setLogs((prev) => prev.map((l) => l.id === streamId ? { ...l, text: `[HUGINN]: ${textBuffer}` } : l));
          }
        },
        onToolResult: (toolName, data) => {
          displayToolOutput(toolName, data);
          if (toolName === 'route_planned') {
            printRouteToChat(data as RouteData);
          }
        },
        onDone: () => {
          if (textBuffer) {
            setChatHistory((prev) => [
              ...prev,
              { role: 'user', content: userInput },
              { role: 'assistant', content: textBuffer },
            ]);
          }
          setIsLoading(false);
          windDown(300, 2);
        },
        onError: (err) => {
          addLog(`Error: ${err.message}`, 'error');
          cancelWindDown();
          setIsStreaming(false);
          setFeralTickMs(300);
          setIsLoading(false);
        },
      }
    );
  };

  // Feature flag guard — returns true and warns if feature is disabled
  const isOff = (key: string): boolean => {
    if (featureFlags[key] === false) {
      addLog('Feature disabled. Enable in /admin.', 'warning');
      return true;
    }
    return false;
  };

  // --- Connection + help ---
  const handleConnectionCommands = (command: string): void => {
    if (command === '/connect') {
      if (isConnected) { addLog('Already connected.', 'warning'); }
      else { handleConnect(); addLog('Initiating wallet connection...', 'command'); }
    } else if (command === '/disconnect') {
      if (!isConnected) { addLog('Not connected.', 'warning'); }
      else { handleDisconnect(); addLog('Wallet disconnected.', 'info'); }
    } else if (command === '/help') {
      const on = (key: string) => featureFlags[key] !== false;
      const helpGroups: HelpGroup[] = [
        {
          label: 'CONNECTION',
          cmds: [{ text: '/connect', action: '/connect' }, { text: '/disconnect', action: '/disconnect' }],
        },
        {
          label: 'NAVIGATION',
          cmds: [
            { text: '/system <name>', action: '/system' },
            ...(on('recon') ? [{ text: '/recon', action: '/recon' }] : []),
            ...(on('route') ? [{ text: '/route [dest]', action: '/route' }] : []),
            { text: '/home', action: '/home' },
          ],
        },
        ...(on('network') || on('nodes') || on('inventory') || on('assets') || on('signal') || on('upload') ? [{
          label: 'INTEL',
          cmds: [
            ...(on('network')   ? [{ text: '/network',   action: '/network' }]   : []),
            ...(on('nodes')     ? [{ text: '/nodes',     action: '/nodes' }]     : []),
            ...(on('inventory') ? [{ text: '/inventory', action: '/inventory' }] : []),
            ...(on('assets')    ? [{ text: '/assets',    action: '/assets' }]    : []),
            ...(on('signal')    ? [{ text: '/signal',    action: '/signal' }]    : []),
            ...(on('upload')    ? [{ text: '/upload',    action: '/upload' }]    : []),
          ],
        }] : []),
        ...(on('watches') ? [{
          label: 'WATCHER',
          cmds: [{ text: '/watches', action: '/watches' }, { text: '/unwatch <rule_id>', action: '/unwatch' }],
        }] : []),
        ...(on('courier') || on('tribe') || on('board') ? [{
          label: 'SOCIAL',
          cmds: [
            ...(on('courier') ? [{ text: '/courier', action: '/courier' }, { text: '/claim-courier <id>', action: '/claim-courier' }] : []),
            ...(on('tribe')   ? [{ text: '/tribe',   action: '/tribe' }]   : []),
            ...(on('board')   ? [{ text: '/board',   action: '/board' }]   : []),
          ],
        }] : []),
        ...(canAccess(tier, 'canAdmin') ? [{ label: 'ADMIN', cmds: [{ text: '/admin', action: '/admin' }] }] : []),
      ];
      setLogs(prev => [...prev, { text: '', type: 'help', timestamp: Date.now(), helpGroups }]);
      addLog('Anything else goes to HUGINN.', 'info');
    }
  };

  // --- Navigation ---
  const handleNavigationCommands = async (command: string, parts: string[]): Promise<void> => {
    if (command === '/system') {
      const systemName = parts.slice(1).join(' ').trim();
      if (!systemName) { addLog('Usage: /system <system name>', 'warning'); return; }
      try {
        const res = await fetch(`${API_BASE_URL}/galaxy/system/${encodeURIComponent(systemName)}`);
        if (res.status === 404) { addLog(`Unknown system: "${systemName}"`, 'error'); return; }
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        const canonical = data.name as string;
        displayToolOutput('baseline', buildBaselineData(walletAddress, assemblyId, visitorName, tier, canonical, enrichedAssembly));
        setCurrentSystem(canonical);
        addLog(`Location set: ${canonical}`, 'info');
        if (assemblyId) {
          localStorage.setItem(`sys_${assemblyId}`, canonical);
          fetch(`${API_BASE_URL}/structure/${assemblyId}/location/manual`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ system_name: canonical }),
          }).catch((e) => console.warn('Failed to persist system to profile:', e));
        }
      } catch (err) { addLog(`System lookup failed: ${err instanceof Error ? err.message : String(err)}`, 'error'); }
    } else if (command === '/home') {
      displayToolOutput('baseline', buildBaselineData(
        walletAddress, assemblyId, visitorName, tier,
        assembly?.solarSystem?.name || currentSystem || '[REDACTED]',
        enrichedAssembly,
      ));
    } else if (command === '/route') {
      const destination = parts.slice(1).join(' ').trim();
      if (!destination) {
        setLogs(prev => [...prev, { text: '', type: 'form', timestamp: Date.now(), id: `tripcalc-${Date.now()}` }]);
        return;
      }
      try {
        addLog(`Plotting route to ${destination}...`, 'info');
        const res = await fetch(`${API_BASE_URL}/route`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ destination, origin: currentSystem || undefined }),
        });
        if (res.status === 404 || res.status === 400) {
          const err = await res.json();
          addLog(err.detail || `No route found to "${destination}".`, 'error');
          return;
        }
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const routeData = await res.json();
        displayToolOutput('route_planned', routeData);
        addLog(`Route: ${routeData.jumps} jump${routeData.jumps !== 1 ? 's' : ''} to ${destination}.`, 'info');
      } catch (err) { addLog(`Route failed: ${err instanceof Error ? err.message : String(err)}`, 'error'); }
    } else if (command === '/intel') {
      const target = parts.slice(1).join(' ').trim() || currentSystem;
      if (!target) { addLog('Usage: /intel <system name>  (or set location with /system first)', 'warning'); return; }
      try {
        addLog(`Scanning ${target}...`, 'info');
        const res = await fetch(`${API_BASE_URL}/galaxy/system/${encodeURIComponent(target)}/intel`);
        if (res.status === 404) { addLog(`Unknown system: "${target}"`, 'error'); return; }
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        displayToolOutput('system_intel', await res.json());
        addLog('System intel loaded.', 'info');
      } catch (err) { addLog(`Intel scan failed: ${err instanceof Error ? err.message : String(err)}`, 'error'); }
    }
  };

  // --- Network / intel panels ---
  const handleNetworkCommands = async (command: string): Promise<void> => {
    if (command === '/network') {
      if (isOff('network')) return;
      if (!networkData) { addLog('Network data not available.', 'warning'); return; }
      displayToolOutput('network_map', {
        nodeId:              networkData.id,
        nodeName:            networkData.name,
        nodeStatus:          networkData.status,
        currentAssemblyId:   assemblyId || '',
        currentAssemblyName: enrichedAssembly?.name ?? assemblyId?.slice(0, 10) ?? '',
        fuel: {
          quantity:           networkData.fuel.quantity,
          maxCapacity:        networkData.fuel.max_capacity,
          fuelPercent:        networkData.fuel.fuel_percent,
          hoursRemaining:     networkData.fuel.hours_remaining,
          burnRateUnitsPerHr: networkData.fuel.burn_rate_units_per_hr,
          isBurning:          networkData.fuel.is_burning,
        },
        energy: {
          currentEnergyProduction: networkData.energy.current_energy_production,
          maxEnergyProduction:     networkData.energy.max_energy_production,
          totalReservedEnergy:     networkData.energy.total_reserved_energy,
          energyPercent:           networkData.energy.energy_percent,
        },
        connectedAssemblies: (networkData.connected_assemblies ?? []).map(a => ({
          id: a.id, name: a.name, assemblyType: a.assembly_type, status: a.status,
          typeId: a.type_id, key: a.key, groupName: a.group_name, categoryName: a.category_name,
        })),
        truncated: networkData.truncated,
      });
      addLog('Network map loaded.', 'info');
    } else if (command === '/nodes') {
      if (isOff('nodes')) return;
      try {
        addLog('Scanning for network nodes...', 'info');
        const res = await fetch(`${API_BASE_URL}/entity/nodes?tenant=${sessionTenant || tenant}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const raw = await res.json();
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const nodes = (raw.nodes ?? []).map((n: any) => ({
          id: n.id, name: n.name, status: n.status, fuelPercent: n.fuel_percent,
          hoursRemaining: n.hours_remaining, isBurning: n.is_burning,
          connectedCount: n.connected_count, systemName: n.system_name,
        }));
        displayToolOutput('nodes_list', { nodes, count: nodes.length });
        addLog(`${nodes.length} network node${nodes.length !== 1 ? 's' : ''} found.`, 'info');
      } catch (err) { addLog(`Nodes scan failed: ${err instanceof Error ? err.message : String(err)}`, 'error'); }
    } else if (command === '/inventory') {
      if (isOff('inventory')) return;
      if (!inventoryData) { addLog('Inventory data not available. Structure may not be a SSU.', 'warning'); return; }
      displayToolOutput('inventory', inventoryData);
      addLog('Inventory loaded.', 'info');
    } else if (command === '/assets') {
      if (isOff('assets')) return;
      if (!characterAssemblies) { addLog('Asset data not available. Wallet may not be connected.', 'warning'); return; }
      displayToolOutput('asset_map', { characterName: characterAssemblies.character_name, assemblies: characterAssemblies.assemblies });
      addLog('Asset map loaded.', 'info');
    } else if (command === '/signal') {
      if (isOff('signal')) return;
      if (!canAccess(tier, 'canSignal')) { addLog('Signal access restricted to OWNER and TRIBE.', 'warning'); return; }
      if (!walletAddress || !assemblyId) { addLog('Wallet not connected.', 'warning'); return; }
      try {
        addLog('Receiving signal...', 'info');
        const res = await fetch(
          `${API_BASE_URL}/news/latest?assembly_id=${encodeURIComponent(assemblyId)}`,
          { headers: { 'X-Wallet-Address': walletAddress } },
        );
        if (res.status === 403) { addLog('Signal access denied.', 'error'); return; }
        if (res.status === 404) { addLog('[ NO TRANSMISSION ON FILE ]', 'info'); return; }
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        displayToolOutput('huginn_news', await res.json() as HuginnNewsData);
        addLog('Signal received.', 'info');
      } catch (err) { addLog(`Signal failed: ${err instanceof Error ? err.message : String(err)}`, 'error'); }
    }
  };

  // --- Watcher ---
  const handleWatcherCommands = async (command: string, parts: string[]): Promise<void> => {
    if (command === '/watches') {
      if (isOff('watches')) return;
      if (!walletAddress) { addLog('Wallet not connected.', 'warning'); return; }
      try {
        const res = await fetch(`${API_BASE_URL}/watcher/${walletAddress}`, { headers: { 'X-Wallet-Address': walletAddress } });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const rules = ((await res.json()).rules as WatchRule[]).filter(r => r.active);
        if (rules.length === 0) { addLog('No active watch rules. Use /watch <ssu_id> to add one.', 'info'); return; }
        addLog(`Watch rules (${rules.length}):`, 'info');
        const t = Date.now();
        rules.forEach(r => {
          const filter = r.item_filter ? ` [${r.item_filter}]` : ' [all items]';
          const name = r.ssu_name || r.ssu_id.slice(0, 16);
          const checked = r.last_checked ? ` checked ${r.last_checked.slice(11, 16)}z` : '';
          setLogs(prev => [...prev, { text: `  ${r.id.slice(0, 8)}  ${name}${filter}  threshold=${r.threshold}${checked}`, type: 'command' as const, timestamp: t, action: `/unwatch ${r.id}` }]);
        });
      } catch (err) { addLog(`Failed to load watches: ${err instanceof Error ? err.message : String(err)}`, 'error'); }
    } else if (command === '/unwatch') {
      if (isOff('watches')) return;
      const ruleId = parts[1];
      if (!ruleId) { addLog('Usage: /unwatch <rule_id>', 'warning'); return; }
      if (!walletAddress) { addLog('Wallet not connected.', 'warning'); return; }
      try {
        const res = await fetch(`${API_BASE_URL}/watcher/${walletAddress}/${ruleId}`, { method: 'DELETE', headers: { 'X-Wallet-Address': walletAddress } });
        if (res.status === 404) { addLog(`Rule not found: ${ruleId}`, 'error'); return; }
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        addLog(`Watch rule removed: ${ruleId.slice(0, 8)}`, 'info');
      } catch (err) { addLog(`Unwatch failed: ${err instanceof Error ? err.message : String(err)}`, 'error'); }
    }
  };

  // --- Social ---
  const handleSocialCommands = async (command: string, parts: string[]): Promise<void> => {
    if (command === '/courier') {
      if (isOff('courier')) return;
      try {
        const res = await fetch(`${API_BASE_URL}/courier`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const contracts = (await res.json()).contracts as CourierContract[];
        if (contracts.length === 0) { addLog('No active courier contracts. Ask HUGINN to post one.', 'info'); return; }
        addLog(`Courier contracts (${contracts.length}):`, 'info');
        const t = Date.now();
        contracts.forEach(c => {
          const status = c.status.replace('_', ' ').toUpperCase();
          const claimer = c.claimed_by_name ? `  claimer: ${c.claimed_by_name}` : '';
          setLogs(prev => [...prev, { text: `  ${c.id.slice(0, 8)}  [${status}]  ${c.item_description}  ${c.from_location} → ${c.to_location}  reward: ${c.reward_description}  by ${c.poster_name}${claimer}`, type: 'command' as const, timestamp: t, action: c.status === 'open' ? `/claim-courier ${c.id}` : undefined }]);
        });
      } catch (err) { addLog(`Failed to load courier board: ${err instanceof Error ? err.message : String(err)}`, 'error'); }
    } else if (command === '/claim-courier') {
      const contractId = parts[1];
      if (!contractId) { addLog('Usage: /claim-courier <contract_id>', 'warning'); return; }
      if (!walletAddress) { addLog('Wallet not connected.', 'warning'); return; }
      try {
        const res = await fetch(`${API_BASE_URL}/courier/${contractId}/claim`, { method: 'PATCH', headers: { 'X-Wallet-Address': walletAddress } });
        if (res.status === 404) { addLog(`Contract not found: ${contractId}`, 'error'); return; }
        if (res.status === 409) { addLog(`Cannot claim: ${(await res.json()).detail}`, 'error'); return; }
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const c = (await res.json()).contract as CourierContract;
        addLog(`Contract claimed: ${c.id.slice(0, 8)}  ${c.item_description}  ${c.from_location} → ${c.to_location}  reward: ${c.reward_description}`, 'info');
      } catch (err) { addLog(`Claim failed: ${err instanceof Error ? err.message : String(err)}`, 'error'); }
    } else if (command === '/tribe') {
      if (isOff('tribe')) return;
      if (!walletAddress) { addLog('Wallet not connected.', 'warning'); return; }
      if (!tribeId) { addLog('No tribe affiliation found. Your character may not belong to a tribe, or tribe data is still loading.', 'warning'); return; }
      try {
        const res = await fetch(`${API_BASE_URL}/tribe/${tribeId}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const members = (await res.json()).members as TribePresenceMember[];
        const TRIBE_NAMES: Record<number, string> = { 1000167: 'WOLF' };
        const tribeName = TRIBE_NAMES[tribeId] ?? `Tribe ${tribeId}`;
        if (members.length === 0) { addLog(`${tribeName} — no members currently online.`, 'info'); return; }
        addLog(`${tribeName} — ${members.length} online:`, 'info');
        const t = Date.now();
        members.forEach(m => setLogs(prev => [...prev, { text: `  ${m.character_name.padEnd(20)} [${m.status}]  ${m.location}  ${m.last_ping.slice(11, 16)}z`, type: 'command' as const, timestamp: t }]));
      } catch (err) { addLog(`Failed to load tribe board: ${err instanceof Error ? err.message : String(err)}`, 'error'); }
    } else if (command === '/board') {
      if (isOff('board')) return;
      if (!walletAddress) { addLog('Wallet not connected.', 'warning'); return; }
      if (!tribeId) { addLog('No tribe affiliation found. Your character may not belong to a tribe, or tribe data is still loading.', 'warning'); return; }
      try {
        const res = await fetch(`${API_BASE_URL}/tribe-posts/${tribeId}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        const boardId = `board-${Date.now()}`;
        activeBoardLogIdRef.current = boardId;
        setLogs(prev => [...prev, { text: '', type: 'board' as const, timestamp: Date.now(), id: boardId, boardPosts: data.posts as TribePost[], boardConfirmDeleteId: null, boardShowPostForm: false, boardPostDraft: '' }]);
      } catch (err) { addLog(`Failed to load board: ${err instanceof Error ? err.message : String(err)}`, 'error'); }
    }
  };

  // --- Admin / util ---
  const handleAdminCommands = (command: string): void => {
    if (command === '/admin') {
      if (!canAccess(tier, 'canAdmin')) { addLog('Admin access restricted to OWNER.', 'warning'); return; }
      setLogs(prev => [...prev, { text: '', type: 'admin' as const, timestamp: Date.now(), id: `admin-${Date.now()}`, adminFeatureFlags: { ...featureFlags }, adminToolFlags: { ...toolFlags } }]);
    } else if (command === '/recon') {
      if (isOff('recon')) return;
      setLogs(prev => [...prev, { text: '', type: 'recon' as const, timestamp: Date.now(), id: `recon-${Date.now()}` }]);
    } else if (command === '/upload') {
      setLogs(prev => [...prev, { text: '', type: 'upload' as const, timestamp: Date.now(), id: `upload-${Date.now()}` }]);
    } else if (command === '/debug') {
      setDebugMode(true);
      addLog('Debug mode active. Session will be dumped after each message.', 'info');
    }
  };

  // --- Dispatcher ---
  const handleCommand = async (input: string): Promise<void> => {
    const parts = input.trim().split(/\s+/);
    const command = parts[0].toLowerCase();

    if (['/connect', '/disconnect', '/help'].includes(command))
      return handleConnectionCommands(command);
    if (['/system', '/home', '/route', '/intel'].includes(command))
      return handleNavigationCommands(command, parts);
    if (['/network', '/nodes', '/inventory', '/assets', '/signal'].includes(command))
      return handleNetworkCommands(command);
    if (['/watches', '/unwatch'].includes(command))
      return handleWatcherCommands(command, parts);
    if (['/courier', '/claim-courier', '/tribe', '/board'].includes(command))
      return handleSocialCommands(command, parts);
    if (['/admin', '/recon', '/upload', '/debug'].includes(command))
      return handleAdminCommands(command);

    addLog(`Unknown command: ${command}`, 'error');
  };

  const printRouteToChat = (route: RouteData): void => {
    const origin = route.path[0] ?? '?';
    const dest   = route.path[route.path.length - 1] ?? '?';

    const hopLines: string[] = [];
    if (route.hops && route.hops.length > 0) {
      hopLines.push(`  ${String(1).padStart(3)}. ${origin.padEnd(24)} ORIGIN`);
      route.hops.forEach((hop, i) => {
        const num     = String(i + 2).padStart(3);
        const name    = hop.to.padEnd(24);
        const typeTag = hop.type === 'gate' ? 'GATE' : 'JUMP';
        const dist    = hop.type === 'direct' ? `  ${hop.distance_ly.toFixed(1)} LY` : '';
        const hot     = hop.dest_temp >= 70 ? `  [${hop.dest_temp}°]` : '';
        hopLines.push(`  ${num}. ${name} ${typeTag}${dist}${hot}`);
      });
    } else {
      route.path.forEach((name, i) => {
        const num     = String(i + 1).padStart(3);
        const typeTag = i === 0 ? 'ORIGIN' : 'GATE';
        hopLines.push(`  ${num}. ${name.padEnd(24)} ${typeTag}`);
      });
    }

    const fuelLine = route.fuel_used > 0 || route.fuel_remaining > 0
      ? `Fuel: ${route.fuel_used.toFixed(1)}u used  |  ${route.fuel_remaining.toFixed(1)}u remaining`
      : null;

    const lines = [
      `[ROUTE] ${origin} → ${dest}  —  ${route.jumps} jump${route.jumps !== 1 ? 's' : ''}${route.total_ly > 0 ? `  ${route.total_ly.toFixed(1)} LY` : ''}`,
      SUBDIV,
      ...hopLines,
      SUBDIV,
      ...(fuelLine ? [fuelLine] : []),
      ...(route.hot_systems.length > 0 ? [`Hot: ${route.hot_systems.join(', ')}`] : []),
      ...(route.warnings.length > 0 ? route.warnings.map(w => `  ! ${w}`) : []),
    ];

    const routeText = lines.join('\n');
    addLog(routeText, 'info');

    // Build linked version for copy button (system names → showinfo links)
    const COPY_SEP = '─'.repeat(43);
    const nameToId = new Map<string, number>();
    route.path.forEach((name, i) => {
      if (route.path_ids?.[i]) nameToId.set(name, route.path_ids[i]);
    });
    const link = (name: string) => {
      const id = nameToId.get(name);
      return id ? `<a href="showinfo:5//${id}">${name}</a>` : name;
    };

    // Find first hop where cumulative fuel use exceeds starting fuel
    const fuelQuantity = route.fuel_used + route.fuel_remaining;
    let refuelHopIndex = -1;
    if (fuelQuantity > 0 && route.fuel_remaining < 0 && route.hops && route.total_ly > 0) {
      const fuelRate = route.fuel_used / route.total_ly;
      let cumulative = 0;
      for (let i = 0; i < route.hops.length; i++) {
        cumulative += route.hops[i].distance_ly * fuelRate;
        if (cumulative > fuelQuantity) { refuelHopIndex = i; break; }
      }
    }

    const linkedHopLines: string[] = [];
    if (route.hops && route.hops.length > 0) {
      linkedHopLines.push(`  ${String(1).padStart(3)}. ${link(origin)}  ORIGIN`);
      route.hops.forEach((hop, i) => {
        const num     = String(i + 2).padStart(3);
        const typeTag = hop.type === 'gate' ? 'GATE' : 'JUMP';
        const dist    = hop.type === 'direct' ? `  ${hop.distance_ly.toFixed(1)} LY` : '';
        const hot     = route.hot_systems.includes(hop.to) ? '  HOT' : '';
        const refuel  = i === refuelHopIndex ? '  REFUEL' : '';
        linkedHopLines.push(`  ${num}. ${link(hop.to)}  ${typeTag}${dist}${hot}${refuel}`);
      });
    } else {
      route.path.forEach((name, i) => {
        const num     = String(i + 1).padStart(3);
        const typeTag = i === 0 ? 'ORIGIN' : 'GATE';
        linkedHopLines.push(`  ${num}. ${link(name)}  ${typeTag}`);
      });
    }
    const linkedLines = [
      `[ROUTE] ${link(origin)} → ${link(dest)}  —  ${route.jumps} jump${route.jumps !== 1 ? 's' : ''}${route.total_ly > 0 ? `  ${route.total_ly.toFixed(1)} LY` : ''}`,
      COPY_SEP,
      ...linkedHopLines,
      COPY_SEP,
      ...(fuelLine ? [fuelLine] : []),
      ...(route.hot_systems.length > 0 ? [`Hot systems: ${route.hot_systems.join(', ')}`] : []),
    ];

    setLogs(prev => [...prev, {
      text: '',
      type: 'info' as const,
      timestamp: Date.now(),
      copyText: linkedLines.join('\n'),
    }]);
  };

  const handlePrintToTerminal = (): void => {
    const fmtNum = (n: number) => Math.round(n).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
    const fmtVol = (n: number) => n.toFixed(2);
    const pad  = (s: string, len: number) => s.slice(0, len).padEnd(len);
    const padR = (s: string, len: number) => s.slice(0, len).padStart(len);

    if (currentToolType === 'inventory' && inventoryData) {
      const { assembly_name, used_capacity, max_capacity, capacity_percent, items } = inventoryData;
      const capStr = max_capacity && max_capacity > 0
        ? `${fmtNum(used_capacity)} / ${fmtNum(max_capacity)} m³${capacity_percent !== null ? ` (${capacity_percent.toFixed(1)}%)` : ''}`
        : `${fmtNum(used_capacity)} m³ used`;
      const sorted = [...items].sort((a, b) => {
        const c = a.category_name.localeCompare(b.category_name);
        return c !== 0 ? c : a.type_name.localeCompare(b.type_name);
      });
      const itemLines = sorted.map(item =>
        `  ${padR(fmtNum(item.quantity), 6)}x  ${pad(item.type_name, 24)}${pad(item.category_name, 16)}${padR(fmtVol(item.total_volume) + ' m³', 12)}`
      );
      const totalVol = items.reduce((s, i) => s + i.total_volume, 0);
      const lines = [
        `INVENTORY — ${assembly_name}  |  ${capStr}`,
        ...itemLines,
        `  TOTAL: ${items.length} item type${items.length !== 1 ? 's' : ''}, ${fmtVol(totalVol)} m³`,
      ];
      addLog('[PRINT]: ' + lines.join('\n'), 'info');
    } else if (currentToolType === 'network_map' && networkData) {
      const { name, status, fuel, energy, connected_assemblies } = networkData;
      const fuelStr = fuel.is_burning
        ? `FUEL: ${fuel.fuel_percent.toFixed(0)}%  ~${(fuel.hours_remaining / 24).toFixed(1)}d`
        : 'FUEL: NOT BURNING';
      const maxEn = parseInt(energy.max_energy_production, 10) || 0;
      const curEn = parseInt(energy.current_energy_production, 10) || 0;
      const enStr = maxEn > 0
        ? `ENERGY: ${fmtNum(curEn)} / ${fmtNum(maxEn)} kW`
        : 'ENERGY: [ NO DATA ]';
      const sorted = [...(connected_assemblies ?? [])].sort((a, b) => {
        if (a.id === assemblyId) return -1;
        if (b.id === assemblyId) return 1;
        const aOn = a.status === 'ONLINE' ? 0 : 1;
        const bOn = b.status === 'ONLINE' ? 0 : 1;
        return aOn !== bOn ? aOn - bOn : a.name.localeCompare(b.name);
      });
      const asmLines = sorted.map(a => {
        const isOff = a.status !== 'ONLINE';
        const badge = a.id === assemblyId ? ' [THIS]' : (isOff ? ' [!]' : '');
        const displayName = (a.id === assemblyId && enrichedAssembly?.name) ? enrichedAssembly.name : a.name;
        return `  ${pad((isOff ? '~' : ' ') + displayName, 24)}${pad(a.group_name || a.assembly_type, 18)}${a.status}${badge}`;
      });
      const lines = [
        `NETWORK — ${name} [${status}]  |  ${fuelStr}  |  ${enStr}`,
        `  (${sorted.length} connected structure${sorted.length !== 1 ? 's' : ''})`,
        ...asmLines,
      ];
      addLog('[PRINT]: ' + lines.join('\n'), 'info');
    } else if (currentToolType === 'huginn_news' && currentData) {
      const news = currentData as HuginnNewsData;
      addLog(news.text, 'info');
    } else if (currentToolType === 'asset_map' && characterAssemblies) {
      const TYPE_SHORT: Record<string, string> = {
        NetworkNode: 'NODE', SmartStorageUnit: 'SSU', SmartGate: 'GATE',
        SmartTurret: 'TURT', Manufacturing: 'MFG', Refinery: 'REF', Assembly: 'ASM',
      };
      const TYPE_PRI: Record<string, number> = {
        NetworkNode: 0, Manufacturing: 1, Refinery: 2,
        SmartStorageUnit: 3, SmartGate: 4, SmartTurret: 5,
      };
      const rank = (s: string) => s === 'ONLINE' ? 0 : s === 'DESTROYED' ? 2 : 1;
      const sorted = [...characterAssemblies.assemblies].sort((a, b) => {
        if (a.is_current && !b.is_current) return -1;
        if (!a.is_current && b.is_current) return 1;
        const tp = (TYPE_PRI[a.assembly_type] ?? 9) - (TYPE_PRI[b.assembly_type] ?? 9);
        if (tp !== 0) return tp;
        const r = rank(a.status) - rank(b.status);
        return r !== 0 ? r : a.name.localeCompare(b.name);
      });
      const lines = [
        `ASSETS — ${characterAssemblies.character_name} (${sorted.length} structure${sorted.length !== 1 ? 's' : ''})`,
        ...sorted.map(a => {
          const label  = pad(TYPE_SHORT[a.assembly_type] ?? a.assembly_type.slice(0, 4).toUpperCase(), 4);
          const name   = pad(a.name, 22);
          const status = pad(a.status, 9);
          const parts: string[] = [];
          if (a.assembly_type === 'NetworkNode') {
            if (a.fuel_percent !== undefined) parts.push(`${a.fuel_percent}% fuel`);
            if (a.fuel_burning && a.fuel_hours) parts.push(`${a.fuel_hours}h`);
            if (a.connected_count !== undefined) parts.push(`${a.connected_count} linked`);
          } else if (a.assembly_type === 'SmartGate') {
            if (a.is_linked !== undefined) parts.push(a.is_linked ? 'LINKED' : 'UNLINKED');
          } else if (a.item_type_count !== undefined) {
            parts.push(`${a.item_type_count} item type${a.item_type_count !== 1 ? 's' : ''}`);
          }
          if (a.is_current) parts.push('[HERE]');
          const isOff = a.status !== 'ONLINE';
          return `  ${isOff ? '~' : ' '}${label}  ${name}  ${status}  ${parts.join('  ')}`.trimEnd();
        }),
      ];
      addLog('[PRINT]: ' + lines.join('\n'), 'info');
    } else if (currentToolType === 'build_options' && currentData) {
      const bd = currentData as BuildOptionsData;
      const steps = bd.buildOrder ?? [];
      if (steps.length === 0) return;
      const stepLines = steps.map(s => {
        const stepLabel = `STEP ${s.step}`;
        const name = s.name.slice(0, 20).padEnd(20);
        let detail: string;
        if (s.status === 'can_build') {
          detail = 'READY';
        } else if (s.status === 'blocked') {
          detail = `BLOCKED  ${s.note}`;
        } else {
          const pct = (Math.round(s.pctReady * 100) + '%').padStart(4);
          const entries = Object.entries(s.shortfalls);
          const sfStr = entries.length > 0 ? `${entries[0][1]}x ${entries[0][0]}` : '';
          const extra = entries.length > 1 ? ' +more' : '';
          detail = `${pct}  need ${sfStr}${extra}`;
        }
        return `  ${stepLabel.padEnd(8)} ${name} ${detail}`;
      });
      addLog('[BUILD ORDER]\n' + stepLines.join('\n'), 'info');
    }
  };

  const handlePrintNode = async (nodeId: string): Promise<void> => {
    try {
      const t = (sessionTenant || tenant);
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

  const doSubmit = async (): Promise<void> => {
    if (!inputValue.trim() || isLoading) return;
    const input = inputValue.trim();
    setInputValue('');
    if (input.startsWith('/')) {
      await handleCommand(input);
    } else {
      await handleChatMessage(input);
    }
    inputRef.current?.focus();
  };

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>): Promise<void> => {
    e.preventDefault();
    await doSubmit();
  };

  const handleKeyDown = async (e: React.KeyboardEvent<HTMLInputElement>): Promise<void> => {
    if (e.key === 'Enter') {
      e.preventDefault();
      await doSubmit();
    }
  };

  return (
    <div className="terminal-ui">
      <InfoPanel
        currentToolType={currentToolType}
        currentData={currentData}
        isAnimating={isAnimating}
        onAnimationEnd={finishAnimation}
        onPrintToTerminal={handlePrintToTerminal}
        onPrintNode={handlePrintNode}
        showSplash={!splashDone}
        onSplashComplete={handleSplashComplete}
        onNavCommand={handleCommand}
        activeNavItems={getActiveNavItemsForTier(tier, featureFlags, FEATURES)}
      />

      <div className="terminal-output">
        {logs.map((log, idx) => (
          <div key={log.id ?? idx} className={`terminal-line line-${log.type}`}>
            {log.type === 'form' ? (
              <TripCalculatorForm
                currentSystem={currentSystem}
                apiBaseUrl={API_BASE_URL}
                walletAddress={walletAddress || null}
                initialShipProfile={shipProfile}
                onResult={(routeData, summary) => {
                  const id = log.id;
                  setLogs(prev => prev.map(l => l.id === id ? { ...l, type: 'info', text: summary } : l));
                  // eslint-disable-next-line @typescript-eslint/no-explicit-any
                  displayToolOutput('route_planned', routeData as any);
                  printRouteToChat(routeData as RouteData);
                }}
                onDismiss={() => {
                  const id = log.id;
                  setLogs(prev => prev.map(l => l.id === id ? { ...l, type: 'command', text: '[tripcalc]: cancelled' } : l));
                }}
              />
            ) : log.type === 'help' ? (
              <div className="help-grid">
                {log.helpGroups!.map((group, gi) => (
                  <>
                    {gi > 0 && <div key={`div-${gi}`} className="help-divider" />}
                    <div key={`grp-${gi}`} className="help-group">
                      <div className="help-group-label">{group.label}</div>
                      {group.cmds.map((cmd, ci) => (
                        <span key={ci} className="terminal-cmd-link help-cmd" onClick={() => handleCommand(cmd.action)}>
                          {cmd.text.toUpperCase()}
                        </span>
                      ))}
                    </div>
                  </>
                ))}
              </div>
            ) : log.type === 'board' ? (
              <BoardPanel
                posts={log.boardPosts ?? []}
                walletAddress={walletAddress || null}
                tribeId={tribeId!}
                confirmDeleteId={log.boardConfirmDeleteId ?? null}
                showPostForm={log.boardShowPostForm ?? false}
                postDraft={log.boardPostDraft ?? ''}
                apiBaseUrl={API_BASE_URL}
                onUpdate={(patch) => {
                  setLogs(prev => prev.map(l => l.id === log.id ? { ...l, ...patch } : l));
                }}
              />
            ) : log.type === 'upload' ? (
              <LogUploadPanel
                apiBaseUrl={API_BASE_URL}
                walletAddress={walletAddress || null}
                tenant={sessionTenant || tenant}
                onResult={(analysis, meta) => {
                  const id = log.id;
                  const skipNote = meta.skipped > 0 ? ` (${meta.skipped} already-processed skipped)` : '';
                  setLogs(prev => prev.map(l =>
                    l.id === id ? { ...l, type: 'info' as const, text: `[UPLOAD] ${meta.files} file(s) — ${meta.events} events — ${meta.systems.length} system(s)${skipNote}` } : l
                  ));
                  addLog(`[HUGINN]: ${analysis}`, 'ai');
                }}
                onDismiss={() => {
                  const id = log.id;
                  setLogs(prev => prev.map(l => l.id === id ? { ...l, type: 'command' as const, text: '[upload]: cancelled' } : l));
                }}
              />
            ) : log.type === 'admin' ? (
              <AdminPanel
                featureFlags={log.adminFeatureFlags ?? featureFlags}
                toolFlags={log.adminToolFlags ?? toolFlags}
                walletAddress={walletAddress || ''}
                apiBase={API_BASE_URL}
                currentEnv={(sessionTenant || tenant)}
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
            ) : log.type === 'recon' ? (
              <ReconForm
                currentSystem={currentSystem}
                onScan={(message) => {
                  const id = log.id;
                  setLogs(prev => prev.map(l =>
                    l.id === id ? { ...l, type: 'command' as const, text: '[recon]: scanning...' } : l
                  ));
                  handleChatMessage(message);
                }}
                onDismiss={() => {
                  const id = log.id;
                  setLogs(prev => prev.map(l =>
                    l.id === id ? { ...l, type: 'command' as const, text: '[recon]: cancelled' } : l
                  ));
                }}
              />
            ) : (
              <span className="content">
                {log.action
                  ? <span className="terminal-cmd-link" onClick={() => handleCommand(log.action!)}>{log.text}</span>
                  : log.text
                }
                {log.copyText && (
                  <span
                    className="terminal-cmd-link copy-route-btn"
                    onClick={() => {
                      if (navigator.clipboard) {
                        navigator.clipboard.writeText(log.copyText!).catch(() => {});
                      } else {
                        const el = document.createElement('textarea');
                        el.value = log.copyText!;
                        el.style.position = 'absolute';
                        el.style.left = '-9999px';
                        document.body.appendChild(el);
                        el.select();
                        try { document.execCommand('copy'); } catch { /* ignore */ }
                        document.body.removeChild(el);
                      }
                    }}
                  >
                    {' '}[Copy Route]
                  </span>
                )}
              </span>
            )}
          </div>
        ))}
        <div ref={terminalEndRef} />
        {isStreaming && (
          <div className="terminal-line line-ai feral-flicker">
            <span className="content">
              <EveFeralCodeGen tickMs={feralTickMs} />
              <EveFeralCodeGen tickMs={Math.round(feralTickMs * 1.33)} />
              <EveFeralCodeGen tickMs={Math.round(feralTickMs * 0.67)} />
            </span>
          </div>
        )}
      </div>

      <form onSubmit={handleSubmit} className="terminal-input-area">
        <div className="input-wrapper">
          <span className="prompt">{'> '}</span>
          <div className="input-field-wrapper" onClick={() => inputRef.current?.focus()}>
            <div className="fake-input" aria-hidden="true">
              {inputValue ? (
                <span className="fake-input-text">{inputValue}</span>
              ) : (
                !isReady && (
                  <span className="fake-input-placeholder">
                    {!isConnected
                      ? 'Waiting for wallet...'
                      : !assemblyId
                        ? 'Waiting for structure...'
                        : 'Identifying...'}
                  </span>
                )
              )}
              {isFocused && !isLoading && <span className="cursor-blink">_</span>}
            </div>
            <input
              ref={inputRef}
              type="text"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleKeyDown}
              onFocus={() => setIsFocused(true)}
              onBlur={() => setIsFocused(false)}
              placeholder=""
              disabled={isLoading}
              autoFocus
              className="hidden-input"
            />
          </div>
          <button
            type="submit"
            disabled={isLoading || !inputValue.trim()}
            className="submit-btn"
          >
            {isLoading ? '...' : 'Send'}
          </button>
        </div>
      </form>

      {isLoading && (
        <div className="loading-indicator">HUGINN is processing...</div>
      )}
    </div>
  );
}
