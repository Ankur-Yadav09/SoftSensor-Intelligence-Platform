import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  generateMapping,
  getConfigStatus,
  getDetectedCounts,
  getModelMapping,
  getModelsStatus,
  commitMapping as commitMappingApi,
} from '../../api/whatIf'
import { Callout } from '../../components/Callout'
import { Tabs } from '../../components/Tabs'
import { useActiveWhatIf } from '../../state/ActiveWhatIfContext'
import { ConfigSourceStatus } from './ConfigSourceStatus'
import { MappingPreviewGrid } from './MappingPreviewGrid'
import { ModelMappingEditor } from './ModelMappingEditor'
import { ModelStatusPanel } from './ModelStatusPanel'
import { PiTagMappingEditor } from './PiTagMappingEditor'
import { PlantConfigWizard } from './PlantConfigWizard'
import { TrainingDataUpload } from './TrainingDataUpload'
import type { ModelDetailsRow, PiMappingRow } from '../../api/types'

export function CaseSetupPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { setGeneratedTags } = useActiveWhatIf()

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

  const canProceed =
    !!configStatusQuery.data?.pi_mapping_present &&
    !!configStatusQuery.data?.model_details_present &&
    !!modelStatusQuery.data?.all_present

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.75rem' }}>
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
        <h3 style={{ marginTop: 0 }}>⚙️ Configuration Editors</h3>
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

      <ModelStatusPanel status={modelStatusQuery.data} isLoading={modelStatusQuery.isLoading} />

      <div className="card" style={{ padding: '1.5rem' }}>
        <button
          disabled={!canProceed}
          onClick={() => {
            queryClient.invalidateQueries({ queryKey: ['whatif-config-status'] })
            queryClient.invalidateQueries({ queryKey: ['whatif-models-status'] })
            navigate('/what-if/dashboard')
          }}
        >
          🚀 Proceed to What-If Dashboard
        </button>
        {!canProceed && (
          <p className="caption" style={{ marginTop: '0.5rem' }}>
            Requires: PI Tag Mapping present, Model Mapping present, and all trained Kalman models detected.
          </p>
        )}
      </div>
    </div>
  )
}
