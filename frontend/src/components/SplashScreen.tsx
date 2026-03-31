// src/components/SplashScreen.tsx

import { useState, useEffect } from 'react';
import '../styles/splash.css';

const ART_LINES = [
  '██╗  ██╗ ██╗   ██╗  ██████╗  ██╗ ███╗   ██╗ ███╗   ██╗',
  '██║  ██║ ██║   ██║ ██╔════╝  ██║ ████╗  ██║ ████╗  ██║',
  '███████║ ██║   ██║ ██║  ███╗ ██║ ██╔██╗ ██║ ██╔██╗ ██║',
  '██╔══██║ ██║   ██║ ██║   ██║ ██║ ██║╚██╗██║ ██║╚██╗██║',
  '██║  ██║ ╚██████╔╝ ╚██████╔╝ ██║ ██║ ╚████║ ██║ ╚████║',
  '╚═╝  ╚═╝  ╚═════╝   ╚═════╝  ╚═╝ ╚═╝  ╚═══╝ ╚═╝  ╚═══╝',
];

const LOADING_LINES = [
  'VERIFYING SIGNATURE RESONANCE...',
  'HANDSHAKING WITH CLUSTER CONSENSUS LAYER...',
  'VERIFYING STRUCTURE ACCESS PROTOCOLS...',
  'ESTABLISHING SECURE COMM UPLINK...',
  'LOADING ENTITY RESPONSE MATRIX...',
  'SCANNING ASSEMBLY SIGNATURE REGISTRY...',
  'CALIBRATING THREAT ASSESSMENT ARRAY...',
  'DECRYPTING ASSEMBLY STATE REGISTER...',
  'SYNCHRONIZING TEMPORAL ANCHOR NODE...',
];

const MAX_LEN = Math.max(...ART_LINES.map(l => l.length));

interface SplashScreenProps {
  onComplete: () => void;
}

export function SplashScreen({ onComplete }: SplashScreenProps) {
  const [revealedChars, setRevealedChars] = useState(0);
  const [phase, setPhase] = useState<'typing' | 'loading' | 'exiting'>('typing');
  const [loadingIdx, setLoadingIdx] = useState(0);
  const [isExiting, setIsExiting] = useState(false);

  // Phase 1: reveal all art lines simultaneously, one character per tick
  useEffect(() => {
    if (phase !== 'typing') return;
    const id = setInterval(() => {
      setRevealedChars(prev => {
        const next = prev + 1;
        if (next >= MAX_LEN) {
          setPhase('loading');
          return MAX_LEN;
        }
        return next;
      });
    }, 40);
    return () => clearInterval(id);
  }, [phase]);

  // Phase 2: cycle loading lines for ~1000ms, then signal exit
  useEffect(() => {
    if (phase !== 'loading') return;
    const lineId = setInterval(() => setLoadingIdx(prev => prev + 1), 180);
    const exitId = setTimeout(() => {
      clearInterval(lineId);
      setIsExiting(true);
      onComplete();
    }, 1000);
    return () => {
      clearInterval(lineId);
      clearTimeout(exitId);
    };
  }, [phase, onComplete]);

  return (
    <div className={`splash-screen${isExiting ? ' splash-exit' : ''}`}>
      <div className="splash-art">
        {ART_LINES.map((line, i) => (
          <div key={i}>{line.slice(0, revealedChars) || '\u00A0'}</div>
        ))}
      </div>
      <div className={`splash-subtitle${phase !== 'typing' ? ' splash-subtitle-lit' : ''}`}>
        HEURISTIC UNIFIED GRID INTELLIGENCE NETWORK NODE
      </div>
      <div className="splash-loading">
        {phase === 'loading' ? LOADING_LINES[loadingIdx % LOADING_LINES.length] : '\u00A0'}
      </div>
    </div>
  );
}
