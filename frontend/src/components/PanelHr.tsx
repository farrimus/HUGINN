// src/components/PanelHr.tsx
import '../styles/panel-lines.css';

interface PanelHrProps {
  light?: boolean;
}

export function PanelHr({ light = false }: PanelHrProps) {
  return <div className={`panel-hr ${light ? 'panel-hr-light' : 'panel-hr-heavy'}`} />;
}
