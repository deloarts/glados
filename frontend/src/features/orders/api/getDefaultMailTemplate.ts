import { webApi } from '@/core/api/webRequest'

export interface DefaultMailTemplateResult {
  kind: string
  // The resolved language, which may differ after the fallback chain
  // (requested, tenant default, enGB).
  language: string
  subject: string
  body: string
  // false when nothing is configured anywhere; body is then empty and must not
  // be used.
  configured: boolean
}

/**
 * Needs no permission, since every user composing a supplier mail needs it.
 * Limited to the supplier kinds, so non-admins cannot read system mail
 * bodies through it.
 */
export async function getDefaultMailTemplate(
  kind: 'request' | 'order' | 'order_canceled',
  language: string | null,
): Promise<DefaultMailTemplateResult> {
  return webApi.get('/mail/templates/default', {
    // A null language is omitted, so the backend's fallback chain applies.
    query: { kind, language: language ?? undefined },
  })
}
