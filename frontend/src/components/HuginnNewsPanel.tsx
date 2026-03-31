// src/components/HuginnNewsPanel.tsx

import { HuginnNewsData } from '../types/terminal';
import { DIVIDER } from '../constants/dividers';

interface HuginnNewsPanelProps {
  data: HuginnNewsData;
  onPrintToTerminal?: () => void;
}

const ASCII_HEADER = `
  ██╗  ██╗██╗   ██╗ ██████╗ ██╗███╗   ██╗███╗   ██╗
  ██║  ██║██║   ██║██╔════╝ ██║████╗  ██║████╗  ██║
  ███████║██║   ██║██║  ███╗██║██╔██╗ ██║██╔██╗ ██║
  ██╔══██║██║   ██║██║   ██║██║██║╚██╗██║██║╚██╗██║
  ██║  ██║╚██████╔╝╚██████╔╝██║██║ ╚████║██║ ╚████║
  ╚═╝  ╚═╝ ╚═════╝  ╚═════╝ ╚═╝╚═╝  ╚═══╝╚═╝  ╚═══╝`.trimStart();

export function HuginnNewsPanel({ data, onPrintToTerminal }: HuginnNewsPanelProps) {
  const date = data.generated_at
    ? data.generated_at.replace('T', ' ').replace('Z', ' UTC').slice(0, 20)
    : '';

  const header = [
    ASCII_HEADER,
    DIVIDER,
    `  S I G N A L   T R A N S M I S S I O N`,
    date ? `  ${date}` : '',
    DIVIDER,
  ].filter(Boolean).join('\n');

  return (
    <>
      <pre style={{ whiteSpace: 'pre-wrap', wordWrap: 'break-word' }}>
        {header}
      </pre>
      {onPrintToTerminal && (
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
            {'  [ PRINT ARTICLE ]'}
          </span>
        </div>
      )}
    </>
  );
}
