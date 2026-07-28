import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  generateMapping,
  getColumnOrder,
  getConfigStatus,
  getConstraints,
  getDetectedCounts,
  getModelMapping,
  getModelsStatus,
  getMvDvCvTaglist,
  getPiMapping,
  getSectionOrder,
  getUserInputs,
  saveConfig,
  commitMapping as commitMappingApi,
} from '../../api/whatIf'
import { Callout } from '../../components/Callout'
import { StepHeading } from '../../components/StepHeading'
import { Tabs } from '../../components/Tabs'
import { useActiveWhatIf } from '../../state/ActiveWhatIfContext'
import { ColumnOrderEditor } from './ColumnOrderEditor'
import { ConfigSourceStatus } from './ConfigSourceStatus'
import { ConstraintsEditor } from './ConstraintsEditor'
import { CorrelationMatrixView } from './CorrelationMatrixView'
import { MappingPreviewGrid } from './MappingPreviewGrid'
import { ModelMappingEditor } from './ModelMappingEditor'
import { ModelStatusPanel } from './ModelStatusPanel'
import { MvDvCvTagListEditor } from './MvDvCvTagListEditor'
import { PiTagMappingEditor } from './PiTagMappingEditor'
import { PlantConfigWizard } from './PlantConfigWizard'
import { SectionOrderEditor } from './SectionOrderEditor'
import { TargetSectionSelector } from './TargetSectionSelector'
import { TrainingDataUpload } from './TrainingDataUpload'
import { UserInputsEditor } from './UserInputsEditor'
import type { ModelDetailsRow, PiMappingRow } from '../../api/types'

