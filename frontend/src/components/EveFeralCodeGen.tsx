// src/components/EveFeralCodeGen.tsx
// Ported from @eveworld/ui-components — ambient lore texture during streaming.

import { useState, useEffect } from 'react';

const randomCode = (): string => {
  const characters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789------------------------------...';
  const length = Math.floor(Math.random() * (10 - 3 + 1)) + 3;
  let value = '';
  for (let i = 0; i < length; i++) {
    value += characters.charAt(Math.floor(Math.random() * characters.length));
  }
  return value;
};

const randomGlyphs = (): string => {
  const choices = [0, 0, 0, 1, 1, 2];
  const count = choices[Math.floor(Math.random() * choices.length)];
  return '▮'.repeat(count);
};

interface Target {
  code1: string;
  glyphs: string;
  hasLine2: boolean;
  code2: string;
  isRed: boolean;
}

const generateTarget = (): Target => ({
  code1: randomCode(),
  glyphs: randomGlyphs(),
  hasLine2: Math.random() < 0.2,
  code2: randomCode(),
  isRed: Math.random() >= 0.85,
});

interface EveFeralCodeGenProps {
  tickMs?: number;
  charMs?: number;
}

export function EveFeralCodeGen({ tickMs = 300, charMs = 40 }: EveFeralCodeGenProps) {
  const [target, setTarget] = useState<Target>(generateTarget);
  const [revealed, setRevealed] = useState(0);

  // Reveal one character at a time
  useEffect(() => {
    if (revealed >= target.code1.length) return;
    const id = setTimeout(() => setRevealed(r => r + 1), charMs);
    return () => clearTimeout(id);
  }, [revealed, target.code1.length, charMs]);

  // Once fully revealed, hold then cycle to a new target
  useEffect(() => {
    if (revealed < target.code1.length) return;
    const id = setTimeout(() => {
      setTarget(generateTarget());
      setRevealed(0);
    }, tickMs);
    return () => clearTimeout(id);
  }, [revealed, target.code1.length, tickMs]);

  const visible = target.code1.slice(0, revealed);
  const fullyRevealed = revealed >= target.code1.length;

  return (
    <div className={`feral-jitter${target.isRed ? ' text-martianred-5' : ''}`}>
      {visible}
      {!fullyRevealed && <span className="cursor-blink">▮</span>}
      {fullyRevealed ? target.glyphs : ''}
      {fullyRevealed && target.hasLine2 ? <><br />{target.code2}</> : null}
    </div>
  );
}
