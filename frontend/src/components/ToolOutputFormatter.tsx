// src/components/ToolOutputFormatter.tsx

import { useState } from 'react';
import {
  ToolType,
  SystemIntelData,
  ThreatAssessmentData,
  PilotProfileData,
  MemorySearchData,
  MemorySummaryData,
  NetworkMapData,
  NodesListData,
  InventoryData,
  AssetMapData,
  RouteData,
  BuildOptionsData,
} from '../types/terminal';
import { NetworkMapPanel } from './NetworkMapPanel';
import { NodesListPanel } from './NodesListPanel';
import { InventoryPanel } from './InventoryPanel';
import { AssetMapPanel } from './AssetMapPanel';
import { RoutePanel } from './RoutePanel';

import { DIVIDER } from '../constants/dividers';
import { copyText } from '../utils/formatters';

interface ToolOutputFormatterProps {
  toolType: ToolType;
  data: any;
  onPrintToTerminal?: () => void;
  onPrintNode?: (nodeId: string) => void;
}

const padLabel = (label: string): string => {
  const padding = 38;
  return label.padEnd(padding, ' ');
};

const truncateValue = (value: string, maxLen: number = 30): string => {
  return value.length > maxLen ? value.substring(0, maxLen - 3) + '...' : value;
};

function formatSystemIntel(data: SystemIntelData): string {
  const fields = [
    { label: 'SYSTEM:', value: data.system || '[REDACTED]' },
    { label: 'STAR CLASS:', value: data.starClass || '[REDACTED]' },
    { label: 'MIN TEMP:', value: data.minTemp || '[REDACTED]' },
    { label: 'PLANETS:', value: data.planets || '[REDACTED]' },
    { label: 'LAGRANGE POINTS:', value: data.lagrangePoints ?? '[REDACTED]' },
    { label: 'KILLS (24H):', value: data.kills24h || '[REDACTED]' },
    { label: 'GATES:', value: data.gates || '[REDACTED]' },
  ];

  const lines = [
    DIVIDER,
    ...fields.map((f) => padLabel(f.label) + truncateValue(f.value)),
    DIVIDER,
  ];

  return lines.join('\n');
}

function formatThreat(data: ThreatAssessmentData): string {
  const fields = [
    { label: 'THREAT LEVEL:', value: data.level || '[REDACTED]' },
    { label: 'TOP AGGRESSOR:', value: data.topAggressor || '[REDACTED]' },
    { label: 'DOMINANT SHIP:', value: data.dominantShip || '[REDACTED]' },
    { label: 'ESCALATION:', value: data.escalation || '[REDACTED]' },
    { label: '', value: '' },
    { label: '', value: '' },
  ];

  const lines = [
    DIVIDER,
    ...fields.map((f) =>
      f.label ? padLabel(f.label) + truncateValue(f.value) : ''
    ),
    DIVIDER,
  ];

  return lines.join('\n');
}

function formatPilotProfile(data: PilotProfileData): string {
  const fields = [
    { label: 'VISITS:', value: data.visits || '[REDACTED]' },
    { label: 'FIRST VISIT:', value: data.firstVisit || '[REDACTED]' },
    { label: 'LAST VISIT:', value: data.lastVisit || '[REDACTED]' },
    { label: 'TIER:', value: data.tier || '[REDACTED]' },
    { label: '', value: '' },
    { label: '', value: '' },
  ];

  const lines = [
    DIVIDER,
    ...fields.map((f) =>
      f.label ? padLabel(f.label) + truncateValue(f.value) : ''
    ),
    DIVIDER,
  ];

  return lines.join('\n');
}

function formatMemorySearch(data: MemorySearchData): string {
  const results = data.results || [];
  const lines = [
    DIVIDER,
    padLabel('QUERY:') + truncateValue(data.query || '[REDACTED]'),
    padLabel('RESULTS:'),
    ...results.slice(0, 3).map((r) => '  • ' + truncateValue(r)),
    ...(results.length > 3 ? ['  ...'] : []),
    DIVIDER,
  ];

  return lines.join('\n');
}

function formatMemorySummary(data: MemorySummaryData): string {
  const fields = [
    { label: 'ATTACKS:', value: data.attacks || '[REDACTED]' },
    { label: 'CONTACTS:', value: data.contacts || '[REDACTED]' },
    { label: 'DOCKING:', value: data.docking || '[REDACTED]' },
    { label: '', value: '' },
    { label: '', value: '' },
    { label: '', value: '' },
  ];

  const lines = [
    DIVIDER,
    ...fields.map((f) =>
      f.label ? padLabel(f.label) + truncateValue(f.value) : ''
    ),
    DIVIDER,
  ];

  return lines.join('\n');
}

export function fmtBuildStep(s: NonNullable<BuildOptionsData['buildOrder']>[number]): string {
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
}

