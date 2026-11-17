import { webApi } from '@/core/api/webRequest'

export async function deleteAllSessions(): Promise<void> {
  await webApi.delete('/users/sessions')
}
