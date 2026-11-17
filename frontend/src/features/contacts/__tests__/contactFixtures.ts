import type { ContactResponse, ContactSummaryResponse } from '../types/contactResponse'

export function makeContact(overrides: Partial<ContactResponse> = {}): ContactResponse {
  return {
    id: 7,
    public_id: '77777777-7777-7777-7777-777777777777',
    created: '2026-11-10T08:00:00Z',
    changed: null,
    archived: false,
    anonymised_at: null,
    name: 'Karin Hypothetical',
    role: 'Sales',
    email: 'k.hypothetical@pneumatik.example',
    phone: '+43 000 123 45',
    mobile: null,
    note: null,
    customer_id: null,
    supplier_id: 3,
    organisation: { kind: 'supplier', id: 3, name: 'Pneumatik Hypothetical', archived: false },
    receives_request_mails: true,
    receives_order_mails: false,
    creator_id: 1,
    creator: null,
    changed_by_id: null,
    changed_by: null,
    edit_version: 2,
    ...overrides,
  }
}

export function makeSummary(overrides: Partial<ContactSummaryResponse> = {}): ContactSummaryResponse {
  return {
    id: 7,
    public_id: '77777777-7777-7777-7777-777777777777',
    name: 'Thomas Muster',
    role: 'Project lead',
    email: 't.muster@muster.example',
    phone: null,
    mobile: null,
    archived: false,
    anonymised: false,
    organisation: { kind: 'customer', id: 2, name: 'Muster Anlagenbau', archived: false },
    ...overrides,
  }
}
