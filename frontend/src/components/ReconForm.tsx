import { useState } from 'react';

interface ReconFormProps {
  currentSystem: string;
  onScan: (message: string) => void;
  onDismiss: () => void;
}

export function ReconForm({ currentSystem, onScan, onDismiss }: ReconFormProps) {
  const [system, setSystem] = useState(currentSystem || '');
  const [radius, setRadius] = useState('100');

  const handleScan = () => {
    const s = system.trim();
    if (!s) return;
    const r = parseFloat(radius);
    const ly = isNaN(r) || r <= 0 ? 100 : r;
    onScan(
      `Recon scan: center system ${s}, radius ${ly} LY. ` +
      `Report kill activity in the last 24 hours, threat assessment, and any notable systems or contacts.`
    );
  };

  return (
    <div className="recon-form">
      <div className="recon-header">RECON — AREA SCAN</div>
      <div className="recon-fields">
        <div className="recon-field">
          <span className="recon-label">CENTER</span>
          <input
            className="recon-input"
            value={system}
            onChange={e => setSystem(e.target.value)}
            placeholder="system name"
            onKeyDown={e => { if (e.key === 'Enter') handleScan(); }}
            autoFocus
          />
        </div>
        <div className="recon-field">
          <span className="recon-label">RADIUS</span>
          <input
            className="recon-input recon-input-short"
            value={radius}
            onChange={e => setRadius(e.target.value)}
            placeholder="LY"
            type="number"
            min="1"
            onKeyDown={e => { if (e.key === 'Enter') handleScan(); }}
          />
          <span className="recon-unit">LY</span>
        </div>
      </div>
      <div className="recon-actions">
        <button
          className="recon-btn recon-btn-primary"
          onClick={handleScan}
          disabled={!system.trim()}
        >
          SCAN
        </button>
        <button className="recon-btn" onClick={onDismiss}>
          CANCEL
        </button>
      </div>
    </div>
  );
}
