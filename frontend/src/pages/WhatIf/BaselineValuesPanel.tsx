import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { getBaseline } from '../../api/whatIf'
import { DataTable } from '../../components/DataTable'

interface BaselineValuesPanelProps {
  timestamp: string
  tags: string[]
}

export function BaselineValuesPanel({ timestamp, tags }: BaselineValuesPanelProps) {
  const [open, setOpen] = useState(false)
  const query = useQuery({
    queryKey: ['whatif-baseline', timestamp, tags],
    queryFn: () => getBaseline(timestamp, tags),
    enabled: open && !!timestamp,
  })

  const rows = query.data ? Object.entries(query.data).map(([parameter, value]) => ({ parameter, value })) : []

  return (
    <div>
      <button className="chip" onClick={() => setOpen((o) => !o)}>
        {open ? '▲' : '▼'} 🔎 Baseline Process Values at Selected Timestamp
      </button>
      {open && (
        <div style={{ marginTop: '0.75rem' }}>
          <DataTable
            columns={[
              { header: 'Parameter', render: (r) => r.parameter },
              {
                header: 'Current Value',
                render: (r) => (typeof r.value === 'number' ? r.value.toFixed(2) : String(r.value ?? '')),
              },
            ]}
            rows={rows}
            keyFn={(r) => r.parameter}
            maxVisibleRows={8}
          />
        </div>
      )}
    </div>
  )
}
