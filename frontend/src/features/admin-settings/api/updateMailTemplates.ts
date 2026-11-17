import { webApi } from '@/core/api/webRequest'
import type {
  MailTemplateKind,
  MailTemplateKindGroup,
  UpdateMailTemplatesCommand,
} from '../types/adminSettingsTypes'

/**
 * Kind-scoped save: the dialog's transaction boundary. The response is a
 * single MailTemplateKindGroup for this kind (not a list, not `{ templates }`),
 * carrying every language's entries, never the other eleven kinds'.
 */
export async function updateMailTemplates(
  kind: MailTemplateKind,
  cmd: UpdateMailTemplatesCommand,
): Promise<MailTemplateKindGroup> {
  return webApi.put('/admin/settings/mail/templates/{kind}', { path: { kind }, body: cmd })
}
