import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { commitUserInputs, getUserInputs } from '../../api/whatIf'
import { Callout } from '../../components/Callout'
import type { UserInputsRow } from '../../api/types'

const FIELDS: (keyof UserInputsRow)[] = ['Parameter', 'Value', 'Lower Limit', 'Upper Limit', 'Remark']

// Editor for the "user inputs" sheet: the tags that get a Simulation
// Overrides text box on the Dashboard, with their default value and
// override bounds.
export function UserInputsEditor() {
  const queryClient = useQueryClient()
  const query = useQuery({ queryKey: ['whatif-user-inputs'], queryFn: getUserInputs })
  const [rows, setRows] = useState<UserInputsRow[]>([])

  useEffect(() => {
    if (query.data) setRows(query.data)
  }, [query.data])

  const commitMutation = useMutation({
    mutationFn: commitUserInputs,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['whatif-user-inputs'] }),
  })

  if (query.isLoading) return <p className="caption">Loading user inputs…</p>

  function updateCell(index: number, field: keyof UserInputsRow, value: string) {
    const next = [...rows]
    next[index] = { ...next[index], [field]: value }
    setRows(next)
  }

  function addRow() {
    setRows([...rows, { Parameter: '' }])
  }

  function removeRow(index: number) {
    setRows(rows.filter((_, i) => i !== index))
  }

  return (
    <div>
      <p className="caption">Default value and override bounds for each tag exposed as a Simulation Override.</p>
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
                      style={{ width: f === 'Remark' ? 220 : 130 }}
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
          + Add Parameter
        </button>
        <button onClick={() => commitMutation.mutate(rows)}>💾 Save User Inputs</button>
      </div>
      {commitMutation.isSuccess && (
        <div style={{ marginTop: '0.75rem' }}>
          <Callout variant="success">User inputs updated for this session.</Callout>
        </div>
      )}
    </div>
  )
}
