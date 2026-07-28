import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { commitSectionOrder, getSectionOrder } from '../../api/whatIf'
import { Callout } from '../../components/Callout'
import type { SectionOrderRow } from '../../api/types'

// Editor for the plant's process-flow order (Section Order sheet) — used by
// src/whatif/engine.py's section-scoping (filter_model_details_by_section)
// to decide what "upstream of the target section" means. Requires at least
// 2 distinct sections to be meaningful.
export function SectionOrderEditor() {
  const queryClient = useQueryClient()
  const query = useQuery({ queryKey: ['whatif-section-order'], queryFn: getSectionOrder })
  const [rows, setRows] = useState<SectionOrderRow[]>([])

  useEffect(() => {
    if (query.data) setRows(query.data)
  }, [query.data])

  const commitMutation = useMutation({
    mutationFn: commitSectionOrder,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['whatif-section-order'] })
      queryClient.invalidateQueries({ queryKey: ['whatif-target-section'] })
    },
  })

  if (query.isLoading) return <p className="caption">Loading process execution order…</p>

  const distinctSections = new Set(rows.map((r) => r.Section).filter(Boolean))

  function updateCell(index: number, field: keyof SectionOrderRow, value: string) {
    const next = [...rows]
    next[index] = { ...next[index], [field]: value }
    setRows(next)
  }

  function addRow() {
    setRows([...rows, { 'Sr.no': rows.length + 1, Section: '' }])
  }

  function removeRow(index: number) {
    setRows(rows.filter((_, i) => i !== index))
  }

  return (
    <div>
      <p className="caption">
        The plant's process-flow order (e.g. Furnace → Quench → CGC → PRC → ERC → Cold). This defines what "upstream"
        means when a Target Section scopes a what-if run.
      </p>
      <table className="table-compact">
        <thead>
          <tr>
            <th>Sr.no</th>
            <th>Section</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i}>
              <td>
                <input
                  type="number"
                  value={row['Sr.no']}
                  onChange={(e) => updateCell(i, 'Sr.no', e.target.value)}
                  style={{ width: 70 }}
                />
              </td>
              <td>
                <input
                  type="text"
                  value={row.Section}
                  onChange={(e) => updateCell(i, 'Section', e.target.value)}
                  style={{ width: 180 }}
                />
              </td>
              <td>
                <button className="chip" onClick={() => removeRow(i)}>
                  Remove
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div style={{ display: 'flex', gap: '0.75rem', marginTop: '1rem' }}>
        <button className="chip" onClick={addRow}>
          + Add Section
        </button>
        <button onClick={() => commitMutation.mutate(rows)} disabled={distinctSections.size < 2}>
          💾 Save Section Order
        </button>
      </div>
      {distinctSections.size < 2 && (
        <div style={{ marginTop: '0.75rem' }}>
          <Callout variant="warning">At least 2 distinct sections are required.</Callout>
        </div>
      )}
      {commitMutation.isSuccess && (
        <div style={{ marginTop: '0.75rem' }}>
          <Callout variant="success">Section order updated for this session.</Callout>
        </div>
      )}
    </div>
  )
}
