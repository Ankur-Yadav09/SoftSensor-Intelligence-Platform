import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { commitMvDvCvTaglist, getMvDvCvTaglist } from '../../api/whatIf'
import { Callout } from '../../components/Callout'
import type { MvDvCvTagRow } from '../../api/types'

const FIELDS: (keyof MvDvCvTagRow)[] = ['Name', 'GeneralizedDescription', 'Section', 'Type']

// Editor for the optional MV/DV/CV Tag List — a prioritized, plant-engineer
// curated input-tag source. When present, Model Mapping's input dropdowns
// list these tags before the remaining PI tags.
export function MvDvCvTagListEditor() {
  const queryClient = useQueryClient()
  const query = useQuery({ queryKey: ['whatif-mvdvcv'], queryFn: getMvDvCvTaglist })
  const [rows, setRows] = useState<MvDvCvTagRow[]>([])

  useEffect(() => {
    if (query.data) setRows(query.data)
  }, [query.data])

  const commitMutation = useMutation({
    mutationFn: commitMvDvCvTaglist,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['whatif-mvdvcv'] }),
  })

  if (query.isLoading) return <p className="caption">Loading MV/DV/CV tag list…</p>

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
            {rows.map((row, i) => (
              <tr key={i}>
                {FIELDS.map((f) => (
                  <td key={f}>
                    <input
                      type="text"
                      value={row[f] ?? ''}
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
