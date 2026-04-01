import { useState, useEffect } from 'react';
import { FEATURES, FeatureFlags, ToolFlags, ToolRegistryEntry, TOOL_DEFAULTS, formatToolLabel } from '../features/featureFlags';

interface AdminPanelProps {
  featureFlags: FeatureFlags;
  toolFlags: ToolFlags;
  onApply: (features: FeatureFlags, tools: ToolFlags) => void;
  walletAddress?: string;
  apiBase?: string;
  currentEnv?: string;
  toolRegistry?: ToolRegistryEntry[];
}

export function AdminPanel({ featureFlags, toolFlags, onApply, walletAddress, apiBase, currentEnv, toolRegistry }: AdminPanelProps) {
  const [features, setFeatures] = useState<FeatureFlags>({ ...featureFlags });
  const [tools, setTools] = useState<ToolFlags>({ ...toolFlags });

  const [selectedEnv, setSelectedEnv] = useState(currentEnv || '');
  const [envOpen, setEnvOpen] = useState(false);
  const [vouches, setVouches] = useState<Record<string, string>>({});
  const [vouchInput, setVouchInput] = useState('');
  const [vouchTier, setVouchTier] = useState<'VETTED' | 'TRIBE'>('VETTED');
  const [tierOpen, setTierOpen] = useState(false);
  const [vouchLoading, setVouchLoading] = useState(false);

  useEffect(() => {
    if (!apiBase) return;
    fetch(`${apiBase}/admin/vouches?env=${selectedEnv}`)
      .then(r => r.ok ? r.json() : null)
      .then(data => { if (data?.overrides) setVouches(data.overrides); })
      .catch(() => {});
  }, [apiBase, selectedEnv]);

  const handleAdd = async () => {
    const w = vouchInput.trim();
    if (!w || !walletAddress || !apiBase) return;
    setVouchLoading(true);
    try {
      const res = await fetch(`${apiBase}/session/${encodeURIComponent(w)}/vouch`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Wallet-Address': walletAddress },
        body: JSON.stringify({ tier: vouchTier, env: selectedEnv }),
      });
      if (res.ok) {
        setVouches(prev => ({ ...prev, [w.toLowerCase()]: vouchTier }));
        setVouchInput('');
      }
    } finally {
      setVouchLoading(false);
    }
  };

  const handleRevoke = async (wallet: string) => {
    if (!walletAddress || !apiBase) return;
    const res = await fetch(
      `${apiBase}/session/${encodeURIComponent(wallet)}/vouch?env=${selectedEnv}`,
      { method: 'DELETE', headers: { 'X-Wallet-Address': walletAddress } }
    );
    if (res.ok) {
      setVouches(prev => { const next = { ...prev }; delete next[wallet]; return next; });
    }
  };

  return (
    <div className="admin-panel">
      <div className="admin-header">HUGINN ADMIN — OWNER ACCESS</div>

      <div className="admin-cols">
        <div className="admin-section">
          <div className="admin-section-label">FEATURES</div>
          {Object.entries(FEATURES).map(([key, def]) => (
            <label key={key} className="admin-row">
              <input
                type="checkbox"
                checked={!!features[key]}
                onChange={e => setFeatures(prev => ({ ...prev, [key]: e.target.checked }))}
              />
              <span>{def.label}</span>
            </label>
          ))}
        </div>

        <div className="admin-section">
          <div className="admin-section-label">HUGINN TOOLS</div>
          {(toolRegistry && toolRegistry.length > 0
            ? toolRegistry
            : Object.keys(TOOL_DEFAULTS).map(name => ({ name, category: 'tools', default_enabled: TOOL_DEFAULTS[name] }))
          ).map(tool => (
            <label key={tool.name} className="admin-row">
              <input
                type="checkbox"
                checked={tools[tool.name] !== undefined ? !!tools[tool.name] : tool.default_enabled}
                onChange={e => setTools(prev => ({ ...prev, [tool.name]: e.target.checked }))}
              />
              <span>{formatToolLabel(tool.name)}</span>
            </label>
          ))}
        </div>
      </div>

      {walletAddress && apiBase && (
        <div className="admin-section admin-vouches">
          <div className="admin-section-label">
            VETTED WALLETS
            <div className="admin-dd">
              <button className="admin-dd-trigger" onClick={() => setEnvOpen(o => !o)}>
                {selectedEnv} ▾
              </button>
              {envOpen && (
                <div className="admin-dd-options">
                  {['utopia', 'stillness'].map(env => (
                    <div
                      key={env}
                      className={`admin-dd-option${env === selectedEnv ? ' admin-dd-option-active' : ''}`}
                      onClick={() => { setSelectedEnv(env); setEnvOpen(false); }}
                    >
                      {env}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {Object.entries(vouches).length === 0 && (
            <div className="admin-row admin-empty">no vetted wallets</div>
          )}
          {Object.entries(vouches).map(([wallet, tier]) => (
            <div key={wallet} className="admin-row admin-vouch-row">
              <span className="admin-vouch-addr">{wallet.slice(0, 18)}…</span>
              <span className="admin-vouch-tier">{tier}</span>
              <button className="admin-btn admin-btn-sm" onClick={() => handleRevoke(wallet)}>
                REVOKE
              </button>
            </div>
          ))}

          <div className="admin-row admin-vouch-add">
            <input
              className="admin-input"
              placeholder="0x wallet address"
              value={vouchInput}
              onChange={e => setVouchInput(e.target.value)}
            />
            <div className="admin-dd">
              <button className="admin-dd-trigger" onClick={() => setTierOpen(o => !o)}>
                {vouchTier} ▾
              </button>
              {tierOpen && (
                <div className="admin-dd-options">
                  {(['VETTED', 'TRIBE'] as const).map(t => (
                    <div
                      key={t}
                      className={`admin-dd-option${t === vouchTier ? ' admin-dd-option-active' : ''}`}
                      onClick={() => { setVouchTier(t); setTierOpen(false); }}
                    >
                      {t}
                    </div>
                  ))}
                </div>
              )}
            </div>
            <button
              className="admin-btn admin-btn-sm"
              onClick={handleAdd}
              disabled={vouchLoading || !vouchInput.trim()}
            >
              {vouchLoading ? '…' : 'ADD'}
            </button>
          </div>
        </div>
      )}

      <div className="admin-footer">
        <button className="admin-btn" onClick={() => onApply(features, tools)}>
          APPLY
        </button>
        <span className="admin-note">Tool changes take effect on next message.</span>
      </div>
    </div>
  );
}
