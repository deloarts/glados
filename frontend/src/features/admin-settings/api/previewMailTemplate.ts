import { webApi } from '@/core/api/webRequest'
import type {
  MailTemplateKind,
  MailTemplatePreviewResult,
  PreviewMailTemplateCommand,
} from '../types/adminSettingsTypes'

/**
 * Renders a *draft* body+subject through the real server-side engine (the
 * point of a `family: 'system'` preview: a frontend `{{ var }}` substituter
 * cannot render the digest template's `{% for %}` loop). A Jinja syntax
 * error comes back as a 400 with `{ detail }`, not a 500: the editor shows
 * it inline via extractApiError rather than a generic failure toast.
 */
export async function previewMailTemplate(
  kind: MailTemplateKind,
  cmd: PreviewMailTemplateCommand,
): Promise<MailTemplatePreviewResult> {
  return webApi.post('/admin/settings/mail/templates/{kind}/preview', { path: { kind }, body: cmd })
}
