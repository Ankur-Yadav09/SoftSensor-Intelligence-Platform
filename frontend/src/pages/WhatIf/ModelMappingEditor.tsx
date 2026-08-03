import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { commitModelMapping, getModelMapping } from '../../api/whatIf'
import { Callout } from '../../components/Callout'
import { inSectionScope, modelInputOptionsForSection, optionsWithCurrentValue } from './caseSetupHelpers'
import { useTouchedRowIndices } from './useTouchedRowIndices'
import { SECTION_OPTIONS } from './whatIfConstants'
import type { ModelDetailsRow, MvDvCvTagRow, PiMappingRow } from '../../api/types'

const INPUT_COLS = Array.from({ length: 8 }, (_, i) => `Input parameter_${i + 1}`)
const STICKY_COL_WIDTH = 200
// Matches src/whatif/config_io.py::_is_data_model() exactly: blank/"Data
// model" is Kalman/Soft-Sensor-driven (the default); anything else — here,
// "First principle" — is simulation-owned. A First-Principle parameter's
// value comes from the plant physics plugin (src/whatif/plants/
// yanpet_olf1_formulas.py, matching Scripts/yanpet_olf1_formulas.py's HOOKS/
// SIMULATION contract) instead of a trained model — the engine skips Kalman/
// Soft-Sensor prediction for it entirely (src/whatif/engine.py::whatif_analysis).
const MODEL_TYPE_OPTIONS = ['', 'Data model', 'First principle']

// The highest input-column index actually filled in across every row (at
// least 1) — so a workbook that already has, say, 5 input tags saved never
// has those columns hidden, even though new/blank rows start collapsed to
// just "In 1".
function maxFilledInputIndex(rows: ModelDetailsRow[]): number {
  let max = 1
  for (const row of rows) {
    for (let i = INPUT_COLS.length; i >= 1; i--) {
      if ((row[INPUT_COLS[i - 1]] ?? '').toString().trim()) {
        max = Math.max(max, i)
        break
      }
    }
  }
  return max
}

interface ModelMappingEditorProps {
  /** Restricts which rows are shown/editable to those in-scope. Omit for
   * the unscoped, full-sheet view used outside the wizard. */
  allowed?: Set<string>
  /** Raw PI tag dictionary and MV/DV/CV tag list — used to compute each
   * row's own Input dropdown options. MV/DV/CV tags whose Section matches
   * the row's chosen Section (or is upstream of it) are bumped to the top
   * as prioritized choices; every other tag still follows — nothing is
   * ever hidden from the dropdown, only reordered. Falls back to the full
   * historian tag list when omitted entirely. */
  piRows?: PiMappingRow[]
  mvdvcvRows?: MvDvCvTagRow[]
  sectionOptions?: string[]
  /** The plant's process-flow order (e.g. Furnace/Quench/CGC/PRC/ERC/Cold),
   * used to resolve "upstream of this row's Section" for prioritizing its
   * Input dropdown. Without it, only an exact Section match is prioritized. */
  sectionOrder?: string[]
}

