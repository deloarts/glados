import { webApi } from '@/core/api/webRequest'

import type { Schemas } from '@/core/api/generated'

export type ProductContactResponse = Schemas['ProductContactResponse']

/** Every call answers the product's contacts as they are afterwards. */
export async function getProductContacts(productId: number): Promise<ProductContactResponse[]> {
  return webApi.get('/products/{product_id}/contacts', { path: { product_id: productId } })
}

export async function linkProductContact(
  productId: number,
  contactId: number,
  receivesMeetingNotes: boolean,
): Promise<ProductContactResponse[]> {
  return webApi.post('/products/{product_id}/contacts', {
    path: { product_id: productId },
    body: { contact_id: contactId, receives_meeting_notes: receivesMeetingNotes },
  })
}

export async function setProductContactMeetingNotes(
  productId: number,
  contactId: number,
  receivesMeetingNotes: boolean,
): Promise<ProductContactResponse[]> {
  return webApi.put('/products/{product_id}/contacts/{contact_id}', {
    path: { product_id: productId, contact_id: contactId },
    body: { receives_meeting_notes: receivesMeetingNotes },
  })
}

export async function unlinkProductContact(
  productId: number,
  contactId: number,
): Promise<ProductContactResponse[]> {
  return webApi.delete('/products/{product_id}/contacts/{contact_id}', {
    path: { product_id: productId, contact_id: contactId },
  })
}
