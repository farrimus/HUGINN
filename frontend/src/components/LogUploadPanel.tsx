// src/components/LogUploadPanel.tsx
//
// Inline upload panel for EVE Frontier client logs.
// Supports folder selection (webkitdirectory) and manual multi-file selection.
// Filters by subdirectory (Chatlogs/Local_* and Gamelogs/YYYYMMDD_*) and date cutoff.
// Passes wallet address and webkitRelativePath per file for server-side tracking.

import { useRef, useState } from 'react';

interface LogUploadPanelProps {
  apiBaseUrl: string;
  walletAddress: string | null;
  onResult: (analysis: string, meta: { files: number; skipped: number; events: number; systems: string[] }) => void;
  onDismiss: () => void;
}

// Minimum date tag (YYYYMMDD) — client-side pre-filter, server enforces the same.
const DATE_CUTOFF = '20260311';

const CHATLOG_NAME_RE = /^Local_(\d{8})_/i;
const GAMELOG_NAME_RE = /^(\d{8})_/;

interface MatchedFile {
  file: File;
  relativePath: string;   // webkitRelativePath or '' for manual selection
  logType: 'chatlog' | 'gamelog';
}

function extractDateTag(name: string): string | null {
  let m = CHATLOG_NAME_RE.exec(name);
  if (m) return m[1];
  m = GAMELOG_NAME_RE.exec(name);
  if (m) return m[1];
  return null;
}

function classifyByPath(name: string, relativePath: string): 'chatlog' | 'gamelog' | null {
  if (relativePath) {
    // Use the immediate parent directory to determine which subfolder this file is in.
    // webkitRelativePath: "Gamelogs/Chatlogs/Local_20260315_xxx.txt"
    const parts = relativePath.replace(/\\/g, '/').split('/');
    const parentDir = parts.length >= 2 ? parts[parts.length - 2].toLowerCase() : '';

    if (parentDir === 'chatlogs') return CHATLOG_NAME_RE.test(name) ? 'chatlog' : null;
    if (parentDir === 'gamelogs') return GAMELOG_NAME_RE.test(name) ? 'gamelog' : null;
    return null; // wrong subfolder (Fleetlogs, Marketlogs, etc.)
  }

  // Manual selection — no path info, classify by filename pattern only
  if (CHATLOG_NAME_RE.test(name)) return 'chatlog';
  if (GAMELOG_NAME_RE.test(name)) return 'gamelog';
  return null;
}

function filterFiles(fileList: FileList): MatchedFile[] {
  const matched: MatchedFile[] = [];
  for (let i = 0; i < fileList.length; i++) {
    const file = fileList[i];
    const relativePath = (file as File & { webkitRelativePath?: string }).webkitRelativePath || '';
    const name = file.name;

    // Date pre-filter
    const dateTag = extractDateTag(name);
    if (!dateTag || dateTag < DATE_CUTOFF) continue;

    const logType = classifyByPath(name, relativePath);
    if (!logType) continue;

    matched.push({ file, relativePath, logType });
  }
  return matched;
}

type PanelState = 'idle' | 'ready' | 'uploading' | 'done' | 'error';