export function CaseSetupPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { setGeneratedTags, targetSection, setTargetSection } = useActiveWhatIf()

  const [configUploadedThisSession, setConfigUploadedThisSession] = useState(false)
  const [mappingRows, setMappingRows] = useState<PiMappingRow[]>([])
  const [sectionCounts, setSectionCounts] = useState<Record<string, number>>({})

  const configStatusQuery = useQuery({ queryKey: ['whatif-config-status'], queryFn: getConfigStatus })
  const detectedCountsQuery = useQuery({ queryKey: ['whatif-detected-counts'], queryFn: getDetectedCounts })
  const modelStatusQuery = useQuery({ queryKey: ['whatif-models-status'], queryFn: getModelsStatus })
  const modelMappingQuery = useQuery({ queryKey: ['whatif-model-mapping'], queryFn: getModelMapping })
  const modelDetailsForExport: ModelDetailsRow[] = modelMappingQuery.data?.rows ?? []

  const generateMutation = useMutation({
    mutationFn: generateMapping,
    onSuccess: (res) => {
      setMappingRows(res.rows)
      setSectionCounts(res.section_counts)
      const tags = Array.from(new Set(res.rows.map((r) => r['Generalized Description']).filter(Boolean)))
      setGeneratedTags(tags)
    },
  })

  const commitMutation = useMutation({
    mutationFn: commitMappingApi,
    onSuccess: (rows) => setMappingRows(rows),
  })

  function resetMapping() {
    setMappingRows([])
    setSectionCounts({})
    setGeneratedTags([])
  }

  // Persists the current server-cached state of every config sheet in one
  // call (see backend/app/services/what_if_service.py::save_config). Each
  // editor below has its own "Save X" button first — those commit endpoints
  // are stateless echoes (client carries state forward, matching this
  // module's existing PI/Model Mapping editors), so save each sheet you've
  // edited there before using this button to write everything to
  // Config_file.xlsx on disk.
  const saveConfigMutation = useMutation({
    mutationFn: async () => {
      const [pi, model, sectionOrder, mvdvcv, constraints, userInputs, columnOrder] = await Promise.all([
        queryClient.ensureQueryData({ queryKey: ['whatif-pi-mapping'], queryFn: getPiMapping }),
        queryClient.ensureQueryData({ queryKey: ['whatif-model-mapping'], queryFn: getModelMapping }),
        queryClient.ensureQueryData({ queryKey: ['whatif-section-order'], queryFn: getSectionOrder }),
        queryClient.ensureQueryData({ queryKey: ['whatif-mvdvcv'], queryFn: getMvDvCvTaglist }),
        queryClient.ensureQueryData({ queryKey: ['whatif-constraints'], queryFn: getConstraints }),
        queryClient.ensureQueryData({ queryKey: ['whatif-user-inputs'], queryFn: getUserInputs }),
        queryClient.ensureQueryData({ queryKey: ['whatif-column-order'], queryFn: getColumnOrder }),
      ])
      return saveConfig({
        pi_mapping_rows: pi,
        model_details_rows: model.rows,
        constraints_rows: constraints,
        user_inputs_rows: userInputs,
        display_order_rows: columnOrder,
        section_order_rows: sectionOrder,
        mvdvcv_rows: mvdvcv,
        target_section: targetSection,
      })
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['whatif-config-status'] }),
  })

  // Unchanged gate: PI Tag Mapping + Model Mapping present, and all trained
  // Kalman models detected — same formula as before, just consumed by
  // ModelStatusPanel's "Continue to Scenario Dashboard" action instead of a
  // separate card at the bottom of the page.
  const canProceed =
    !!configStatusQuery.data?.pi_mapping_present &&
    !!configStatusQuery.data?.model_details_present &&
    !!modelStatusQuery.data?.all_present

  function proceedToDashboard() {
    queryClient.invalidateQueries({ queryKey: ['whatif-config-status'] })
    queryClient.invalidateQueries({ queryKey: ['whatif-models-status'] })
    navigate('/what-if/dashboard')
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      <h1>What-If Case Setup</h1>
      <p className="caption">
        Configure the plant tag mapping and confirm trained models are available before running scenarios on the
        What-If Dashboard.
      </p>

      <ConfigSourceStatus
        status={configStatusQuery.data}
        onUploaded={() => setConfigUploadedThisSession(true)}
      />

      <div className="card" style={{ padding: '1.5rem' }}>
        <PlantConfigWizard
          detectedCounts={detectedCountsQuery.data}
          generating={generateMutation.isPending}
          onReset={resetMapping}
          onGenerate={(counts) => generateMutation.mutate(counts)}
        />
        {generateMutation.isError && (
          <div style={{ marginTop: '1rem' }}>
            <Callout variant="error">
              {(generateMutation.error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
                'Failed to generate the PI mapping for this line-up.'}
            </Callout>
          </div>
        )}
        <div style={{ marginTop: '1.5rem' }}>
          <MappingPreviewGrid
            rows={mappingRows}
            onChange={setMappingRows}
            onCommit={() => commitMutation.mutate(mappingRows)}
            modelDetailsRows={modelDetailsForExport}
            sectionCounts={sectionCounts}
          />
        </div>
      </div>

      <TrainingDataUpload />

      <div className="card" style={{ padding: '1.5rem' }}>
        <StepHeading step={4} title="Process Flow &amp; Target Section" />
        <TargetSectionSelector value={targetSection} onChange={setTargetSection} />
      </div>

      <div className="card" style={{ padding: '1.5rem' }}>
        <StepHeading step={5} title="Advanced Configuration" />
        <p className="caption">
          Section Order, the optional MV/DV/CV Tag List, Constraints (the generic rule engine that drives constraint
          bumps and abort checks), User Inputs, Column Order, and the training dataset's Correlation Matrix.
        </p>
        <Tabs
          tabs={[
            { label: '🔀 Section Order', content: <SectionOrderEditor /> },
            { label: '🏷️ MV/DV/CV Tag List', content: <MvDvCvTagListEditor /> },
            { label: '🚦 Constraints', content: <ConstraintsEditor /> },
            { label: '🎛️ User Inputs', content: <UserInputsEditor /> },
            { label: '📑 Column Order', content: <ColumnOrderEditor /> },
            { label: '📊 Correlation Matrix', content: <CorrelationMatrixView /> },
          ]}
        />
        <div style={{ marginTop: '1.5rem', borderTop: '1px solid var(--border)', paddingTop: '1rem' }}>
          <button onClick={() => saveConfigMutation.mutate()} disabled={saveConfigMutation.isPending}>
            {saveConfigMutation.isPending ? 'Saving…' : '💾 Save Full Configuration to Server'}
          </button>
          <p className="caption" style={{ marginTop: '0.5rem' }}>
            Writes every sheet above (and the Target Section) to Config_file.xlsx. Save each sheet you've edited with
            its own "Save" button first, then use this to persist everything to disk.
          </p>
          {saveConfigMutation.isSuccess && (
            <div style={{ marginTop: '0.5rem' }}>
              <Callout variant="success">Configuration saved to Config_file.xlsx.</Callout>
            </div>
          )}
          {saveConfigMutation.isError && (
            <div style={{ marginTop: '0.5rem' }}>
              <Callout variant="error">
                {(saveConfigMutation.error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
                  'Failed to save the configuration.'}
              </Callout>
            </div>
          )}
        </div>
      </div>

      <div className="card" style={{ padding: '1.5rem' }}>
        <StepHeading step={6} title="Configuration Editors" />
        {configUploadedThisSession ? (
          <Tabs
            tabs={[
              { label: '🏷️ PI Tag Mapping', content: <PiTagMappingEditor /> },
              { label: '🧠 Model Mapping', content: <ModelMappingEditor /> },
            ]}
          />
        ) : (
          <>
            <Callout variant="info">
              The PI Tag Mapping sheet appears here once you upload a config workbook (with the model mapping
              sheet) in Configuration Source above.
            </Callout>
            <div style={{ marginTop: '1rem' }}>
              <ModelMappingEditor />
            </div>
          </>
        )}
      </div>

      <ModelStatusPanel
        status={modelStatusQuery.data}
        isLoading={modelStatusQuery.isLoading}
        canProceed={canProceed}
        onProceed={proceedToDashboard}
      />
    </div>
  )
}