// Case Setup wizard Step 7: maps each predicted parameter to its Section and
// its ordered input feature tags. Rows outside the active scope stay in the
// dataset untouched, just hidden from view (see `allowed`). Each row's Input
// dropdowns prioritize tags matching its own Section (see modelInputOptionsForSection) —
// choosing a Section moves matching MV/DV/CV tags to the top; every tag is
// still selectable either way, nothing is hidden.
export function ModelMappingEditor({ allowed, piRows, mvdvcvRows, sectionOptions, sectionOrder }: ModelMappingEditorProps) {
  const queryClient = useQueryClient()
  const query = useQuery({ queryKey: ['whatif-model-mapping'], queryFn: getModelMapping })
  const [rows, setRows] = useState<ModelDetailsRow[]>([])
  const { touched, markTouched, onRowRemoved } = useTouchedRowIndices()
  // Starts at just "In 1" — most predicted parameters don't need all 8 input
  // slots, so showing them empty by default is just clutter. "+ Add Input"
  // reveals one more column at a time, up to 8.
  const [visibleInputCount, setVisibleInputCount] = useState(1)

  useEffect(() => {
    if (query.data) {
      setRows(query.data.rows)
      setVisibleInputCount((prev) => Math.max(prev, maxFilledInputIndex(query.data.rows)))
    }
  }, [query.data])

  const commitMutation = useMutation({
    mutationFn: commitModelMapping,
    onSuccess: (result) => {
      setRows(result)
      queryClient.setQueryData(['whatif-model-mapping'], { rows: result, historian_tags: query.data?.historian_tags ?? [] })
    },
  })

  if (query.isLoading) return <p className="caption">Loading model mapping…</p>

  const fallbackOptions = query.data?.historian_tags ?? []
  function inputOptionsForRow(row: ModelDetailsRow): string[] {
    if (!piRows) return fallbackOptions
    return modelInputOptionsForSection(piRows, mvdvcvRows ?? [], row.Section, sectionOrder ?? [])
  }
  const sectionChoices = sectionOptions ?? SECTION_OPTIONS
  const visibleInputCols = INPUT_COLS.slice(0, visibleInputCount)

  const visibleIndices = rows
    .map((_, i) => i)
    .filter(
      (i) => !allowed || touched.has(i) || inSectionScope(rows[i].Section, allowed, rows[i]['Predicted parameter']),
    )
  const hiddenCount = rows.length - visibleIndices.length

  function updateCell(index: number, col: string, value: string) {
    const next = [...rows]
    next[index] = { ...next[index], [col]: value }
    setRows(next)
    markTouched(index)
  }

  function addRow() {
    setRows([...rows, { 'Predicted parameter': '', Section: '' }])
  }

  function removeRow(index: number) {
    setRows(rows.filter((_, i) => i !== index))
    onRowRemoved(index)
  }

  return (
    <div>
      <p className="caption">
        Maps each predicted parameter to its Section and the ordered input feature tags its Kalman model consumes.
        "Predicted parameter" stays pinned on the left; input dropdowns list MV/DV/CV tags first, then the remaining
        scoped PI tags.
      </p>
      {rows.length === 0 && (
        <Callout variant="info">No predicted parameters yet — click "+ Add Parameter" below to add one.</Callout>
      )}
      <div className="data-table-scroll" style={{ overflowX: 'auto', maxHeight: 420, overflowY: 'auto' }}>
        <table className="table-compact" style={{ tableLayout: 'fixed' }}>
          <thead>
            <tr>
              <th className="sticky-col" style={{ minWidth: STICKY_COL_WIDTH, width: STICKY_COL_WIDTH }}>
                Predicted parameter
              </th>
              <th style={{ width: 130 }}>Section</th>
              <th style={{ width: 150 }}>Model Type</th>
              {visibleInputCols.map((c, i) => (
                <th key={c} title={c} style={{ width: 180 }}>
                  In {i + 1}
                </th>
              ))}
              <th style={{ width: 90 }} />
            </tr>
          </thead>
          <tbody>
            {visibleIndices.map((i) => {
              const rowInputOptions = inputOptionsForRow(rows[i])
              return (
              <tr key={i}>
                <td className="sticky-col" style={{ minWidth: STICKY_COL_WIDTH, verticalAlign: 'middle' }}>
                  <input
                    type="text"
                    value={rows[i]['Predicted parameter']}
                    onChange={(e) => updateCell(i, 'Predicted parameter', e.target.value)}
                    style={{ width: '100%', fontWeight: 600, boxSizing: 'border-box' }}
                  />
                </td>
                <td style={{ verticalAlign: 'middle' }}>
                  <select
                    value={rows[i].Section ?? ''}
                    onChange={(e) => updateCell(i, 'Section', e.target.value)}
                    style={{ width: '100%', boxSizing: 'border-box' }}
                  >
                    {sectionChoices.map((s) => (
                      <option key={s} value={s}>
                        {s || '—'}
                      </option>
                    ))}
                  </select>
                </td>
                <td style={{ verticalAlign: 'middle' }}>
                  <select
                    value={rows[i]['model type'] ?? ''}
                    onChange={(e) => updateCell(i, 'model type', e.target.value)}
                    style={{ width: '100%', boxSizing: 'border-box' }}
                  >
                    {MODEL_TYPE_OPTIONS.map((t) => (
                      <option key={t} value={t}>
                        {t || '—'}
                      </option>
                    ))}
                  </select>
                </td>
                {visibleInputCols.map((c) => (
                  <td key={c} style={{ verticalAlign: 'middle' }}>
                    <select
                      value={rows[i][c] ?? ''}
                      onChange={(e) => updateCell(i, c, e.target.value)}
                      title={rows[i][c] || undefined}
                      style={{ width: '100%', boxSizing: 'border-box' }}
                    >
                      <option value="">—</option>
                      {optionsWithCurrentValue(rowInputOptions, rows[i][c]).map((t) => (
                        <option key={t} value={t}>
                          {t}
                        </option>
                      ))}
                    </select>
                  </td>
                ))}
                <td style={{ verticalAlign: 'middle', textAlign: 'center' }}>
                  <button className="chip" onClick={() => removeRow(i)}>
                    Remove
                  </button>
                </td>
              </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      {hiddenCount > 0 && (
        <p className="caption" style={{ marginTop: '0.5rem' }}>
          Active scope only — {hiddenCount} downstream model(s) hidden here.
        </p>
      )}
      <div style={{ display: 'flex', gap: '0.75rem', marginTop: '1rem' }}>
        <button className="chip" onClick={addRow}>
          + Add Parameter
        </button>
        {visibleInputCount < INPUT_COLS.length && (
          <button className="chip" onClick={() => setVisibleInputCount((n) => Math.min(INPUT_COLS.length, n + 1))}>
            + Add Input (In {visibleInputCount + 1})
          </button>
        )}
        <button onClick={() => commitMutation.mutate(rows)}>💾 Save Model Mapping</button>
      </div>
      {commitMutation.isSuccess && (
        <div style={{ marginTop: '0.75rem' }}>
          <Callout variant="success">Model mapping updated for this session.</Callout>
        </div>
      )}
    </div>
  )
}
