import { webApi } from '@/core/api/webRequest'

export interface SendMailPayload {
  to: string
  subject: string
  html_body: string
  cc?: string
  reply_to?: string
}

export async function sendMail(payload: SendMailPayload): Promise<void> {
  await webApi.post('/mail/send', { body: payload })
}
