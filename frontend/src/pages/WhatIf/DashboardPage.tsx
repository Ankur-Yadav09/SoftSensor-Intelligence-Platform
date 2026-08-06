import { useMutation, useQuery } from '@tanstack/react-query'
import { useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { getConfigStatus, getModelsStatus, getTagOptions, runScenario } from '../../api/whatIf'
import { extractErrorMessage } from '../../api/errors'
import { Callout } from '../../components/Callout'
import { useActiveWhatIf } from '../../state/ActiveWhatIfContext'
import { ActualVsEstimatedTable } from './ActualVsEstimatedTable'
import { BaselineValuesPanel } from './BaselineValuesPanel'
import { KpiCardsRow } from './KpiCardsRow'
import { SimulationOverridesPanel } from './SimulationOverridesPanel'
import { TagSourcePanel } from './TagSourcePanel'
import { TargetSectionSelector } from './TargetSectionSelector'
import { TimestampSelector } from './TimestampSelector'
import { ValidationFiltersPanel } from './ValidationFiltersPanel'

// What-If Analysis — kept as a single flowing page matching the reference
// Streamlit "📊 What-if Dashboard" tab's layout/order exactly (Target
// Section → Tag Source → Timestamp/Baseline → Simulation Overrides →
// Compute → KPI cards → Actual vs Estimated → Historical Validation), not
// split into tabs.
export function DashboardPage() {
  const { generatedTags, targetSection, setTargetSection } = useActiveWhatIf()

  const configStatusQuery = useQuery({ queryKey: ['whatif-config-status'], queryFn: getConfigStatus })
  const modelStatusQuery = useQuery({ queryKey: ['whatif-models-status'], queryFn: getModelsStatus })

  const gateReady =
    !!configStatusQuery.data?.pi_mapping_present &&
    !!configStatusQuery.data?.model_details_present &&
    !!modelStatusQuery.data?.all_present

  const tagOptionsQuery = useQuery({
    queryKey: ['whatif-tag-options', generatedTags, targetSection],
    queryFn: () => getTagOptions(generatedTags, targetSection),
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
  const resultsRef = useRef<HTMLDivElement>(null)

  // Results land well below the Compute button — jump to them automatically
  // instead of leaving the user to notice and scroll down themselves (same
  // reasoning as the Welcome page's User Guide/FAQ auto-scroll).
  useEffect(() => {
    if (scenarioMutation.data) resultsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [scenarioMutation.data])

  if (configStatusQuery.isLoading || modelStatusQuery.isLoading) {
    return <p className="caption">Checking What-If setup status…</p>
  }

  if (!gateReady) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
        <h1>What-If Analysis</h1>
        <Callout variant="warning">
          🔒 Simulation overrides are locked. Complete{' '}
          <Link to="/what-if/case-setup">What-If Setup</Link> — PI Tag Mapping, Model Mapping, and all trained Kalman
          models must be present — before this page unlocks.
        </Callout>
      </div>
    )
  }

  function runCompute() {
    scenarioMutation.mutate({ timestamp: selectedTimestamp, overrides: validOverrides, target_section: targetSection })
  }

  const nOverrides = validOverrides.length

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.75rem' }}>
      <h1>What-If Analysis</h1>

      <div className="card" style={{ padding: '1.5rem' }}>
        <h3 style={{ marginTop: 0 }}>🎯 Target Section</h3>
        <TargetSectionSelector value={targetSection} onChange={setTargetSection} />
      </div>

      <div className="card" style={{ padding: '1.5rem' }}>
        <h3 style={{ marginTop: 0 }}>🏷️ Tag Source</h3>
        <TagSourcePanel tagOptions={tagOptionsQuery.data} selectedTags={manualTags} onChange={setManualTags} />
      </div>

      <div className="card" style={{ padding: '1.5rem' }}>
        <h3 style={{ marginTop: 0 }}>🕐 Baseline Process Snapshot</h3>
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
        onReset={() => setOverrides({})}
      />

      <div className="card" style={{ padding: '1.5rem' }}>
        <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center', flexWrap: 'wrap' }}>
          <button disabled={!selectedTimestamp || scenarioMutation.isPending} onClick={runCompute}>
            {scenarioMutation.isPending
              ? 'Processing…'
              : `🚀 Compute What-If Scenario (${nOverrides} override${nOverrides === 1 ? '' : 's'} active)`}
          </button>
          {!selectedTimestamp && <span className="caption">Pick an Available Snapshot Time above first.</span>}
        </div>
        {scenarioMutation.isError && (
          <div style={{ marginTop: '0.75rem' }}>
            <Callout variant="error">{extractErrorMessage(scenarioMutation.error, 'What-if analysis failed.')}</Callout>
          </div>
        )}
      </div>

      {scenarioMutation.data && (
        <div ref={resultsRef} style={{ display: 'flex', flexDirection: 'column', gap: '1.75rem' }}>
          {scenarioMutation.data.constraint_hit && (
            <Callout variant="warning">{scenarioMutation.data.constraint_message}</Callout>
          )}
          <KpiCardsRow kpis={scenarioMutation.data.kpis} />
          <div className="card" style={{ padding: '1.5rem' }}>
            <ActualVsEstimatedTable timestamp={selectedTimestamp} rows={scenarioMutation.data.rows} />
          </div>
          <ValidationFiltersPanel
            timestamp={selectedTimestamp}
            scenarioRows={scenarioMutation.data.rows}
            targetSection={targetSection}
          />
        </div>
      )}
    </div>
  )
}
