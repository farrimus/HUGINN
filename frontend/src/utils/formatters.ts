// src/utils/formatters.ts
// Shared text/number formatting primitives used across panel components and TerminalUI.

export function pad(s: string, len: number): string {
  return s.slice(0, len).padEnd(len);
}

export function padR(s: string, len: number): string {
  return s.slice(0, len).padStart(len);
}

export function fmtNum(n: number): string {
  return Math.round(n).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
}

export function fmtVol(n: number): string {
  return n.toFixed(2);
}

// Clipboard copy via execCommand fallback (works on HTTP, no HTTPS requirement)
export function copyText(text: string): boolean {
  try {
    const el = document.createElement('textarea');
    el.value = text;
    el.style.cssText = 'position:fixed;top:0;left:0;opacity:0;pointer-events:none';
    document.body.appendChild(el);
    el.focus();
    el.select();
    const ok = document.execCommand('copy');
    document.body.removeChild(el);
    return ok;
  } catch {
    return false;
  }
}
