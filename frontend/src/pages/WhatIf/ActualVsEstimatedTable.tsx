import { DataTable } from '../../components/DataTable'
import { downloadBlob } from '../../api/whatIf'
import type { WhatIfScenarioRow } from '../../api/types'

function fmt(val: unknown): string {
  if (typeof val === 'number') {
    const s = val.toFixed(2)
    return s.replace(/\.?0+$/, '') || '0'
  }
  return val == null ? '' : String(val)
}

function toCsv(timestamp: string, rows: WhatIfScenarioRow[]): string {
  const header = ['Selected Timestamp', 'Parameter', 'Actual', 'Estimated', 'Change']
  const lines = [header.join(',')]
  for (const r of rows) {
    lines.push([timestamp, r.parameter, fmt(r.actual), fmt(r.estimated), r.change != null ? fmt(r.change) : ''].join(','))
  }
  return lines.join('\n')
}

interface ActualVsEstimatedTableProps {
  timestamp: string
  rows: WhatIfScenarioRow[]
}

export function ActualVsEstimatedTable({ timestamp, rows }: ActualVsEstimatedTableProps) {
  function exportCsv() {
    const csv = toCsv(timestamp, rows)
    downloadBlob(new Blob([csv], { type: 'text/csv' }), 'WhatIf_Result.csv')
  }

  return (
    <div>
      <h3>📈 Actual vs Estimated Scenario Output</h3>
      <DataTable
        columns={[
          { header: 'Parameter', render: (r) => r.parameter },
          { header: 'Actual', render: (r) => fmt(r.actual) },
          { header: 'Estimated', render: (r) => fmt(r.estimated) },
          {
            header: 'Change',
            render: (r) =>
              r.change == null ? (
                ''
              ) : (
                <span
                  style={{
                    color: r.change > 0 ? 'var(--success-text)' : r.change < 0 ? 'var(--error-text)' : 'var(--text-caption)',
                    fontWeight: 600,
                  }}
                >
                  {fmt(r.change)}
                </span>
              ),
          },
        ]}
        rows={rows}
        keyFn={(r) => r.parameter}
        maxVisibleRows={12}
      />
      <button className="chip" style={{ marginTop: '1rem' }} onClick={exportCsv}>
        📥 Export Baseline vs Simulation Matrix (.CSV)
      </button>
    </div>
  )
}
