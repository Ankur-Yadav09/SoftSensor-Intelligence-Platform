import { KPI_TAGS } from './whatIfConstants'
import type { WhatIfKpi } from '../../api/types'

function fmtNum(val: number, forceSign = false): string {
  const sign = forceSign && val > 0 ? '+' : ''
  return Math.abs(val) >= 1000 ? `${sign}${val.toFixed(0)}` : `${sign}${val.toFixed(1)}`
}

function WhatIfKpiCard({ kpi }: { kpi: WhatIfKpi }) {
  let border = 'var(--border)'
  let color = 'var(--text-caption)'
  if (kpi.change > 0) {
    border = 'var(--success-text)'
    color = 'var(--success-text)'
  } else if (kpi.change < 0) {
    border = 'var(--error-text)'
    color = 'var(--error-text)'
  }
  return (
    <div
      className="status-card"
      style={{ flex: 1, minWidth: 200, borderLeft: `4px solid ${border}` }}
    >
      <div className="caption" title={kpi.tag} style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
        🏷️ {kpi.tag.replace(/_/g, ' ')}
      </div>
      <div className="metric-value">{fmtNum(kpi.estimated)}</div>
      <div className="caption" style={{ color, fontWeight: 600 }}>
        {fmtNum(kpi.change, true)} vs Act ({fmtNum(kpi.actual)})
      </div>
    </div>
  )
}

export function KpiCardsRow({ kpis }: { kpis: WhatIfKpi[] }) {
  const active = KPI_TAGS.map((tag) => kpis.find((k) => k.tag === tag)).filter((k): k is WhatIfKpi => !!k)
  if (active.length === 0) return null

  const chunks: WhatIfKpi[][] = []
  for (let i = 0; i < active.length; i += 4) chunks.push(active.slice(i, i + 4))

  return (
    <div>
      <h3>📊 Key Performance Indicators</h3>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
        {chunks.map((chunk, i) => (
          <div key={i} style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
            {chunk.map((kpi) => (
              <WhatIfKpiCard key={kpi.tag} kpi={kpi} />
            ))}
          </div>
        ))}
      </div>
    </div>
  )
}
