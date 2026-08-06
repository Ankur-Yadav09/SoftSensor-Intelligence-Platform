import { useMutation, useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { downloadBlob, exportScenarioCsv, runValidationFilter } from '../../api/whatIf'
import { DataTable } from '../../components/DataTable'
import type { WhatIfScenarioRow } from '../../api/types'

interface ValidationFiltersPanelProps {
  timestamp: string
  scenarioRows: WhatIfScenarioRow[]
  targetSection?: string | null
}

interface FilterEntry {
  tag: string
  min: number
  max: number
}

function round3(n: number): number {
  return Math.round(n * 1000) / 1000
}

// Same "round numbers, leave everything else alone" convention as
// ActualVsEstimatedTable.tsx's fmt() — historian values often carry many
// more decimals than are meaningful to read.
function fmt(value: unknown): string {
  if (typeof value === 'number') return value.toFixed(3)
  return value == null ? '' : String(value)
}

// This is where Streamlit's st.sidebar "Validation Filters" panel lives in
// the React app — placed directly above the historical validation table it
// feeds, since the app's actual Sidebar is reserved for top-level nav.
export function ValidationFiltersPanel({ timestamp, scenarioRows, targetSection }: ValidationFiltersPanelProps) {
  // "+ Add Filter" appends a blank entry; picking a tag for it fills in that
  // tag's historical min/max as a starting range — same "+ Add X" row
  // pattern as ConstraintsEditor/UserInputsEditor, rather than a checkbox
  // multi-select of every tag at once.
  const [filters, setFilters] = useState<FilterEntry[]>([])

  const allQuery = useQuery({
    queryKey: ['whatif-validation-all', targetSection],
    queryFn: () => runValidationFilter({}, targetSection),
  })
  const filterMutation = useMutation({
    mutationFn: (body: Record<string, { min: number; max: number }>) => runValidationFilter(body, targetSection),
  })

  const allTags = allQuery.data && allQuery.data.rows.length > 0
    ? Object.keys(allQuery.data.rows[0]).filter((k) => k !== 'Timestamp')
    : []

  function tagBounds(tag: string): { min: number; max: number } {
    const values = (allQuery.data?.rows ?? [])
      .map((r) => Number(r[tag]))
      .filter((v) => !Number.isNaN(v))
    return values.length
      ? { min: round3(Math.min(...values)), max: round3(Math.max(...values)) }
      : { min: 0, max: 0 }
  }

  function addFilter() {
    setFilters([...filters, { tag: '', min: 0, max: 0 }])
  }

  function selectTag(index: number, tag: string) {
    const next = [...filters]
    next[index] = tag ? { tag, ...tagBounds(tag) } : { tag: '', min: 0, max: 0 }
    setFilters(next)
  }

  function updateBound(index: number, field: 'min' | 'max', value: number) {
    const next = [...filters]
    next[index] = { ...next[index], [field]: value }
    setFilters(next)
  }

  function removeFilter(index: number) {
    setFilters(filters.filter((_, i) => i !== index))
  }

  const activeFilters = filters.filter((f) => f.tag)
  const results = filterMutation.data ?? allQuery.data

  function apply() {
    const body = Object.fromEntries(activeFilters.map((f) => [f.tag, { min: f.min, max: f.max }]))
    filterMutation.mutate(body)
  }

  async function exportCsv() {
    if (!results) return
    const blob = await exportScenarioCsv(timestamp, scenarioRows, results.rows)
    downloadBlob(blob, 'filtered_validation_data.csv')
  }

  return (
    <details className="card" style={{ padding: '1.5rem' }}>
      <summary style={{ cursor: 'pointer', fontWeight: 700, fontSize: '1.05rem' }}>
        🔍 Validation Filters — compare this scenario against similar historical snapshots (optional)
      </summary>
      <div style={{ marginTop: '1rem' }}>
        {allQuery.isLoading ? (
          <p className="caption">Loading historical validation data…</p>
        ) : allTags.length === 0 ? (
          <p className="caption">Validation tags are missing from the historian dataset.</p>
        ) : (
          <>
            {filters.length > 0 && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', marginBottom: '1rem' }}>
                {filters.map((f, i) => (
                  <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
                    <select
                      value={f.tag}
                      onChange={(e) => selectTag(i, e.target.value)}
                      style={{ minWidth: 240 }}
                    >
                      <option value="">Select a tag…</option>
                      {allTags.map((t) => (
                        <option key={t} value={t}>
                          {t}
                        </option>
                      ))}
                    </select>
                    {f.tag && (
                      <>
                        <label className="caption">
                          Min
                          <input
                            type="number"
                            value={f.min}
                            onChange={(e) => updateBound(i, 'min', Number(e.target.value))}
                            style={{ width: 110, marginLeft: '0.4rem' }}
                          />
                        </label>
                        <label className="caption">
                          Max
                          <input
                            type="number"
                            value={f.max}
                            onChange={(e) => updateBound(i, 'max', Number(e.target.value))}
                            style={{ width: 110, marginLeft: '0.4rem' }}
                          />
                        </label>
                      </>
                    )}
                    <button className="chip" onClick={() => removeFilter(i)}>
                      Remove
                    </button>
                  </div>
                ))}
              </div>
            )}
            <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
              <button className="chip" onClick={addFilter}>
                + Add Filter
              </button>
              {activeFilters.length > 0 && (
                <button onClick={apply} disabled={filterMutation.isPending}>
                  {filterMutation.isPending ? 'Filtering…' : 'Apply Filters'}
                </button>
              )}
            </div>
          </>
        )}

        {results && (
          <div style={{ marginTop: '1.5rem' }}>
            <h4>🔍 Correlated Historical Validation Sets</h4>
            <p className="caption">{results.match_count} matching historical snapshot(s)</p>
            <DataTable
              columns={allTags.map((tag) => ({
                header: tag,
                render: (r: Record<string, unknown>) => fmt(r[tag]),
              }))}
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
    </details>
  )
}
