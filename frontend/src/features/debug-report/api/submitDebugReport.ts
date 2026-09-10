import { api } from '@/api/client'
import type { SubmitDebugReportInput } from '../schemas'

export async function submitDebugReport(payload: SubmitDebugReportInput): Promise<{ success: true }> {
  return api.submitDebugReport(payload)
}
