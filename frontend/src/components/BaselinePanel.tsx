// src/components/BaselinePanel.tsx

import { BaselinePanelData } from '../types/terminal';
import { DIVIDER, SUBDIV } from '../constants/dividers';

interface BaselinePanelProps {
  data: BaselinePanelData;
}

const ART = [
  '  ⣇⣸ ⡇⢸ ⡎⠑ ⡇ ⡷⣸ ⡷⣸',
  '  ⠇⠸ ⠣⠜ ⠣⠝ ⠇ ⠇⠹ ⠇⠹',
];
const ART_WIDTH = 22; // chars reserved for left art column (+ separator)
const SEP = '  │  ';

function pad(label: string, width = 22): string {
  return label.padEnd(width);
}

function trunc(value: string, max = 36): string {
  return value.length > max ? value.slice(0, max - 3) + '...' : value;
}

/**
 * Displays baseline player information panel with optional enrichment.
 *
 * Header: Braille HUGINN art (left) | ASSEMBLY / OWNER+TRIBE+LOCATION (right)
 * Section B — visitor: SHELL NAME, SIGNATURE, ACCESS LEVEL
 * Section A — game type (when available)
 * Section D — network node / fuel (when available)
 */
export function BaselinePanel({ data }: BaselinePanelProps) {
  const lines: string[] = [DIVIDER];

  // Header — art box left, assembly info right
  const assembly = trunc(data.assemblySignature || '[REDACTED]', 45);
  const owner    = data.ownerCharacterName || '[REDACTED]';
  const tribe    = data.ownerTribeName || data.ownerTribeId || '[REDACTED]';
  const location = trunc(data.location     || '[REDACTED]', 16);

  const rightRow1 = `ID  ${assembly}`;
  const rightRow2 = `OWNER  ${owner}   TRIBE  ${tribe}   LOCATION  ${location}`;

  lines.push(ART[0].padEnd(ART_WIDTH) + SEP + rightRow1);
  lines.push(ART[1].padEnd(ART_WIDTH) + SEP + rightRow2);

  // Section B — visitor identity
  lines.push(SUBDIV);
  lines.push(pad('SHELL NAME')   + trunc(data.shellName   || '[REDACTED]'));
  lines.push(pad('SIGNATURE')    + trunc(data.signature   || '[REDACTED]'));
  lines.push(pad('ACCESS LEVEL') + trunc(data.accessLevel || '[REDACTED]'));

  // Section A — game type (when enriched)
  if (data.gameTypeName || data.enrichmentLoading) {
    lines.push(SUBDIV);
    if (data.enrichmentLoading) {
      lines.push(pad('TYPE') + '[ LOADING... ]');
    } else {
      lines.push(pad('TYPE') + trunc(data.gameTypeName || '[REDACTED]'));
      if (data.gameTypeCategory) {
        lines.push(pad('CATEGORY') + trunc(data.gameTypeCategory));
      }
    }
  }

  // Section D — network fuel line
  if (data.networkNodeName || data.fuelPercent !== undefined) {
    lines.push(SUBDIV);
    if (data.networkNodeName) {
      lines.push(pad('NETWORK NODE') + trunc(data.networkNodeName));
    }
    if (data.fuelPercent !== undefined) {
      if (!data.fuelBurning) {
        lines.push(pad('FUEL') + 'NOT BURNING');
      } else if (data.fuelDaysRemaining === '0' || data.fuelDaysRemaining === '0.0') {
        const fuelLabel = (data.fuelQuantity !== undefined && data.fuelEffectiveMax !== undefined)
          ? `${data.fuelQuantity} / ${data.fuelEffectiveMax} units`
          : `${data.fuelPercent}`;
        lines.push(pad('FUEL') + `${fuelLabel}  DEPLETED`);
      } else {
        const fuelLabel = (data.fuelQuantity !== undefined && data.fuelEffectiveMax !== undefined)
          ? `${data.fuelQuantity} / ${data.fuelEffectiveMax} units`
          : `${data.fuelPercent}`;
        lines.push(pad('FUEL') + `${fuelLabel}  ~${data.fuelDaysRemaining} remaining`);
      }
    }
  }

  lines.push(DIVIDER);

  return (
    <pre style={{ whiteSpace: 'pre-wrap', wordWrap: 'break-word' }}>
      {lines.join('\n')}
    </pre>
  );
}
