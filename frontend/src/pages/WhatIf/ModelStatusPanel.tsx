import { Callout } from '../../components/Callout'
import { StatusCard } from '../../components/StatusCard'
import type { WhatIfModelStatus } from '../../api/types'

interface ModelStatusPanelProps {
  status: WhatIfModelStatus | undefined
  isLoading: boolean
}

export function ModelStatusPanel({ status, isLoading }: ModelStatusPanelProps) {
  return (
    <div className="card" style={{ padding: '1.5rem' }}>
      <h3 style={{ marginTop: 0 }}>🧠 Step B — Trained Models</h3>
      {isLoading || !status ? (
        <p className="caption">Checking Results/Model for trained artifacts…</p>
      ) : (
        <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
          <StatusCard
            label="Model artifacts found"
            value={`${status.pkl_count} files`}
            tone={status.all_present ? 'success' : 'warning'}
          />
          <StatusCard
            label="Tags ready"
            value={`${status.tags_ok.length} / ${status.tags_ok.length + status.tags_missing.length}`}
            sublabel={status.tags_missing.length ? `Missing: ${status.tags_missing.join(', ')}` : 'All tags ready'}
            tone={status.all_present ? 'success' : 'warning'}
          />
        </div>
      )}
      <div style={{ marginTop: '1rem' }}>
        <Callout variant="info">
          Model training is managed outside this UI in Phase 1 — the 48 Kalman model/scaler files under
          Results/Model are trained by the standalone process and simply detected here.
        </Callout>
      </div>
    </div>
  )
}
