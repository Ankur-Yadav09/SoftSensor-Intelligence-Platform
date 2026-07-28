import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { commitMvDvCvTaglist, getMvDvCvTaglist } from '../../api/whatIf'
import { Callout } from '../../components/Callout'
import { inSectionScope } from './caseSetupHelpers'
import type { MvDvCvTagRow } from '../../api/types'

const FIELDS: (keyof MvDvCvTagRow)[] = ['Name', 'GeneralizedDescription', 'Section', 'Type']

interface MvDvCvTagListEditorProps {
  /** Restricts which rows are shown/editable to those in-scope. Omit for
   * the unscoped, full-list view used outside the wizard. */
  allowed?: Set<string>
}

// Editor for the optional MV/DV/CV Tag List — a prioritized, plant-engineer
// curated input-tag source. When present, Model Mapping's input dropdowns
// list these tags before the remaining PI tags.
export function MvDvCvTagListEditor({ allowed }: MvDvCvTagListEditorProps) {
  const queryClient = useQueryClient()
  const query = useQuery({ queryKey: ['whatif-mvdvcv'], queryFn: getMvDvCvTaglist })
  const [rows, setRows] = useState<MvDvCvTagRow[]>([])

  useEffect(() => {
    if (query.data) setRows(query.data)
  }, [query.data])

  const commitMutation = useMutation({
    mutationFn: commitMvDvCvTaglist,
    onSuccess: (result) => {
      setRows(result)
      queryClient.setQueryData(['whatif-mvdvcv'], result)
    },
  })

  if (query.isLoading) return <p className="caption">Loading MV/DV/CV tag list…</p>

  const visibleIndices = rows
    .map((_, i) => i)
    .filter((i) => !allowed || inSectionScope(rows[i].Section, allowed, rows[i].GeneralizedDescription))
  const hiddenCount = rows.length - visibleIndices.length

  function updateCell(index: number, field: keyof MvDvCvTagRow, value: string) {
    const next = [...rows]
    next[index] = { ...next[index], [field]: value }
    setRows(next)
  }

  function addRow() {
    setRows([...rows, { Name: '', GeneralizedDescription: '', Section: '', Type: '' }])
  }

  function removeRow(index: number) {
    setRows(rows.filter((_, i) => i !== index))
  }

  return (
    <div>
      <p className="caption">
        Optional: Manipulated/Disturbance/Controlled variable tags, prioritized as an input-tag source for Model
        Mapping ahead of the general PI Tag Mapping list.
      </p>
      <div style={{ overflowX: 'auto' }}>
        <table className="table-compact">
          <thead>
            <tr>
              {FIELDS.map((f) => (
                <th key={f}>{f}</th>
              ))}
              <th />
            </tr>
          </thead>
          <tbody>
            {visibleIndices.map((i) => (
              <tr key={i}>
                {FIELDS.map((f) => (
                  <td key={f}>
                    <input
                      type="text"
                      value={rows[i][f] ?? ''}
                      onChange={(e) => updateCell(i, f, e.target.value)}
                      style={{ width: 180 }}
                    />
                  </td>
                ))}
                <td>
                  <button className="chip" onClick={() => removeRow(i)}>
                    Remove
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {hiddenCount > 0 && (
        <p className="caption" style={{ marginTop: '0.5rem' }}>
          {hiddenCount} row(s) belonging to other sections are hidden here (left untouched).
        </p>
      )}
      <div style={{ display: 'flex', gap: '0.75rem', marginTop: '1rem' }}>
        <button className="chip" onClick={addRow}>
          + Add Tag
        </button>
        <button onClick={() => commitMutation.mutate(rows)}>💾 Save MV/DV/CV Tag List</button>
      </div>
      {commitMutation.isSuccess && (
        <div style={{ marginTop: '0.75rem' }}>
          <Callout variant="success">MV/DV/CV tag list updated for this session.</Callout>
        </div>
      )}
    </div>
  )
}
