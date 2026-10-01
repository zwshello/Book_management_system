import { apiClient } from './client'
import type { Overview } from '../types/domain'
export async function getOverview(): Promise<Overview> { const { data } = await apiClient.get<Overview>('/statistics/overview'); return data }
