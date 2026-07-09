import { useMutation, useQuery } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { downloadBlob, exportScenarioCsv, runValidationFilter } from '../../api/whatIf'
import { DataTable } from '../../components/DataTable'
import type { WhatIfScenarioRow } from '../../api/types'

interface ValidationFiltersPanelProps {
  timestamp: string
  scenarioRows: WhatIfScenarioRow[]
}

// This is where Streamlit's st.sidebar "Validation Filters" panel lives in
// the React app — placed directly above the historical validation table it
// feeds, since the app's actual Sidebar is reserved for top-level nav.
export function ValidationFiltersPanel({ timestamp, scenarioRows }: ValidationFiltersPanelProps) {
  const [range, setRange] = useState<Record<string, { min: number; max: number }>>({})

  const allQuery = useQuery({ queryKey: ['whatif-validation-all'], queryFn: () => runValidationFilter({}) })
  const filterMutation = useMutation({ mutationFn: runValidationFilter })

  useEffect(() => {
    if (allQuery.data && Object.keys(range).length === 0 && allQuery.data.rows.length > 0) {
      const tags = Object.keys(allQuery.data.rows[0]).filter((k) => k !== 'Timestamp')
      const init: Record<string, { min: number; max: number }> = {}
      for (const tag of tags) {
        const values = allQuery.data.rows
          .map((r) => Number(r[tag]))
          .filter((v) => !Number.isNaN(v))
        if (values.length) init[tag] = { min: Math.min(...values), max: Math.max(...values) }
      }
      setRange(init)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [allQuery.data])

  const results = filterMutation.data ?? allQuery.data
  const tags = Object.keys(range)

  function apply() {
    const body = Object.fromEntries(Object.entries(range).map(([tag, r]) => [tag, { min: r.min, max: r.max }]))
    filterMutation.mutate(body)
  }

  async function exportCsv() {
    if (!results) return
    const blob = await exportScenarioCsv(timestamp, scenarioRows, results.rows)
    downloadBlob(blob, 'filtered_validation_data.csv')
  }

  return (
    <div className="card" style={{ padding: '1.5rem' }}>
      <h3 style={{ marginTop: 0 }}>🔍 Validation Filters</h3>
      {allQuery.isLoading ? (
        <p className="caption">Loading historical validation data…</p>
      ) : tags.length === 0 ? (
        <p className="caption">Validation tags are missing from the historian dataset.</p>
      ) : (
        <>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            {tags.map((tag) => (
              <div key={tag} style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                <div style={{ minWidth: 220, fontWeight: 600 }}>{tag}</div>
                <label className="caption">
                  Min
                  <input
                    type="number"
                    value={range[tag].min}
                    onChange={(e) => setRange({ ...range, [tag]: { ...range[tag], min: Number(e.target.value) } })}
                    style={{ width: 110, marginLeft: '0.4rem' }}
                  />
                </label>
                <label className="caption">
                  Max
                  <input
                    type="number"
                    value={range[tag].max}
                    onChange={(e) => setRange({ ...range, [tag]: { ...range[tag], max: Number(e.target.value) } })}
                    style={{ width: 110, marginLeft: '0.4rem' }}
                  />
                </label>
              </div>
            ))}
          </div>
          <button style={{ marginTop: '1rem' }} onClick={apply} disabled={filterMutation.isPending}>
            {filterMutation.isPending ? 'Filtering…' : 'Apply Filters'}
          </button>
        </>
      )}

      {results && (
        <div style={{ marginTop: '1.5rem' }}>
          <h4>🔍 Correlated Historical Validation Sets</h4>
          <p className="caption">{results.match_count} matching historical snapshot(s)</p>
          <DataTable
            columns={tags.map((tag) => ({ header: tag, render: (r: Record<string, unknown>) => String(r[tag] ?? '') }))}
            rows={results.rows}
            keyFn={(r) => String(r.Timestamp)}
            maxVisibleRows={8}
          />
          <button className="chip" style={{ marginTop: '1rem' }} onClick={exportCsv}>
            📥 Export Unified Comparison &amp; Historical Validation Data (.CSV)
          </button>
        </div>
      )}
    </div>
  )
}
