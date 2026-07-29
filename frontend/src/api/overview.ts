import { apiClient } from './client'
import type { OverviewResponse } from './types'

export async function getOverview(): Promise<OverviewResponse> {
  const { data } = await apiClient.get<OverviewResponse>('/overview')
  return data
}

// "Use for What-If Analysis" on Experiment History — marks model_name as the
// active predictor for parameter; only one model can be selected per
// parameter at a time (enforced server-side).
export async function selectModelForParameter(parameter: string, model_name: string): Promise<OverviewResponse> {
  const { data } = await apiClient.post<OverviewResponse>('/overview/select-model', { parameter, model_name })
  return data
}

export async function clearModelSelection(parameter: string): Promise<OverviewResponse> {
  const { data } = await apiClient.post<OverviewResponse>('/overview/clear-selection', { parameter })
  return data
}
