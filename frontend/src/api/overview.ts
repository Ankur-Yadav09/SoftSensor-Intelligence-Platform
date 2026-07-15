import { apiClient } from './client'
import type { OverviewResponse } from './types'

export async function getOverview(): Promise<OverviewResponse> {
  const { data } = await apiClient.get<OverviewResponse>('/overview')
  return data
}
