interface SimulationOverridesPanelProps {
  tags: string[]
  limits: Record<string, { lower: number; upper: number }>
  overrides: Record<string, string>
  onChange: (tag: string, raw: string) => void
  onReset: () => void
}

function validate(raw: string, lower: number, upper: number): string | null {
  if (!raw.trim()) return null
  const value = Number(raw)
  if (Number.isNaN(value)) return 'Numeric input required'
  if (value < lower || value > upper) return `Value must be between ${lower.toFixed(3)} and ${upper.toFixed(3)}`
  return null
}

// This is where Streamlit's st.sidebar "Simulation Overrides" panel lives in
// the React app — placed directly above the Compute button on the Dashboard
// page itself, since the app's actual Sidebar is reserved for top-level nav.
export function SimulationOverridesPanel({ tags, limits, overrides, onChange, onReset }: SimulationOverridesPanelProps) {
  if (tags.length === 0) {
    return (
      <div className="card" style={{ padding: '1.5rem' }}>
        <h3 style={{ marginTop: 0 }}>🔧 Simulation Overrides</h3>
        <p className="caption">Pick one or more tags in Tag Source above to override their value for this run.</p>
      </div>
    )
  }

  const activeCount = tags.filter((tag) => (overrides[tag] ?? '').trim() !== '').length

  return (
    <div className="card" style={{ padding: '1.5rem' }}>
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.5rem' }}>
        <h3 style={{ marginTop: 0 }}>
          🔧 Simulation Overrides
          {activeCount > 0 && (
            <span className="caption" style={{ fontWeight: 500, marginLeft: '0.5rem' }}>
              ({activeCount} of {tags.length} active)
            </span>
          )}
        </h3>
        {activeCount > 0 && (
          <button className="chip" onClick={onReset}>
            ↺ Reset All
          </button>
        )}
      </div>
      <p className="caption">Enter a target value to override — leave blank to keep the actual (baseline) value.</p>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', marginTop: '1rem' }}>
        {tags.map((tag) => {
          const lim = limits[tag] ?? { lower: 0, upper: 1e6 }
          const raw = overrides[tag] ?? ''
          const error = validate(raw, lim.lower, lim.upper)
          return (
            <div key={tag}>
              <div style={{ fontWeight: 600 }}>{tag}</div>
              <div className="caption">Boundary range: {lim.lower.toFixed(3)} → {lim.upper.toFixed(3)}</div>
              <input
                type="number"
                value={raw}
                placeholder="blank = keep actual"
                onChange={(e) => onChange(tag, e.target.value)}
                style={{ width: 220, marginTop: '0.25rem' }}
              />
              {error && <div className="caption" style={{ color: 'var(--error-text)' }}>{error}</div>}
            </div>
          )
        })}
      </div>
    </div>
  )
}
