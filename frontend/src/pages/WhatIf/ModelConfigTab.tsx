import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { getModelMapping, getModelsStatus, getMvDvCvTaglist, getPiMapping, getSectionOrder } from '../../api/whatIf'
import { Tabs } from '../../components/Tabs'
import { ExperimentHistoryPage } from '../SoftSensor/ExperimentHistoryPage'
import { FeatureSelectionPage } from '../FeatureSelection/FeatureSelectionPage'
import { PreprocessPage } from '../Preprocess/PreprocessPage'
import { TrainPage } from '../Train/TrainPage'
import { UploadPage } from '../Upload/UploadPage'
import { useActiveWhatIf } from '../../state/ActiveWhatIfContext'
import { allowedSet } from './caseSetupHelpers'
import { CorrelationMatrixView } from './CorrelationMatrixView'
import { ModelDevelopmentStepper } from './ModelDevelopmentStepper'
import { ModelMappingEditor } from './ModelMappingEditor'
import { ModelStatusPanel } from './ModelStatusPanel'
import { TrainingDataUpload } from './TrainingDataUpload'
import type { ModelDevPhaseKey } from './ModelDevelopmentStepper'

// "Model Config" section of What-If Setup, split into the two logical parts
// of building a model: an iterative "Model Development" workflow (Connect
// Data / Data Health / Model Definition / AI Feature Discovery / Build
// Model — freely revisit any step, rebuild, run more experiments) and
// "Experimentation & Model Selection" (compare every experiment Model
// Development has produced, mark one per Predicted Parameter as the model
// What-If Analysis actually uses — see ExperimentHistoryPage.tsx and
// src/whatif/engine.py::predict_and_update_with_soft_sensor_model). All
// Soft Sensor pages are reused verbatim, no duplicated implementations.
// Correlation Matrix isn't a standalone tab — it's appended inside Data
// Health, scoped to What-If's own training workbook. The dedicated
// Kalman-filter training step lives folded into Experimentation & Model
// Selection as a secondary/fallback action for parameters with no
// Experiment-History-selected model.
export function ModelConfigTab() {
  const navigate = useNavigate()
  const { targetSection } = useActiveWhatIf()
  const [outerTab, setOuterTab] = useState(0)
  const [devPhase, setDevPhase] = useState<ModelDevPhaseKey>('connect')

  const sectionOrderQuery = useQuery({ queryKey: ['whatif-section-order'], queryFn: getSectionOrder })
  const piMappingQuery = useQuery({ queryKey: ['whatif-pi-mapping'], queryFn: getPiMapping })
  const mvdvcvQuery = useQuery({ queryKey: ['whatif-mvdvcv'], queryFn: getMvDvCvTaglist })
  const modelMappingQuery = useQuery({ queryKey: ['whatif-model-mapping'], queryFn: getModelMapping })
  const modelStatusQuery = useQuery({ queryKey: ['whatif-models-status'], queryFn: getModelsStatus })

  const sectionOrderList = (sectionOrderQuery.data ?? []).map((r) => r.Section?.trim() ?? '').filter(Boolean)
  const allowed = allowedSet(sectionOrderList, targetSection)
  const piRows = piMappingQuery.data ?? []
  const mvdvcvRows = mvdvcvQuery.data ?? []
  const modelMappingComplete = (modelMappingQuery.data?.rows ?? []).some(
    (r) => (r['Predicted parameter'] ?? '').trim() !== '',
  )

  const readyForAnalysis =
    !!piRows.length && !!(modelMappingQuery.data?.rows.length) && !!modelStatusQuery.data?.all_present

  let devContent
  if (devPhase === 'connect') {
    devContent = <UploadPage hideStepper onContinue={() => setDevPhase('health')} />
  } else if (devPhase === 'health') {
    devContent = (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
        <PreprocessPage hideStepper onContinue={() => setDevPhase('modeldef')} />
        <div style={{ marginTop: '0.5rem', paddingTop: '1.5rem', borderTop: '1px solid var(--border)' }}>
          <h3 style={{ marginTop: 0 }}>What-If Training Data — Correlation Matrix</h3>
          <p className="caption">
            Pearson correlation of the What-If training workbook — spot strongly related tags before mapping model
            inputs below.
          </p>
          <CorrelationMatrixView />
        </div>
      </div>
    )
  } else if (devPhase === 'modeldef') {
    devContent = (
      <div>
        <p className="caption">
          Active scope: {[...allowed].length ? sectionOrderList.filter((s) => allowed.has(s.toLowerCase())).join(', ') : 'all sections'}.
          Maps each predicted parameter to its Section and the ordered input feature tags its Kalman model consumes.
          {modelMappingComplete && (
            <span className="pill active" style={{ marginLeft: '0.6rem' }}>
              ✓ Configured
            </span>
          )}
        </p>
        <ModelMappingEditor
          allowed={allowed}
          piRows={piRows}
          mvdvcvRows={mvdvcvRows}
          sectionOptions={['', ...sectionOrderList]}
        />
        <button style={{ marginTop: '1.25rem' }} onClick={() => setDevPhase('discovery')}>
          Continue to AI Feature Discovery →
        </button>
      </div>
    )
  } else if (devPhase === 'discovery') {
    devContent = (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
        <FeatureSelectionPage hideStepper />
        <button onClick={() => setDevPhase('build')}>Continue to Build Model →</button>
      </div>
    )
  } else {
    devContent = <TrainPage hideStepper onContinue={() => setOuterTab(1)} />
  }

  return (
    <Tabs
      activeIndex={outerTab}
      onChange={setOuterTab}
      tabs={[
        {
          label: 'Model Development',
          content: (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
              <ModelDevelopmentStepper current={devPhase} onSelect={setDevPhase} />
              {devContent}
            </div>
          ),
        },
        {
          label: 'Experimentation & Model Selection',
          content: (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
              <ExperimentHistoryPage />
              <details className="card" style={{ padding: '1.5rem' }}>
                <summary style={{ cursor: 'pointer', fontWeight: 600 }}>
                  Advanced: train dedicated Kalman filter models
                </summary>
                <p className="caption" style={{ marginTop: '0.75rem' }}>
                  Fallback for any parameter with no experiment "Selected for What-If Analysis" above — What-If
                  Analysis uses this dedicated Kalman model for those parameters automatically.
                </p>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem', marginTop: '1rem' }}>
                  <div className="card" style={{ padding: '1.5rem' }}>
                    <h3 style={{ marginTop: 0 }}>Training Dataset</h3>
                    <TrainingDataUpload />
                  </div>
                  <ModelStatusPanel
                    status={modelStatusQuery.data}
                    isLoading={modelStatusQuery.isLoading}
                    canProceed={readyForAnalysis}
                    onProceed={() => navigate('/what-if/dashboard')}
                  />
                </div>
              </details>
            </div>
          ),
        },
      ]}
    />
  )
}