function BuildOrderPanel({ data, onPrintToTerminal }: { data: BuildOptionsData; onPrintToTerminal?: () => void }) {
  // Single-target view
  if (data.targetName) {
    const lines: string[] = [DIVIDER];
    lines.push(padLabel('TARGET:') + data.targetName);
    if (data.targetMaterials) {
      for (const [item, qty] of Object.entries(data.targetMaterials)) {
        lines.push(padLabel('  REQUIRES:') + `${qty}x ${item}`);
      }
    }
    lines.push(padLabel('STATUS:') + (data.targetBuildable ? 'FULLY STOCKED' : 'MATERIALS SHORT'));
    if (data.almostBuildable.length > 0) {
      const e = data.almostBuildable[0];
      for (const [item, qty] of Object.entries(e.shortfalls)) {
        lines.push(padLabel('  SHORT:') + `${qty}x ${item}`);
      }
    }
    lines.push(DIVIDER);
    return <pre style={{ whiteSpace: 'pre-wrap', wordWrap: 'break-word' }}>{lines.join('\n')}</pre>;
  }

  const steps = data.buildOrder ?? [];
  const CAP = 10;
  const shown = steps.slice(0, CAP);
  const rest = steps.length - CAP;

  const lines = [
    DIVIDER,
    `BUILD ORDER  L-POINTS: ${data.lagrangePoints}`,
    DIVIDER,
    ...shown.map(fmtBuildStep),
    ...(rest > 0 ? [`  ... and ${rest} more steps`] : []),
    DIVIDER,
  ];

  return (
    <>
      <pre style={{ whiteSpace: 'pre-wrap', wordWrap: 'break-word' }}>
        {lines.join('\n')}
      </pre>
      {onPrintToTerminal && rest > 0 && (
        <div style={{
          position: 'absolute',
          bottom: 0,
          left: 0,
          right: 0,
          background: 'linear-gradient(to bottom, transparent, #000 40%)',
          paddingTop: '40px',
          paddingBottom: '16px',
          paddingLeft: '16px',
        }}>
          <span
            onClick={onPrintToTerminal}
            style={{ cursor: 'pointer', textDecoration: 'underline' }}
          >
            {'  [ PRINT FULL LIST ]'}
          </span>
        </div>
      )}
    </>
  );
}

function SystemIntelPanel({ data }: { data: SystemIntelData }) {
  const [copyLabel, setCopyLabel] = useState('COPY LINK');
  const formatted = formatSystemIntel(data);

  function handleCopy() {
    if (!data.systemId) return;
    const xml = `<a href="showinfo:5//${data.systemId}">${data.system}</a>`;
    const ok = copyText(xml);
    setCopyLabel(ok ? 'COPIED' : 'FAILED');
    setTimeout(() => setCopyLabel('COPY LINK'), 2000);
  }

  return (
    <div>
      <pre style={{ whiteSpace: 'pre-wrap', wordWrap: 'break-word' }}>{formatted}</pre>
      {data.systemId && (
        <button className="panel-copy-btn" onClick={handleCopy}>
          {copyLabel}
        </button>
      )}
    </div>
  );
}

/**
 * Formats tool output into ASCII panel text
 * Handles all tool types: baseline, system_intel, threat, pilot, memory
 */
export function ToolOutputFormatter({
  toolType,
  data,
  onPrintToTerminal,
  onPrintNode,
}: ToolOutputFormatterProps) {
  let formatted = '';

  switch (toolType) {
    case 'system_intel':
      return <SystemIntelPanel data={data as SystemIntelData} />;
    case 'threat_assessment':
      formatted = formatThreat(data as ThreatAssessmentData);
      break;
    case 'pilot_profile':
      formatted = formatPilotProfile(data as PilotProfileData);
      break;
    case 'memory_search':
      formatted = formatMemorySearch(data as MemorySearchData);
      break;
    case 'memory_summary':
      formatted = formatMemorySummary(data as MemorySummaryData);
      break;
    case 'network_map':
      return <NetworkMapPanel data={data as NetworkMapData} onPrintToTerminal={onPrintToTerminal} />;
    case 'inventory':
      return <InventoryPanel data={data as InventoryData} onPrintToTerminal={onPrintToTerminal} />;
    case 'asset_map':
      return <AssetMapPanel data={data as AssetMapData} onPrintToTerminal={onPrintToTerminal} />;
    case 'route_planned':
      return <RoutePanel data={data as RouteData} />;
    case 'nodes_list':
      return <NodesListPanel data={data as NodesListData} onPrint={onPrintNode ?? (() => {})} />;
    case 'build_options':
      return <BuildOrderPanel data={data as BuildOptionsData} onPrintToTerminal={onPrintToTerminal} />;
    default:
      formatted = DIVIDER + '\n[UNKNOWN TOOL TYPE]\n' + DIVIDER;
  }

  return (
    <pre style={{ whiteSpace: 'pre-wrap', wordWrap: 'break-word' }}>
      {formatted}
    </pre>
  );
}
