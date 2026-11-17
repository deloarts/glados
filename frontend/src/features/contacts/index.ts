// Public barrel of the contacts feature. Other features import through here
// (enforced by eslint). Export only what other features consume.

export { contactDisplayName } from './utils/contactLabels'
export { flaggedSupplierRecipients } from './utils/supplierMailRecipients'
export type { SupplierMailKind } from './utils/supplierMailRecipients'

export type { ContactResponse, ContactSummaryResponse } from './types/contactResponse'

// The meeting attendee picker searches contacts and saves a guest as one.
export { createContact, getContacts } from './api/contactsApi'

export { default as ContactLinksSection } from './components/ContactLinksSection.vue'
export type { ContactLinksApi } from './components/ContactLinksSection.vue'
export type { LinkedContactRow } from './components/LinkedContactsTable.vue'
export { default as OrganisationContactsSection } from './components/OrganisationContactsSection.vue'
