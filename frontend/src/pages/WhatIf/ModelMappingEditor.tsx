import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { commitModelMapping, getModelMapping } from '../../api/whatIf'
import { Callout } from '../../components/Callout'
import { inSectionScope, modelInputOptionsForSection } from './caseSetupHelpers'
import { SECTION_OPTIONS } from './whatIfConstants'
import type { ModelDetailsRow, MvDvCvTagRow, PiMappingRow } from '../../api/types'

const INPUT_COLS = Array.from({ length: 8 }, (_, i) => `Input parameter_${i + 1}`)
const STICKY_COL_WIDTH = 200

interface ModelMappingEditorProps {
  /** Restricts which rows are shown/editable to those in-scope. Omit for
   * the unscoped, full-sheet view used outside the wizard. */
  allowed?: Set<string>
  /** Raw PI tag dictionary and MV/DV/CV tag list — used to compute each
   * row's own Input dropdown options, scoped to that row's chosen Section
   * (MV/DV/CV-prioritized). A row with no Section chosen gets the complete
   * unfiltered tag list. Falls back to the full historian tag list when
   * omitted entirely. */
  piRows?: PiMappingRow[]
  mvdvcvRows?: MvDvCvTagRow[]
  sectionOptions?: string[]
}

// Case Setup wizard Step 7: maps each predicted parameter to its Section and
// its ordered input feature tags. Rows outside the active scope stay in the
// dataset untouched, just hidden from view (see `allowed`). Each row's Input
// dropdowns are scoped to that row's own Section (see modelInputOptionsForSection) —
// choosing a Section narrows the choices to tags belonging to it; leaving it
// blank shows every tag.
export function ModelMappingEditor({ allowed, piRows, mvdvcvRows, sectionOptions }: ModelMappingEditorProps) {
  const queryClient = useQueryClient()
  const query = useQuery({ queryKey: ['whatif-model-mapping'], queryFn: getModelMapping })
  const [rows, setRows] = useState<ModelDetailsRow[]>([])

  useEffect(() => {
    if (query.data) setRows(query.data.rows)
  }, [query.data])

  const commitMutation = useMutation({
    mutationFn: commitModelMapping,
    onSuccess: (result) => {
      setRows(result)
      queryClient.setQueryData(['whatif-model-mapping'], { rows: result, historian_tags: query.data?.historian_tags ?? [] })
    },
  })

  if (query.isLoading) return <p className="caption">Loading model mapping…</p>
  if (rows.length === 0) return <p className="caption">No "Model details" sheet found in the config workbook.</p>

  const fallbackOptions = query.data?.historian_tags ?? []
  function inputOptionsForRow(row: ModelDetailsRow): string[] {
    if (!piRows) return fallbackOptions
    return modelInputOptionsForSection(piRows, mvdvcvRows ?? [], row.Section)
  }
  const sectionChoices = sectionOptions ?? SECTION_OPTIONS

  const visibleIndices = rows
    .map((_, i) => i)
    .filter((i) => !allowed || inSectionScope(rows[i].Section, allowed, rows[i]['Predicted parameter']))
  const hiddenCount = rows.length - visibleIndices.length

  function updateCell(index: number, col: string, value: string) {
    const next = [...rows]
    next[index] = { ...next[index], [col]: value }
    setRows(next)
  }

  function addRow() {
    setRows([...rows, { 'Predicted parameter': '', Section: '' }])
  }

  function removeRow(index: number) {
    setRows(rows.filter((_, i) => i !== index))
  }

  return (
    <div>
      <p className="caption">
        Maps each predicted parameter to its Section and the ordered input feature tags its Kalman model consumes.
        "Predicted parameter" stays pinned on the left; input dropdowns list MV/DV/CV tags first, then the remaining
        scoped PI tags.
      </p>
      <div className="data-table-scroll" style={{ overflowX: 'auto', maxHeight: 420, overflowY: 'auto' }}>
        <table className="table-compact">
          <thead>
            <tr>
              <th className="sticky-col" style={{ minWidth: STICKY_COL_WIDTH }}>
                Predicted parameter
              </th>
              <th>Section</th>
              {INPUT_COLS.map((c, i) => (
                <th key={c} title={c}>
                  In {i + 1}
                </th>
              ))}
              <th />
            </tr>
          </thead>
          <tbody>
            {visibleIndices.map((i) => {
              const rowInputOptions = inputOptionsForRow(rows[i])
              return (
              <tr key={i}>
                <td className="sticky-col" style={{ minWidth: STICKY_COL_WIDTH }}>
                  <input
                    type="text"
                    value={rows[i]['Predicted parameter']}
                    onChange={(e) => updateCell(i, 'Predicted parameter', e.target.value)}
                    style={{ width: 180, fontWeight: 600 }}
                  />
                </td>
                <td>
                  <select
                    value={rows[i].Section ?? ''}
                    onChange={(e) => updateCell(i, 'Section', e.target.value)}
                    style={{ width: 110 }}
                  >
                    {sectionChoices.map((s) => (
                      <option key={s} value={s}>
                        {s || '—'}
                      </option>
                    ))}
                  </select>
                </td>
                {INPUT_COLS.map((c) => (
                  <td key={c}>
                    <select
                      value={rows[i][c] ?? ''}
                      onChange={(e) => updateCell(i, c, e.target.value)}
                      style={{ width: 165 }}
                    >
                      <option value="">—</option>
                      {rowInputOptions.map((t) => (
                        <option key={t} value={t}>
                          {t}
                        </option>
                      ))}
                    </select>
                  </td>
                ))}
                <td>
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
