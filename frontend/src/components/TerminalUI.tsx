import { useState, useRef, useEffect, useCallback } from 'react';
import { useQuery } from '@tanstack/react-query';
import { abbreviateAddress, getDatahubGameInfo } from '@evefrontier/dapp-kit';
import { useWalletReady } from '../hooks/useWalletReady';
import { useChatPayload } from '../hooks/useChatPayload';
import { fetchAndFormatNode } from '../utils/printNode';
import { createDispatcher } from '../commands/index';
import { printRouteToChat, printToTerminal } from '../commands/printFormatters';
import { buildBaselineData } from '../utils/baselineBuilder';
import type { TerminalLog } from '../types/terminal';
import { useToolOutput } from '../hooks/useToolOutput';
import { BaselinePanelData } from '../types/terminal';
import { TripCalculatorForm } from './TripCalculatorForm';
import { BUILD_TIME } from '../main';
import { useCompanionStream } from '../hooks/useCompanionStream';
import { EveFeralCodeGen } from './EveFeralCodeGen';
import { useWatcherAlerts } from '../hooks/useWatcherAlerts';
import { useTribePosts, TribePostEvent } from '../hooks/useTribePosts';
import { useEntityContext } from '../context/EntityContext';
import { useSession } from '../hooks/useSession';
import { InfoPanel } from './InfoPanel';
import { BoardPanel } from './BoardPanel';
import { LogUploadPanel } from './LogUploadPanel';
import { AdminPanel } from './AdminPanel';
import { ReconForm } from './ReconForm';
import {
  getDisabledTools, FEATURES,
  saveCachedAdminConfig,
} from '../features/featureFlags';
import { getActiveNavItemsForTier } from '../features/tierCapabilities';
import type { WatcherAlert, RouteData, ChatMessage } from '../types/terminal';

const API_BASE_URL = window.location.origin;

/**
 * TerminalUI Component
 * CLI interface for the structure companion chat.
 * Wallet and assembly resolved via dapp-kit. Chat via /companion/chat.
 */
export function TerminalUI() {
  const {
    isConnected, walletAddress, handleConnect, handleDisconnect, hasEveVault,
    assembly, assemblyId, itemId,
  } = useWalletReady();

  const { currentToolType, currentData, isAnimating, display: displayToolOutput, finishAnimation, setDirect } = useToolOutput();
  const { sendMessage } = useCompanionStream();
  const {
    enrichedAssembly,
    networkData,
    inventoryData,
    characterAssemblies,
    tenant,
  } = useEntityContext();

  // Game type enrichment from Datahub — populates the TYPE/CATEGORY block in BaselinePanel
  const { data: gameTypeData, isLoading: typeLoading } = useQuery({
    queryKey: ['datahub-type', enrichedAssembly?.type_id],
    queryFn: async () => {
      if (!enrichedAssembly?.type_id) return null;
      try {
        return await getDatahubGameInfo(Number(enrichedAssembly.type_id));
      } catch {
        return null;
      }
    },
    staleTime: Infinity,
    enabled: !!enrichedAssembly?.type_id,
  });

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
  const [cmdHistory, setCmdHistory] = useState<string[]>([]);
  const [historyIdx, setHistoryIdx] = useState(-1);
  const savedDraftRef = useRef('');
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
  } = useSession(walletAddress, assemblyId, tenant, assembly?.solarSystem?.name || currentSystem,
    characterAssemblies?.character_name || undefined);
  const terminalEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const hasGreeted = useRef(false);
  const activeBoardLogIdRef = useRef<string | null>(null);

  const isReady = isConnected && !!assemblyId && sessionRegistered;
  const resolvedCharName = visitorName || (walletAddress ? abbreviateAddress(walletAddress) : '');
  const { buildPayload } = useChatPayload({
    characterName: resolvedCharName,
    tenant: sessionTenant || tenant,
    systemFallback: currentSystem,
  });

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
    const baselineData = {
      ...buildBaselineData(walletAddress, assemblyId, visitorName, tier, location, enrichedAssembly),
      gameTypeName: (gameTypeData as Record<string, unknown> | null)?.name as string | undefined,
      gameTypeCategory: (gameTypeData as Record<string, unknown> | null)?.categoryName as string | undefined,
      enrichmentLoading: typeLoading && !!enrichedAssembly?.type_id,
    };

    latestBaselineRef.current = baselineData;

    // Splash still active — queue silently, do not animate
    if (!splashDoneRef.current) return;

    displayToolOutput('baseline', baselineData);
  }, [
    walletAddress, assemblyId, visitorName, tier,
    assembly?.solarSystem?.name, currentSystem,
    enrichedAssembly, gameTypeData, typeLoading, displayToolOutput,
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
      setInputValue(prev => prev + e.key);   // include the triggering character
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
      buildPayload(userInput, {
        history: chatHistory,
        debug: debugMode,
        disabled_tools: getDisabledTools(toolFlags),
        entity_snapshot: chatHistory.length === 0 ? {
          assembly: enrichedAssembly,
          network: networkData,
          inventory: inventoryData,
        } : null,
      }),
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
            printRouteToChat(data as RouteData, ctx);
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

  // CommandContext passed to the dispatcher and print formatters
  const ctx = {
    addLog, setLogs, isOff, displayToolOutput, currentToolType, currentData,
    walletAddress, assemblyId, isConnected, handleConnect, handleDisconnect, assembly,
    enrichedAssembly, networkData, inventoryData, characterAssemblies, tenant, sessionTenant,
    featureFlags, setFeatureFlags, toolFlags, setToolFlags, tier,
    visitorName, tribeId, toolRegistry,
    currentSystem, setCurrentSystem, setDebugMode,
    activeBoardLogIdRef, API_BASE_URL,
  };

  const handleCommand = createDispatcher(ctx);
  const onPrintToTerminal = () => printToTerminal(ctx);



  const handlePrintNode = async (nodeId: string): Promise<void> => {
    try {
      addLog(await fetchAndFormatNode(nodeId, sessionTenant || tenant, API_BASE_URL), 'info');
    } catch (err) {
      addLog(`Print failed: ${err instanceof Error ? err.message : String(err)}`, 'error');
    }
  };

  const doSubmit = async (): Promise<void> => {
    if (!inputValue.trim() || isLoading) return;
    const input = inputValue.trim();
    setInputValue('');
    setHistoryIdx(-1);
    savedDraftRef.current = '';
    setCmdHistory((prev) => {
      const deduped = prev[0] === input ? prev : [input, ...prev];
      return deduped.slice(0, 50);
    });
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
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      if (cmdHistory.length === 0) return;
      const next = historyIdx + 1;
      if (next >= cmdHistory.length) return;
      if (historyIdx === -1) savedDraftRef.current = inputValue;
      setHistoryIdx(next);
      setInputValue(cmdHistory[next]);
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      if (historyIdx === -1) return;
      const next = historyIdx - 1;
      setHistoryIdx(next);
      setInputValue(next === -1 ? savedDraftRef.current : cmdHistory[next]);
    }
  };

  return (
    <div className="terminal-ui">
      <InfoPanel
        currentToolType={currentToolType}
        currentData={currentData}
        isAnimating={isAnimating}
        onAnimationEnd={finishAnimation}
        onPrintToTerminal={onPrintToTerminal}
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
                  printRouteToChat(routeData as RouteData, ctx);
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
              {!isLoading && <span className="cursor-blink">_</span>}
            </div>
            <input
              ref={inputRef}
              type="text"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleKeyDown}

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
