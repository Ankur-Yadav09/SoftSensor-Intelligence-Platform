import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { getOverview } from '../../api/overview'
import { getConfigStatus, getModelsStatus } from '../../api/whatIf'
import { StatusCard } from '../../components/StatusCard'

// The whole-application landing page (route '/'). Intentionally thin —
// detailed Soft Sensor charts/tables live on /soft-sensor-overview, and
// detailed What-If status lives on /what-if/case-setup. This page just
// orients the user and links to both modules.
export function AppOverviewPage() {
  const softSensorQuery = useQuery({ queryKey: ['overview'], queryFn: getOverview })
  const whatIfConfigQuery = useQuery({ queryKey: ['whatif-config-status'], queryFn: getConfigStatus })
  const whatIfModelsQuery = useQuery({ queryKey: ['whatif-models-status'], queryFn: getModelsStatus })

  const datasetCount = softSensorQuery.data?.datasets.length ?? 0
  const modelCount = softSensorQuery.data?.saved_models.length ?? 0

  const whatIfReady =
    !!whatIfConfigQuery.data?.pi_mapping_present &&
    !!whatIfConfigQuery.data?.model_details_present &&
    !!whatIfModelsQuery.data?.all_present

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.75rem' }}>
      <div>
        <h1>🏭 SoftSense AI — Industrial Intelligence</h1>
        <p className="caption">
          A unified platform for soft-sensor development and what-if process simulation.
        </p>
      </div>

      <div style={{ display: 'flex', gap: '1.5rem', flexWrap: 'wrap' }}>
        <div className="card" style={{ flex: 1, minWidth: 320, padding: '1.5rem' }}>
          <h2 style={{ fontSize: '1.15rem', marginTop: 0 }}>🧪 Soft Sensor Module</h2>
          <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap', marginBottom: '1rem' }}>
            <StatusCard label="Datasets Stored" value={String(datasetCount)} tone={datasetCount > 0 ? 'info' : 'warning'} />
            <StatusCard label="Models Trained" value={String(modelCount)} tone={modelCount > 0 ? 'info' : 'warning'} />
          </div>
          <Link to="/soft-sensor-overview">
            <button>Go to Soft Sensor Module →</button>
          </Link>
        </div>

        <div className="card" style={{ flex: 1, minWidth: 320, padding: '1.5rem' }}>
          <h2 style={{ fontSize: '1.15rem', marginTop: 0 }}>🧭 What-If Analysis Module</h2>
          <div style={{ marginBottom: '1rem' }}>
            <StatusCard
              label="Setup Status"
              value={whatIfReady ? 'Ready' : 'Incomplete'}
              tone={whatIfReady ? 'success' : 'warning'}
              sublabel={whatIfReady ? 'Config and trained models detected' : 'Finish case setup to unlock the dashboard'}
            />
          </div>
          <Link to="/what-if/overview">
            <button>Go to What-If Analysis Module →</button>
          </Link>
        </div>
      </div>
    </div>
  )
}
