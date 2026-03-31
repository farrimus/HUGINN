import { useState } from 'react';
import { FEATURES, FeatureFlags, TOOLS, ToolFlags } from '../features/featureFlags';

interface AdminPanelProps {
  featureFlags: FeatureFlags;
  toolFlags: ToolFlags;
  onApply: (features: FeatureFlags, tools: ToolFlags) => void;
}

export function AdminPanel({ featureFlags, toolFlags, onApply }: AdminPanelProps) {
  const [features, setFeatures] = useState<FeatureFlags>({ ...featureFlags });
  const [tools, setTools] = useState<ToolFlags>({ ...toolFlags });

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
          {TOOLS.map(tool => (
            <label key={tool.name} className="admin-row">
              <input
                type="checkbox"
                checked={!!tools[tool.name]}
                onChange={e => setTools(prev => ({ ...prev, [tool.name]: e.target.checked }))}
              />
              <span>{tool.label}</span>
            </label>
          ))}
        </div>
      </div>

      <div className="admin-footer">
        <button className="admin-btn" onClick={() => onApply(features, tools)}>
          APPLY
        </button>
        <span className="admin-note">Tool changes take effect on next message.</span>
      </div>
    </div>
  );
}
