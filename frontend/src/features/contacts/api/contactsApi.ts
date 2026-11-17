import { webApi } from '@/core/api/webRequest'

import type { PageResponse } from '@/core/api/types'
import type {
  ContactCreateRequest,
  ContactFilterParams,
  ContactUpdateRequest,
} from '../types/contactRequest'
import type {
  ContactResponse,
  ContactUsageResponse,
  SupplierMailRecipientsResponse,
} from '../types/contactResponse'

export async function getContacts(
  params?: ContactFilterParams,
): Promise<PageResponse<ContactResponse>> {
  return webApi.get('/contacts/', { query: params })
}

export async function getContact(contactId: number): Promise<ContactResponse> {
  return webApi.get('/contacts/{contact_id}', { path: { contact_id: contactId } })
}

export async function createContact(body: ContactCreateRequest): Promise<ContactResponse> {
  return webApi.post('/contacts/', { body })
}

export async function updateContact(
  contactId: number,
  body: ContactUpdateRequest,
): Promise<ContactResponse> {
  return webApi.put('/contacts/{contact_id}', { path: { contact_id: contactId }, body })
}

export async function archiveContact(contactId: number): Promise<ContactResponse> {
  return webApi.post('/contacts/{contact_id}/archive', { path: { contact_id: contactId } })
}

export async function restoreContact(contactId: number): Promise<ContactResponse> {
  return webApi.post('/contacts/{contact_id}/restore', { path: { contact_id: contactId } })
}

/** Blanks the contact's personal data and archives it, for good. */
export async function anonymiseContact(contactId: number): Promise<ContactResponse> {
  return webApi.post('/contacts/{contact_id}/anonymise', { path: { contact_id: contactId } })
}

/** The supplier's contacts flagged for its request mails and its order mails. */
export async function getSupplierMailRecipients(
  supplierId: number,
): Promise<SupplierMailRecipientsResponse> {
  return webApi.get('/suppliers/{supplier_id}/mail-recipients', {
    path: { supplier_id: supplierId },
  })
}

/** The products and projects that link each contact, one entry per id asked for. */
export async function getContactUsage(contactIds: number[]): Promise<ContactUsageResponse[]> {
  if (contactIds.length === 0) return []
  return webApi.get('/contact-usage/', { query: { contact_ids: contactIds } })
}
