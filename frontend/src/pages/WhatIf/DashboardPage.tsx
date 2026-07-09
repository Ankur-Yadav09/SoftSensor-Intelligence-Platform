import { useMutation, useQuery } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { getConfigStatus, getModelsStatus, getTagOptions, runScenario } from '../../api/whatIf'
import { Callout } from '../../components/Callout'
import { useActiveWhatIf } from '../../state/ActiveWhatIfContext'
import { ActualVsEstimatedTable } from './ActualVsEstimatedTable'
import { BaselineValuesPanel } from './BaselineValuesPanel'
import { KpiCardsRow } from './KpiCardsRow'
import { SimulationOverridesPanel } from './SimulationOverridesPanel'
import { TagSourcePanel } from './TagSourcePanel'
import { TimestampSelector } from './TimestampSelector'
import { ValidationFiltersPanel } from './ValidationFiltersPanel'

export function DashboardPage() {
  const { generatedTags } = useActiveWhatIf()

  const configStatusQuery = useQuery({ queryKey: ['whatif-config-status'], queryFn: getConfigStatus })
  const modelStatusQuery = useQuery({ queryKey: ['whatif-models-status'], queryFn: getModelsStatus })

  const gateReady =
    !!configStatusQuery.data?.pi_mapping_present &&
    !!configStatusQuery.data?.model_details_present &&
    !!modelStatusQuery.data?.all_present

  const tagOptionsQuery = useQuery({
    queryKey: ['whatif-tag-options', generatedTags],
    queryFn: () => getTagOptions(generatedTags),
    enabled: gateReady,
  })

  const [manualTags, setManualTags] = useState<Set<string>>(new Set())
  const [selectedDate, setSelectedDate] = useState('')
  const [selectedTimestamp, setSelectedTimestamp] = useState('')
  const [overrides, setOverrides] = useState<Record<string, string>>({})

  const activeTags = useMemo(() => {
    if (!tagOptionsQuery.data) return []
    return tagOptionsQuery.data.source === 'config' ? tagOptionsQuery.data.tags : Array.from(manualTags)
  }, [tagOptionsQuery.data, manualTags])

  // Mirrors the Streamlit original: an override that fails numeric or
  // boundary validation is silently dropped (kept at baseline) rather than
  // sent, exactly like whatif_runner.py's val_float = np.nan path.
  const validOverrides = useMemo(() => {
    const limits = tagOptionsQuery.data?.limits ?? {}
    return Object.entries(overrides)
      .filter(([, raw]) => raw.trim() !== '')
      .map(([parameter, raw]) => ({ parameter, value: Number(raw) }))
      .filter((o) => !Number.isNaN(o.value))
      .filter((o) => {
        const lim = limits[o.parameter]
        return !lim || (o.value >= lim.lower && o.value <= lim.upper)
      })
  }, [overrides, tagOptionsQuery.data])

  const scenarioMutation = useMutation({ mutationFn: runScenario })

  if (configStatusQuery.isLoading || modelStatusQuery.isLoading) {
    return <p className="caption">Checking What-If setup status…</p>
  }

  if (!gateReady) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
        <h1>What-If Dashboard</h1>
        <Callout variant="warning">
          🔒 Simulation overrides are locked. Complete the{' '}
          <Link to="/what-if/case-setup">What-If Case Setup</Link> page — PI Tag Mapping, Model Mapping, and all
          trained Kalman models must be present — before this dashboard unlocks.
        </Callout>
      </div>
    )
  }

  function runCompute() {
    scenarioMutation.mutate({ timestamp: selectedTimestamp, overrides: validOverrides })
  }

  const nOverrides = validOverrides.length

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.75rem' }}>
      <h1>What-If Dashboard</h1>

      <div className="card" style={{ padding: '1.5rem' }}>
        <TagSourcePanel tagOptions={tagOptionsQuery.data} selectedTags={manualTags} onChange={setManualTags} />
      </div>

      <div className="card" style={{ padding: '1.5rem' }}>
        <TimestampSelector
          selectedDate={selectedDate}
          onDateChange={setSelectedDate}
          selectedTimestamp={selectedTimestamp}
          onTimestampChange={setSelectedTimestamp}
        />
        <div style={{ marginTop: '1rem' }}>
          <BaselineValuesPanel timestamp={selectedTimestamp} tags={activeTags} />
        </div>
      </div>

      <SimulationOverridesPanel
        tags={activeTags}
        limits={tagOptionsQuery.data?.limits ?? {}}
        overrides={overrides}
        onChange={(tag, raw) => setOverrides({ ...overrides, [tag]: raw })}
      />

      <div className="card" style={{ padding: '1.5rem' }}>
        <button disabled={!selectedTimestamp || scenarioMutation.isPending} onClick={runCompute}>
          {scenarioMutation.isPending
            ? 'Processing…'
            : `🚀 Compute What-If Scenario (${nOverrides} override${nOverrides === 1 ? '' : 's'} active)`}
        </button>
        {scenarioMutation.isError && (
          <div style={{ marginTop: '0.75rem' }}>
            <Callout variant="error">
              {(scenarioMutation.error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
                'What-if analysis failed.'}
            </Callout>
          </div>
        )}
      </div>

      {scenarioMutation.data && (
        <>
          {scenarioMutation.data.constraint_hit && (
            <Callout variant="warning">{scenarioMutation.data.constraint_message}</Callout>
          )}
          <KpiCardsRow kpis={scenarioMutation.data.kpis} />
          <div className="card" style={{ padding: '1.5rem' }}>
            <ActualVsEstimatedTable timestamp={selectedTimestamp} rows={scenarioMutation.data.rows} />
          </div>
          <ValidationFiltersPanel timestamp={selectedTimestamp} scenarioRows={scenarioMutation.data.rows} />
        </>
      )}
    </div>
  )
}
