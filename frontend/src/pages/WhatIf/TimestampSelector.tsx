import { useQuery } from '@tanstack/react-query'
import { useEffect } from 'react'
import { getDates, getTimestamps } from '../../api/whatIf'

interface TimestampSelectorProps {
  selectedDate: string
  onDateChange: (date: string) => void
  selectedTimestamp: string
  onTimestampChange: (ts: string) => void
}

export function TimestampSelector({ selectedDate, onDateChange, selectedTimestamp, onTimestampChange }: TimestampSelectorProps) {
  const datesQuery = useQuery({ queryKey: ['whatif-dates'], queryFn: getDates })
  const timestampsQuery = useQuery({
    queryKey: ['whatif-timestamps', selectedDate],
    queryFn: () => getTimestamps(selectedDate),
    enabled: !!selectedDate,
  })

  useEffect(() => {
    if (!selectedDate && datesQuery.data && datesQuery.data.length > 0) {
      onDateChange(datesQuery.data[datesQuery.data.length - 1])
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [datesQuery.data])

  useEffect(() => {
    if (timestampsQuery.data && timestampsQuery.data.length > 0 && !timestampsQuery.data.includes(selectedTimestamp)) {
      onTimestampChange(timestampsQuery.data[timestampsQuery.data.length - 1])
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [timestampsQuery.data])

  return (
    <div style={{ display: 'flex', gap: '1.5rem', flexWrap: 'wrap' }}>
      <label>
        <div className="caption">Historical Target Date</div>
        <select value={selectedDate} onChange={(e) => onDateChange(e.target.value)} style={{ minWidth: 180 }}>
          {(datesQuery.data ?? []).map((d) => (
            <option key={d} value={d}>{d}</option>
          ))}
        </select>
      </label>
      <label>
        <div className="caption">Process Snapshot Timestamp</div>
        <select value={selectedTimestamp} onChange={(e) => onTimestampChange(e.target.value)} style={{ minWidth: 200 }}>
          {(timestampsQuery.data ?? []).map((t) => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>
      </label>
    </div>
  )
}
