import { webApi } from '@/core/api/webRequest'
import type { AdminMailTemplatesResponse } from '../types/adminSettingsTypes'

export async function getMailTemplates(): Promise<AdminMailTemplatesResponse> {
  return webApi.get('/admin/settings/mail/templates')
}
