import { getSupplierMailRecipients } from '../api/contactsApi'

export type SupplierMailKind = 'request' | 'order'

/**
 * The To field of a supplier mail from the supplier's contacts flagged for
 * that kind of mail, comma separated, or null when none is flagged. A
 * failed lookup also answers null, so the mail falls back to the supplier's
 * own address.
 */
export async function flaggedSupplierRecipients(
  supplierId: number,
  kind: SupplierMailKind,
): Promise<string | null> {
  try {
    const recipients = await getSupplierMailRecipients(supplierId)
    const emails = recipients[kind].map((recipient) => recipient.email)
    return emails.length > 0 ? emails.join(', ') : null
  } catch {
    return null
  }
}
