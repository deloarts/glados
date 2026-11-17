import { webApi } from '@/core/api/webRequest'

export async function sendTestMail(to: string): Promise<void> {
  await webApi.post('/admin/settings/mail/test', { body: { to } })
}
