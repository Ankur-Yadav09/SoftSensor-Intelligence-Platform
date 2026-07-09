import { useState } from 'react'
import type { DetectedCounts } from '../../api/types'

interface PlantConfigWizardProps {
  detectedCounts: DetectedCounts | undefined
  onGenerate: (counts: { cgc_stages: number; prc_stages: number; erc_stages: number; furnaces: number }) => void
  generating: boolean
  onReset: () => void
}

function CountInput({
  label, max, value, onChange,
}: { label: string; max: number; value: number; onChange: (v: number) => void }) {
  if (max === 0) {
    return (
      <label>
        <div className="caption">{label}</div>
        <p className="caption">⚠️ No numbered tags detected for this question.</p>
      </label>
    )
  }
  return (
    <label>
      <div className="caption">{label}</div>
      <input
        type="number"
        min={0}
        max={max}
        value={value}
        onChange={(e) => onChange(Math.max(0, Math.min(max, Number(e.target.value))))}
        style={{ width: 100 }}
      />
      <span className="caption" style={{ marginLeft: '0.5rem' }}>detected: up to {max}</span>
    </label>
  )
}

export function PlantConfigWizard({ detectedCounts, onGenerate, generating, onReset }: PlantConfigWizardProps) {
  const [cgc, setCgc] = useState(detectedCounts?.cgc_max ?? 0)
  const [prc, setPrc] = useState(detectedCounts?.prc_max ?? 0)
  const [erc, setErc] = useState(detectedCounts?.erc_max ?? 0)
  const [furnaces, setFurnaces] = useState(detectedCounts?.furnace_max ?? 0)

  return (
    <div className="card" style={{ padding: '1.5rem' }}>
      <h3 style={{ marginTop: 0 }}>🧙 Plant Configuration Wizard</h3>
      <p className="caption">
        Answer the plant line-up questions — matching tags are automatically clubbed per section (CGC / PRC / ERC /
        Furnace).
      </p>

      <div style={{ display: 'flex', gap: '2rem', flexWrap: 'wrap', marginTop: '1rem' }}>
        <CountInput label="🌀 How many CGC compressor stages are there?" max={detectedCounts?.cgc_max ?? 0} value={cgc} onChange={setCgc} />
        <CountInput label="❄️ How many PRC compressor stages are there?" max={detectedCounts?.prc_max ?? 0} value={prc} onChange={setPrc} />
        <CountInput label="🧊 How many ERC compressor stages are there?" max={detectedCounts?.erc_max ?? 0} value={erc} onChange={setErc} />
        <CountInput label="🔥 How many furnaces are there?" max={detectedCounts?.furnace_max ?? 0} value={furnaces} onChange={setFurnaces} />
      </div>

      <div style={{ display: 'flex', gap: '0.75rem', marginTop: '1.5rem' }}>
        <button
          disabled={generating}
          onClick={() => onGenerate({ cgc_stages: cgc, prc_stages: prc, erc_stages: erc, furnaces })}
        >
          {generating ? 'Generating…' : '⚡ Generate PI Mapping for this line-up'}
        </button>
        <button className="chip" onClick={onReset}>♻️ Reset mapping</button>
      </div>
    </div>
  )
}
