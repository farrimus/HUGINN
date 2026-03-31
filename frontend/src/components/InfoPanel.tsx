// src/components/InfoPanel.tsx

import { useState, useEffect, useRef, useCallback } from 'react';
import { ToolType, ToolOutputData, BaselinePanelData, GateInfoData, HuginnNewsData } from '../types/terminal';
import { BaselinePanel } from './BaselinePanel';
import { GateInfoPanel } from './GateInfoPanel';
import { HuginnNewsPanel } from './HuginnNewsPanel';
import { ToolOutputFormatter } from './ToolOutputFormatter';
import { SplashScreen } from './SplashScreen';
import '../styles/info-panel.css';

interface InfoPanelProps {
  currentToolType: ToolType | null;
  currentData: ToolOutputData | null;
  isAnimating: boolean;
  onAnimationEnd: () => void;
  onPrintToTerminal?: () => void;
  onPrintNode?: (nodeId: string) => void;
  useTypingEffect?: boolean;
  showSplash?: boolean;
  onSplashComplete?: () => void;
  onNavCommand?: (command: string) => void;
  activeNavItems?: Array<{ label: string; command: string }>;
}

/**
 * Animated visual panel that displays tool outputs with slide transitions
 * - Slide out current content (250ms)
 * - Swap content
 * - Slide in new content (500ms)
 * Total: 750ms animation cycle
 */
export function InfoPanel({
  currentToolType,
  currentData,
  isAnimating,
  onAnimationEnd,
  onPrintToTerminal,
  onPrintNode,
  useTypingEffect: _useTypingEffect = false,
  showSplash = false,
  onSplashComplete,
  onNavCommand,
  activeNavItems,
}: InfoPanelProps) {
  const [displayContent, setDisplayContent] = useState<React.ReactNode>(null);
  const [isSliding, setIsSliding] = useState(false);

  // Keep stable callbacks that always call the latest handlers
  const onPrintRef = useRef(onPrintToTerminal);
  onPrintRef.current = onPrintToTerminal;
  const stablePrint = useCallback(() => onPrintRef.current?.(), []);

  const onPrintNodeRef = useRef(onPrintNode);
  onPrintNodeRef.current = onPrintNode;
  const stablePrintNode = useCallback((nodeId: string) => onPrintNodeRef.current?.(nodeId), []);

  useEffect(() => {
    if (!isAnimating || !currentToolType || !currentData) {
      setDisplayContent(getContentComponent(currentToolType, currentData, stablePrint, stablePrintNode));
      setIsSliding(false);
      return;
    }

    // Start slide-out animation
    setIsSliding(true);

    const slideOutTimer = setTimeout(() => {
      // Swap content
      setDisplayContent(getContentComponent(currentToolType, currentData, stablePrint, stablePrintNode));

      // Start slide-in animation
      const slideInTimer = setTimeout(() => {
        setIsSliding(false);
        onAnimationEnd();
      }, 500);

      return () => clearTimeout(slideInTimer);
    }, 250);

    return () => clearTimeout(slideOutTimer);
  }, [currentToolType, currentData, isAnimating, onAnimationEnd]);

  const wrapperClass = isSliding ? 'slide-out-right' : '';

  return (
    <>
      <div id="visual-area" className={wrapperClass}>
        {displayContent}
        {showSplash && onSplashComplete && (
          <SplashScreen onComplete={onSplashComplete} />
        )}
      </div>
      {onNavCommand && activeNavItems && activeNavItems.length > 0 && (
        <div className="info-panel-nav">
          {activeNavItems.map(({ label, command }) => (
            <span
              key={command}
              className="info-panel-nav-item"
              onClick={() => onNavCommand(command)}
            >
              {label}
            </span>
          ))}
        </div>
      )}
    </>
  );
}

function getContentComponent(
  toolType: ToolType | null,
  data: ToolOutputData | null,
  onPrintToTerminal?: () => void,
  onPrintNode?: (nodeId: string) => void,
): React.ReactNode {
  if (!toolType || !data) {
    return <BaselinePanel data={{
      crudVersion: 'HUGINN - Version',
      signature: '[REDACTED]',
      shellName: '[REDACTED]',
      accessLevel: '[REDACTED]',
      assemblySignature: '[REDACTED]',
      location: '[REDACTED]'
    }} />;
  }

  if (toolType === 'baseline') {
    return <BaselinePanel data={data as BaselinePanelData} />;
  }

  if (toolType === 'gate_info') {
    return <GateInfoPanel data={data as GateInfoData} />;
  }

  if (toolType === 'huginn_news') {
    return <HuginnNewsPanel data={data as HuginnNewsData} onPrintToTerminal={onPrintToTerminal} />;
  }

  return <ToolOutputFormatter toolType={toolType} data={data} onPrintToTerminal={onPrintToTerminal} onPrintNode={onPrintNode} />;
}
