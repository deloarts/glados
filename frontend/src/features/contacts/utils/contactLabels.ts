import type { ContactOrganisationKind } from '../types/contactResponse'

/** The name shown for a contact; an anonymised one has none left. */
export function contactDisplayName(
  t: (key: string) => string,
  contact: { name: string; anonymised?: boolean; anonymised_at?: string | null },
): string {
  const anonymised = contact.anonymised ?? Boolean(contact.anonymised_at)
  return anonymised || !contact.name ? t('contacts.anonymised') : contact.name
}

export const ORGANISATION_ICONS: Record<ContactOrganisationKind, string> = {
  customer: 'mdi-account-tie',
  supplier: 'mdi-store',
}