export function LogUploadPanel({ apiBaseUrl, walletAddress, onResult, onDismiss }: LogUploadPanelProps) {
  const folderInputRef = useRef<HTMLInputElement>(null);
  const filesInputRef  = useRef<HTMLInputElement>(null);

  const [state, setState]      = useState<PanelState>('idle');
  const [matched, setMatched]  = useState<MatchedFile[]>([]);
  const [statusMsg, setStatus] = useState('');

  const handleFileSelection = (fileList: FileList | null) => {
    if (!fileList || fileList.length === 0) return;
    const found = filterFiles(fileList);
    if (found.length === 0) {
      setStatus(
        'No matching files found. Select the Gamelogs folder (contains Chatlogs/ and Gamelogs/ subfolders), ' +
        'or individual Local_YYYYMMDD_* and YYYYMMDD_* files from 2026.03.11 onward.'
      );
      return;
    }
    setMatched(found);
    setState('ready');
    setStatus('');
  };

  const handleUpload = async () => {
    if (matched.length === 0) return;
    setState('uploading');
    setStatus(`Transmitting ${matched.length} file(s) to HUGINN...`);

    const form = new FormData();
    for (const { file } of matched) {
      form.append('files', file, file.name);
    }
    // Send relative paths as a JSON array (same order as files)
    form.append('relative_paths', JSON.stringify(matched.map(m => m.relativePath)));
    if (walletAddress) {
      form.append('wallet_address', walletAddress);
    }

    try {
      const res = await fetch(`${apiBaseUrl}/logs/upload`, {
        method: 'POST',
        body: form,
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }
      const data = await res.json();
      setState('done');
      onResult(data.analysis, {
        files:   data.files_processed,
        skipped: data.files_skipped ?? 0,
        events:  data.event_count,
        systems: data.systems_visited,
      });
    } catch (err) {
      setState('error');
      setStatus(`Upload failed: ${err instanceof Error ? err.message : String(err)}`);
    }
  };

  const chatlogCount = matched.filter(f => f.logType === 'chatlog').length;
  const gamelogCount = matched.filter(f => f.logType === 'gamelog').length;

  return (
    <div className="upload-panel">
      {/* Hidden inputs */}
      <input
        ref={folderInputRef}
        type="file"
        // @ts-expect-error webkitdirectory is non-standard but supported in Chromium
        webkitdirectory=""
        multiple
        style={{ display: 'none' }}
        onChange={e => handleFileSelection(e.target.files)}
      />
      <input
        ref={filesInputRef}
        type="file"
        multiple
        accept=".txt"
        style={{ display: 'none' }}
        onChange={e => handleFileSelection(e.target.files)}
      />

      {state === 'idle' && (
        <>
          <div className="upload-title">FLIGHT RECORDER UPLOAD</div>
          <div className="upload-divider" />
          <div className="upload-body">
            HUGINN reconstructs your recent operations from client logs:
            systems visited, resources extracted, hostiles encountered.
          </div>
          <div className="upload-body upload-dim">Files accepted (2026.03.11 onward):</div>
          <div className="upload-body upload-dim">{'  '}Chatlogs/Local_YYYYMMDD_*  — system location</div>
          <div className="upload-body upload-dim">{'  '}Gamelogs/YYYYMMDD_*        — activity events</div>
          <div className="upload-body upload-dim">
            {'  '}Path: Documents\Frontier\logs\Gamelogs
          </div>
          <div className="upload-divider" />
          {statusMsg && <div className="upload-status upload-warn">{statusMsg}</div>}
          <div className="upload-actions">
            <span className="terminal-cmd-link" onClick={() => folderInputRef.current?.click()}>
              [ SELECT FOLDER ]
            </span>
            <span className="upload-sep" />
            <span className="terminal-cmd-link" onClick={() => filesInputRef.current?.click()}>
              [ SELECT FILES ]
            </span>
            <span className="upload-sep" />
            <span className="terminal-cmd-link upload-cancel" onClick={onDismiss}>
              [ CANCEL ]
            </span>
          </div>
        </>
      )}

      {state === 'ready' && (
        <>
          <div className="upload-title">FLIGHT RECORDER UPLOAD</div>
          <div className="upload-divider" />
          <div className="upload-status">
            {matched.length} file(s) matched — {chatlogCount} chatlog, {gamelogCount} gamelog
          </div>
          <div className="upload-file-list">
            {matched.slice(0, 12).map(({ file, logType }) => (
              <div key={file.name} className="upload-file-entry">
                {'  '}{logType === 'chatlog' ? 'C' : 'G'}{'  '}{file.name}
              </div>
            ))}
            {matched.length > 12 && (
              <div className="upload-dim">  ...and {matched.length - 12} more</div>
            )}
          </div>
          <div className="upload-divider" />
          <div className="upload-actions">
            <span className="terminal-cmd-link" onClick={handleUpload}>
              [ UPLOAD TO HUGINN ]
            </span>
            <span className="upload-sep" />
            <span className="terminal-cmd-link upload-cancel" onClick={() => { setState('idle'); setMatched([]); }}>
              [ BACK ]
            </span>
          </div>
        </>
      )}

      {state === 'uploading' && (
        <div className="upload-status">{statusMsg}</div>
      )}

      {state === 'done' && (
        <div className="upload-status upload-ok">Transmission complete.</div>
      )}

      {state === 'error' && (
        <>
          <div className="upload-status upload-warn">{statusMsg}</div>
          <div className="upload-actions">
            <span className="terminal-cmd-link" onClick={() => { setState('idle'); setMatched([]); setStatus(''); }}>
              [ RETRY ]
            </span>
            <span className="upload-sep" />
            <span className="terminal-cmd-link upload-cancel" onClick={onDismiss}>
              [ CANCEL ]
            </span>
          </div>
        </>
      )}
    </div>
  );
}
