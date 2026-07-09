import { apiClient } from './client'
import type {
  DetectedCounts,
  GenerateMappingResult,
  ModelDetailsRow,
  ModelMappingResult,
  PiMappingRow,
  TagOptionsResult,
  TrainingDataUploadResult,
  ValidationFilterCriterion,
  ValidationFilterResult,
  WhatIfConfigStatus,
  WhatIfModelStatus,
  WhatIfScenarioResult,
} from './types'

// ---------------------------------------------------------------------------
// Case setup: config / wizard / model-mapping / model-status
// ---------------------------------------------------------------------------

export async function getConfigStatus(): Promise<WhatIfConfigStatus> {
  const { data } = await apiClient.get<WhatIfConfigStatus>('/what-if/config/status')
  return data
}

export async function getPiMapping(): Promise<PiMappingRow[]> {
  const { data } = await apiClient.get<{ rows: PiMappingRow[] }>('/what-if/config/pi-mapping')
  return data.rows
}

export async function uploadConfig(file: File): Promise<WhatIfConfigStatus> {
  const form = new FormData()
  form.append('file', file)
  const { data } = await apiClient.post<WhatIfConfigStatus>('/what-if/config/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

export async function getDetectedCounts(): Promise<DetectedCounts> {
  const { data } = await apiClient.get<DetectedCounts>('/what-if/wizard/detected-counts')
  return data
}

export interface GenerateMappingRequest {
  cgc_stages: number
  prc_stages: number
  erc_stages: number
  furnaces: number
}

export async function generateMapping(body: GenerateMappingRequest): Promise<GenerateMappingResult> {
  const { data } = await apiClient.post<GenerateMappingResult>('/what-if/wizard/generate-mapping', body)
  return data
}

export async function commitMapping(rows: PiMappingRow[]): Promise<PiMappingRow[]> {
  const { data } = await apiClient.put<{ rows: PiMappingRow[] }>('/what-if/config/mapping', { rows })
  return data.rows
}

export async function getModelMapping(): Promise<ModelMappingResult> {
  const { data } = await apiClient.get<ModelMappingResult>('/what-if/config/model-mapping')
  return data
}

export async function commitModelMapping(rows: ModelDetailsRow[]): Promise<ModelDetailsRow[]> {
  const { data } = await apiClient.put<{ rows: ModelDetailsRow[] }>('/what-if/config/model-mapping', { rows })
  return data.rows
}

export async function exportConfig(
  piMappingRows: PiMappingRow[],
  modelDetailsRows: ModelDetailsRow[],
  format: 'xlsx' | 'csv',
): Promise<Blob> {
  const { data } = await apiClient.post(
    '/what-if/config/export',
    { pi_mapping_rows: piMappingRows, model_details_rows: modelDetailsRows, format },
    { responseType: 'blob' },
  )
  return data
}

export async function uploadTrainingData(file: File): Promise<TrainingDataUploadResult> {
  const form = new FormData()
  form.append('file', file)
  const { data } = await apiClient.post<TrainingDataUploadResult>('/what-if/training-data/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

export async function getModelsStatus(): Promise<WhatIfModelStatus> {
  const { data } = await apiClient.get<WhatIfModelStatus>('/what-if/models/status')
  return data
}

// ---------------------------------------------------------------------------
// Dashboard
// ---------------------------------------------------------------------------

export async function getTagOptions(generatedTags: string[]): Promise<TagOptionsResult> {
  const { data } = await apiClient.post<TagOptionsResult>('/what-if/dashboard/tag-options', {
    generated_tags: generatedTags,
  })
  return data
}

export async function getDates(): Promise<string[]> {
  const { data } = await apiClient.get<{ dates: string[] }>('/what-if/dashboard/dates')
  return data.dates
}

export async function getTimestamps(date: string): Promise<string[]> {
  const { data } = await apiClient.get<{ timestamps: string[] }>('/what-if/dashboard/timestamps', {
    params: { date },
  })
  return data.timestamps
}

export async function getBaseline(timestamp: string, tags: string[]): Promise<Record<string, unknown>> {
  const { data } = await apiClient.get<{ values: Record<string, unknown> }>('/what-if/dashboard/baseline', {
    params: { timestamp, tags: tags.join(',') },
  })
  return data.values
}

export interface RunScenarioRequest {
  timestamp: string
  overrides: { parameter: string; value: number }[]
  write_actual_vs_estimated_xlsx?: boolean
}

export async function runScenario(body: RunScenarioRequest): Promise<WhatIfScenarioResult> {
  const { data } = await apiClient.post<WhatIfScenarioResult>('/what-if/dashboard/compute', body)
  return data
}

export async function runValidationFilter(
  filters: Record<string, ValidationFilterCriterion>,
): Promise<ValidationFilterResult> {
  const { data } = await apiClient.post<ValidationFilterResult>('/what-if/dashboard/validation-filter', { filters })
  return data
}

export async function exportScenarioCsv(
  timestamp: string,
  rows: { parameter: string; actual: unknown; estimated: unknown; change: number | null }[],
  validationRows?: Record<string, unknown>[],
): Promise<Blob> {
  const { data } = await apiClient.post(
    '/what-if/dashboard/export-csv',
    { timestamp, rows, validation_rows: validationRows ?? null },
    { responseType: 'blob' },
  )
  return data
}

export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}
