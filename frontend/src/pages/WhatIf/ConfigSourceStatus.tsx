import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useRef, useState } from 'react'
import { uploadConfig } from '../../api/whatIf'
import { Callout } from '../../components/Callout'
import { StepHeading } from '../../components/StepHeading'
import type { WhatIfConfigStatus } from '../../api/types'

interface ConfigSourceStatusProps {
  status: WhatIfConfigStatus | undefined
  onUploaded: () => void
}

export function ConfigSourceStatus({ status, onUploaded }: ConfigSourceStatusProps) {
  const queryClient = useQueryClient()
  const [open, setOpen] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)

  const uploadMutation = useMutation({
    mutationFn: uploadConfig,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['whatif-config-status'] })
      queryClient.invalidateQueries({ queryKey: ['whatif-pi-mapping'] })
      queryClient.invalidateQueries({ queryKey: ['whatif-model-mapping'] })
      queryClient.invalidateQueries({ queryKey: ['whatif-detected-counts'] })
      onUploaded()
    },
  })

  const piOk = !!status?.pi_mapping_present
  const modelOk = !!status?.model_details_present

  return (
    <div className="card" style={{ padding: '1.5rem' }}>
      <StepHeading step={1} title="Configuration Source" />

      {piOk || modelOk ? (
        <Callout variant="success">
          Config auto-loaded from disk — PI Tag Mapping: {piOk ? status!.pi_mapping_row_count : 'missing'} · Model
          Mapping: {modelOk ? status!.model_details_row_count : 'missing'}
        </Callout>
      ) : (
        <Callout variant="warning">
          No Config_file.xlsx found under Data/. Use the optional upload below, or place the file on disk and
          reload.
        </Callout>
      )}

      <div style={{ marginTop: '1rem' }}>
        <button className="chip" onClick={() => setOpen((o) => !o)}>
          {open ? '▲' : '▼'} Optional: upload a config workbook to override
        </button>
        {open && (
          <div style={{ marginTop: '0.75rem', display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <input ref={fileRef} type="file" accept=".xlsx" />
            <button
              disabled={uploadMutation.isPending}
              onClick={() => {
                const file = fileRef.current?.files?.[0]
                if (file) uploadMutation.mutate(file)
              }}
            >
              {uploadMutation.isPending ? 'Uploading…' : 'Upload'}
            </button>
          </div>
        )}
        {uploadMutation.isSuccess && (
          <div style={{ marginTop: '0.5rem' }}>
            <Callout variant="success">Config workbook uploaded and now in effect.</Callout>
          </div>
        )}
        {uploadMutation.isError && (
          <div style={{ marginTop: '0.5rem' }}>
            <Callout variant="error">
              {(uploadMutation.error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
                'Could not parse the workbook.'}
            </Callout>
          </div>
        )}
      </div>
    </div>
  )
}
