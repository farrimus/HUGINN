import { useState, useEffect, useRef, useCallback } from 'react';
import { SHIPS, FUELS, qualityFactor, fuelsForShip } from '../data/shipData';
import { useSystemNames } from '../hooks/useSystemNames';

interface SelectOption { value: string; label: string; }

function CustomSelect({ value, onChange, options }: {
  value: string;
  onChange: (v: string) => void;
  options: SelectOption[];
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  const selected = options.find(o => o.value === value);

  return (
    <div className="tc-dropdown" ref={ref}>
      <div className="tc-dropdown-trigger" onClick={() => setOpen(o => !o)}>
        <span>{selected?.label ?? value}</span>
        <span className="tc-dropdown-arrow">{open ? '▲' : '▼'}</span>
      </div>
      {open && (
        <div className="tc-dropdown-options">
          {options.map(o => (
            <div
              key={o.value}
              className={`tc-dropdown-option${o.value === value ? ' tc-dropdown-option-active' : ''}`}
              onMouseDown={() => { onChange(o.value); setOpen(false); }}
            >
              {o.label}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function SystemField({ value, onChange, onCommit, placeholder, apiBaseUrl }: {
  value: string;
  onChange: (v: string) => void;
  onCommit?: () => void;
  placeholder?: string;
  apiBaseUrl: string;
}) {
  const { search } = useSystemNames(apiBaseUrl);
  const [open, setOpen] = useState(false);
  const [activeIdx, setActiveIdx] = useState(-1);
  const blurTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const suggestions = open ? search(value) : [];

  const pick = (name: string) => {
    onChange(name);
    setOpen(false);
    setActiveIdx(-1);
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    onChange(e.target.value);
    setOpen(e.target.value.length >= 2);
    setActiveIdx(-1);
  };

  const handleKey = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (!open || suggestions.length === 0) {
      if (e.key === 'Enter') onCommit?.();
      return;
    }
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActiveIdx(i => Math.min(i + 1, suggestions.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActiveIdx(i => Math.max(i - 1, -1));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (activeIdx >= 0) pick(suggestions[activeIdx]);
      else onCommit?.();
    } else if (e.key === 'Escape') {
      setOpen(false);
      setActiveIdx(-1);
    }
  };

  // Close on blur, but delay so mousedown on a suggestion fires first
  const handleBlur = () => {
    blurTimer.current = setTimeout(() => setOpen(false), 150);
  };
  const handleFocus = () => {
    if (blurTimer.current) clearTimeout(blurTimer.current);
    if (value.length >= 2) setOpen(true);
  };

  return (
    <div className="tc-system-wrap">
      <input
        type="text"
        className="tc-input tc-input-text tc-input-upper"
        value={value}
        placeholder={placeholder}
        onChange={handleChange}
        onKeyDown={handleKey}
        onBlur={handleBlur}
        onFocus={handleFocus}
        autoComplete="off"
        spellCheck={false}
      />
      {open && suggestions.length > 0 && (
        <div className="tc-suggestions">
          {suggestions.map((s, i) => (
            <div
              key={s}
              className={`tc-suggestion${i === activeIdx ? ' tc-suggestion-active' : ''}`}
              onMouseDown={() => pick(s)}
            >
              {s.toUpperCase()}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

interface Props {
  currentSystem: string;
  apiBaseUrl: string;
  walletAddress: string | null;
  initialShipProfile: Record<string, unknown> | null;
  onResult: (routeData: unknown, summary: string) => void;
  onDismiss: () => void;
}

const SHIP_NAMES = Object.keys(SHIPS);
const DEFAULT_SHIP = SHIP_NAMES.includes('Reflex') ? 'Reflex' : SHIP_NAMES[0];

export function TripCalculatorForm({ currentSystem, apiBaseUrl, walletAddress, initialShipProfile, onResult, onDismiss }: Props) {
  const savedShip  = initialShipProfile?.ship_type as string;
  const initShip   = SHIPS[savedShip] ? savedShip : DEFAULT_SHIP;
  const initFuel   = initialShipProfile?.fuel_type as string || '';
  const initTank   = (initialShipProfile?.fuel_quantity as number) ?? SHIPS[initShip].fuel_capacity;
  const initAdapt  = (initialShipProfile?.adaptive_level as number) ?? 0;
  const initCargo  = (initialShipProfile?.extra_cargo_kg as number) ?? 0;

  const [shipType, setShipType]     = useState(initShip);
  const [fuelType, setFuelType]     = useState(initFuel);
  const [tankFuel, setTankFuel]     = useState(initTank);
  const [cargoFuel, setCargoFuel]   = useState(0);
  const [cargoKg, setCargoKg]       = useState(initCargo);
  const [adaptive, setAdaptive]     = useState(initAdapt);
  const [cryo, setCryo]             = useState(false);
  const [from, setFrom]             = useState(currentSystem);
  const [to, setTo]                 = useState('');
  const [isLoading, setIsLoading]   = useState(false);
  const [error, setError]           = useState('');

  const ship = SHIPS[shipType];
  const validFuels = fuelsForShip(ship);

  // Skip the first render so initial state above is not overwritten by this effect.
  const isFirstRender = useRef(true);

  // When ship changes: snap fuel to a valid type, reset tank to full capacity
  useEffect(() => {
    if (isFirstRender.current) { isFirstRender.current = false; return; }
    const newShip = SHIPS[shipType];
    setFuelType(prev => fuelsForShip(newShip).includes(prev) ? prev : fuelsForShip(newShip)[0]);
    setTankFuel(newShip.fuel_capacity);
  }, [shipType]); // eslint-disable-line react-hooks/exhaustive-deps

  const saveProfile = useCallback(() => {
    if (!walletAddress) return;
    fetch(`${apiBaseUrl}/session/${walletAddress}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json', 'X-Wallet-Address': walletAddress },
      body: JSON.stringify({ ship_profile: { ship_type: shipType, fuel_type: fuelType, fuel_quantity: tankFuel, adaptive_level: adaptive, extra_cargo_kg: cargoKg } }),
    }).catch(() => {});
  }, [apiBaseUrl, walletAddress, shipType, fuelType, tankFuel, adaptive, cargoKg]);

  const handleSubmit = async () => {
    if (!from.trim()) { setError('FROM is required.'); return; }
    if (!to.trim())   { setError('TO is required.');   return; }
    setError('');
    setIsLoading(true);
    try {
      const res = await fetch(`${apiBaseUrl}/route`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          origin:         from.trim(),
          destination:    to.trim(),
          hull_mass:      ship.mass,
          specific_heat:  ship.specific_heat,
          fuel_type:      fuelType,
          fuel_quantity:  tankFuel,
          cargo_fuel:     cargoFuel,
          extra_cargo_kg: cargoKg,
          adaptive_level: adaptive,
        }),
      });
      if (res.status === 404 || res.status === 400) {
        const body = await res.json();
        setError(body.detail || `No route to "${to}".`);
        setIsLoading(false);
        return;
      }
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json() as Record<string, unknown>;
      const jumps = data.jumps as number ?? '?';
      const summary = `[tripcalc]: ${shipType} / ${fuelType} — ${jumps} jump${jumps !== 1 ? 's' : ''} to ${to.trim()}`;
      saveProfile();
      onResult(data, summary);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setIsLoading(false);
    }
  };

  const fuelLabel = (f: string) => {
    const qf = qualityFactor(f);
    const pct = Math.round((qf - 1) * 100);
    return pct === 0 ? f : `${f}  (${pct > 0 ? '+' : ''}${pct}% range)`;
  };

  return (
    <div className="trip-calc">
      <div className="tc-header">TRIP CALCULATOR</div>

      <div className="tc-field">
        <span className="tc-label">SHIP</span>
        <CustomSelect
          value={shipType}
          onChange={setShipType}
          options={SHIP_NAMES.map(s => ({ value: s, label: `${s} — ${SHIPS[s].class_name}` }))}
        />
        <span className="tc-hint">tank max: {ship.fuel_capacity.toLocaleString()}</span>
      </div>

      <div className="tc-field">
        <span className="tc-label">FUEL</span>
        <CustomSelect
          value={fuelType}
          onChange={setFuelType}
          options={validFuels.map(f => ({ value: f, label: fuelLabel(f) }))}
        />
        <span className="tc-hint">{FUELS[fuelType] ? `q: ${FUELS[fuelType].quality}` : ''}</span>
      </div>

      <div className="tc-field">
        <span className="tc-label">TANK FUEL</span>
        <input
          type="number"
          className="tc-input tc-input-num"
          value={tankFuel}
          min={0}
          max={ship.fuel_capacity}
          onChange={e => setTankFuel(Math.min(Math.max(0, Number(e.target.value)), ship.fuel_capacity))}
        />
        <span className="tc-hint">/ {ship.fuel_capacity.toLocaleString()}</span>
      </div>

      <div className="tc-field">
        <span className="tc-label">CARGO FUEL</span>
        <input
          type="number"
          className="tc-input tc-input-num"
          value={cargoFuel}
          min={0}
          onChange={e => setCargoFuel(Math.max(0, Number(e.target.value)))}
        />
        <span className="tc-hint">units  (adds mass)</span>
      </div>

      <div className="tc-field">
        <span className="tc-label">CARGO</span>
        <input
          type="number"
          className="tc-input tc-input-num"
          value={cargoKg}
          min={0}
          onChange={e => setCargoKg(Math.max(0, Number(e.target.value)))}
        />
        <span className="tc-hint">kg  (non-fuel mass)</span>
      </div>

      <div className="tc-field">
        <span className="tc-label">ADAPTIVE</span>
        <div className="tc-stepper">
          <button className="tc-step-btn" onClick={() => setAdaptive(a => Math.max(0, a - 1))}>−</button>
          <span className="tc-step-val">{adaptive}</span>
          <button className="tc-step-btn" onClick={() => setAdaptive(a => Math.min(5, a + 1))}>+</button>
        </div>
        <span className="tc-hint">heat management level</span>
      </div>

      <div className="tc-field">
        <span className="tc-label">CRYO-INJECTOR</span>
        <span
          className="tc-checkbox-box"
          onClick={() => setCryo(c => !c)}
          role="checkbox"
          aria-checked={cryo}
          tabIndex={0}
          onKeyDown={e => e.key === ' ' && setCryo(c => !c)}
        >
          {cryo ? '[X]' : '[ ]'}
        </span>
        <span className="tc-hint tc-stub">stub — planned feature</span>
      </div>

      <div className="tc-divider" />

      <div className="tc-field">
        <span className="tc-label">FROM</span>
        <input
          type="text"
          className="tc-input tc-input-text tc-input-upper"
          value={from}
          onChange={e => setFrom(e.target.value)}
          placeholder="system name"
          autoComplete="off"
          spellCheck={false}
        />
      </div>

      <div className="tc-field">
        <span className="tc-label">TO</span>
        <SystemField
          value={to}
          onChange={setTo}
          onCommit={handleSubmit}
          placeholder="system name"
          apiBaseUrl={apiBaseUrl}
        />
      </div>

      {error && <div className="tc-error">{error}</div>}

      <div className="tc-actions">
        <button className="tc-btn tc-btn-primary" onClick={handleSubmit} disabled={isLoading}>
          {isLoading ? 'PLOTTING...' : 'CALCULATE'}
        </button>
        <button className="tc-btn tc-btn-cancel" onClick={onDismiss} disabled={isLoading}>
          CANCEL
        </button>
      </div>
    </div>
  );
}
