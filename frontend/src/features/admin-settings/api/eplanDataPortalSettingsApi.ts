import { webApi } from '@/core/api/webRequest'
import type {
  AdminEdpSettings,
  EdpConnectionTestResult,
  UpdateEdpSettingsCommand,
  VerifyEdpConnectionCommand,
} from '../types/adminSettingsTypes'

export async function getEdpSettings(): Promise<AdminEdpSettings> {
  return webApi.get('/admin/settings/eplan-data-portal')
}

export async function updateEdpSettings(cmd: UpdateEdpSettingsCommand): Promise<AdminEdpSettings> {
  return webApi.put('/admin/settings/eplan-data-portal', { body: cmd })
}

export async function testEdpConnection(
  cmd: VerifyEdpConnectionCommand,
): Promise<EdpConnectionTestResult> {
  return webApi.post('/admin/settings/eplan-data-portal/test', { body: cmd })
}
