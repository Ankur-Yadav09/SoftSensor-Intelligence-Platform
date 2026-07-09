import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { commitModelMapping, getModelMapping } from '../../api/whatIf'
import { Callout } from '../../components/Callout'
import type { ModelDetailsRow } from '../../api/types'

const INPUT_COLS = Array.from({ length: 8 }, (_, i) => `Input parameter_${i + 1}`)

export function ModelMappingEditor() {
  const queryClient = useQueryClient()
  const query = useQuery({ queryKey: ['whatif-model-mapping'], queryFn: getModelMapping })
  const [rows, setRows] = useState<ModelDetailsRow[]>([])

  useEffect(() => {
    if (query.data) setRows(query.data.rows)
  }, [query.data])

  const commitMutation = useMutation({
    mutationFn: commitModelMapping,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['whatif-model-mapping'] }),
  })

  if (query.isLoading) return <p className="caption">Loading model mapping…</p>
  if (rows.length === 0) return <p className="caption">No "Model details" sheet found in the config workbook.</p>

  const historianTags = query.data?.historian_tags ?? []

  function updateCell(index: number, col: string, value: string) {
    const next = [...rows]
    next[index] = { ...next[index], [col]: value }
    setRows(next)
  }

  return (
    <div>
      <p className="caption">
        Maps each predicted parameter to the ordered input feature tags its Kalman model consumes. "Predicted
        parameter" is read-only; input columns are chosen from the historian tag list.
      </p>
      <div style={{ overflowX: 'auto', maxHeight: 420, overflowY: 'auto' }}>
        <table>
          <thead>
            <tr>
              <th>Predicted parameter</th>
              {INPUT_COLS.map((c) => (
                <th key={c}>{c}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr key={row['Predicted parameter']}>
                <td>{row['Predicted parameter']}</td>
                {INPUT_COLS.map((c) => (
                  <td key={c}>
                    <select value={row[c] ?? ''} onChange={(e) => updateCell(i, c, e.target.value)}>
                      <option value="">—</option>
                      {historianTags.map((t) => (
                        <option key={t} value={t}>{t}</option>
                      ))}
                    </select>
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <button style={{ marginTop: '1rem' }} onClick={() => commitMutation.mutate(rows)}>
        💾 Save Model Mapping
      </button>
      {commitMutation.isSuccess && (
        <div style={{ marginTop: '0.75rem' }}>
          <Callout variant="success">Model mapping updated for this session.</Callout>
        </div>
      )}
    </div>
  )
}
