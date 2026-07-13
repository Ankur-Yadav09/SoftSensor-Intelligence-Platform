import { useMutation } from '@tanstack/react-query'
import { useRef } from 'react'
import { uploadTrainingData } from '../../api/whatIf'
import { Callout } from '../../components/Callout'
import { StepHeading } from '../../components/StepHeading'

export function TrainingDataUpload() {
  const fileRef = useRef<HTMLInputElement>(null)
  const uploadMutation = useMutation({ mutationFn: uploadTrainingData })

  return (
    <div className="card" style={{ padding: '1.5rem' }}>
      <StepHeading step={3} title="Step A — Upload Training Dataset" />
      <p className="caption">
        Upload <code>DMC_Screen_tags_data.xlsx</code> — a single workbook containing both the "PI data" and "Furnace
        data" sheets. Used only for (future) model retraining, not for running scenarios.
      </p>

      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginTop: '0.75rem' }}>
        <input ref={fileRef} type="file" accept=".xlsx,.xls" />
        <button
          disabled={uploadMutation.isPending}
          onClick={() => {
            const file = fileRef.current?.files?.[0]
            if (file) uploadMutation.mutate(file)
          }}
        >
          {uploadMutation.isPending ? 'Uploading…' : '💾 Save training dataset to Data folder'}
        </button>
      </div>

      {uploadMutation.data && uploadMutation.data.saved && (
        <div style={{ marginTop: '0.75rem' }}>
          <Callout variant="success">Training workbook saved — sheets found: {uploadMutation.data.sheets_found.join(', ')}</Callout>
        </div>
      )}
      {uploadMutation.data && !uploadMutation.data.saved && (
        <div style={{ marginTop: '0.75rem' }}>
          <Callout variant="error">
            Missing required sheet(s): {uploadMutation.data.missing_sheets.join(', ')}. Found:{' '}
            {uploadMutation.data.sheets_found.join(', ')}
          </Callout>
        </div>
      )}
      {uploadMutation.isError && (
        <div style={{ marginTop: '0.75rem' }}>
          <Callout variant="error">
            {(uploadMutation.error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
              'Failed to read/save the training workbook.'}
          </Callout>
        </div>
      )}
    </div>
  )
}
