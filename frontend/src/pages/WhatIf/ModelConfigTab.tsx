import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { getModelMapping, getModelsStatus, getMvDvCvTaglist, getPiMapping, getSectionOrder } from '../../api/whatIf'
import { Tabs } from '../../components/Tabs'
import { ExperimentHistoryPage } from '../SoftSensor/ExperimentHistoryPage'
import { FeatureSelectionPage } from '../FeatureSelection/FeatureSelectionPage'
import { PreprocessPage } from '../Preprocess/PreprocessPage'
import { TrainPage } from '../Train/TrainPage'
import { UploadPage } from '../Upload/UploadPage'
import { useActiveWhatIf } from '../../state/ActiveWhatIfContext'
import { allowedSet, modelInputOptions } from './caseSetupHelpers'
import { CorrelationMatrixView } from './CorrelationMatrixView'
import { ModelMappingEditor } from './ModelMappingEditor'
import { ModelStatusPanel } from './ModelStatusPanel'
import { TrainingDataUpload } from './TrainingDataUpload'

// "Model Config" section of What-If Setup — reuses the existing Soft Sensor
// pages verbatim (Connect Data / Data Health / AI Feature Discovery / Build
// Model / Experiment History — no duplicated implementations) alongside the
// two What-If-specific steps (Model Mapping, Generate What-If Models), all
// as horizontal sub-tabs. Correlation Matrix isn't a standalone tab — it's
// appended inside Data Health, scoped to What-If's own training workbook.
export function ModelConfigTab() {
  const navigate = useNavigate()
  const { targetSection } = useActiveWhatIf()

  const sectionOrderQuery = useQuery({ queryKey: ['whatif-section-order'], queryFn: getSectionOrder })
  const piMappingQuery = useQuery({ queryKey: ['whatif-pi-mapping'], queryFn: getPiMapping })
  const mvdvcvQuery = useQuery({ queryKey: ['whatif-mvdvcv'], queryFn: getMvDvCvTaglist })
  const modelMappingQuery = useQuery({ queryKey: ['whatif-model-mapping'], queryFn: getModelMapping })
  const modelStatusQuery = useQuery({ queryKey: ['whatif-models-status'], queryFn: getModelsStatus })

  const sectionOrderList = (sectionOrderQuery.data ?? []).map((r) => r.Section?.trim() ?? '').filter(Boolean)
  const allowed = allowedSet(sectionOrderList, targetSection)
  const piRows = piMappingQuery.data ?? []
  const mvdvcvRows = mvdvcvQuery.data ?? []
  const inputOptions = modelInputOptions(piRows, mvdvcvRows, allowed)
  const modelMappingComplete = (modelMappingQuery.data?.rows ?? []).some(
    (r) => (r['Predicted parameter'] ?? '').trim() !== '',
  )

  const readyForAnalysis =
    !!piRows.length && !!(modelMappingQuery.data?.rows.length) && !!modelStatusQuery.data?.all_present

  return (
    <Tabs
      tabs={[
        { label: '📤 Connect Data', content: <UploadPage /> },
        {
          label: '⚙️ Data Health',
          content: (
            <div>
              <PreprocessPage />
              <div style={{ marginTop: '2rem', paddingTop: '1.5rem', borderTop: '1px solid var(--border)' }}>
                <h3 style={{ marginTop: 0 }}>📈 What-If Training Data — Correlation Matrix</h3>
                <p className="caption">
                  Pearson correlation of the What-If training workbook — spot strongly related tags before mapping
                  model inputs below.
                </p>
                <CorrelationMatrixView />
              </div>
            </div>
          ),
        },
        { label: '🔍 AI Feature Discovery', content: <FeatureSelectionPage /> },
        { label: '🧠 Build Model', content: <TrainPage /> },
        { label: '📋 Experiment History', content: <ExperimentHistoryPage /> },
        {
          label: '🧭 Model Mapping',
          complete: modelMappingComplete,
          content: (
            <div>
              <p className="caption">
                Active scope: {[...allowed].length ? sectionOrderList.filter((s) => allowed.has(s.toLowerCase())).join(', ') : 'all sections'}.
                Maps each predicted parameter to its Section and the ordered input feature tags its Kalman model
                consumes.
              </p>
              <ModelMappingEditor allowed={allowed} tagOptions={inputOptions} sectionOptions={['', ...sectionOrderList]} />
            </div>
          ),
        },
        {
          label: '🧠 Generate What-If Models',
          complete: !!modelStatusQuery.data?.all_present,
          content: (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
              <div className="card" style={{ padding: '1.5rem' }}>
                <h3 style={{ marginTop: 0 }}>📤 Training Dataset</h3>
                <TrainingDataUpload />
              </div>
              <ModelStatusPanel
                status={modelStatusQuery.data}
                isLoading={modelStatusQuery.isLoading}
                canProceed={readyForAnalysis}
                onProceed={() => navigate('/what-if/dashboard')}
              />
            </div>
          ),
        },
      ]}
    />
  )
}
