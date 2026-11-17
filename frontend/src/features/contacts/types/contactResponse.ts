import type { Schemas } from '@/core/api/generated'

export type ContactResponse = Schemas['ContactResponse']

/** What another record shows of a contact it links to. */
export type ContactSummaryResponse = Schemas['ContactSummaryResponse']

export type ContactOrganisationResponse = Schemas['ContactOrganisationResponse']

export type ContactOrganisationKind = ContactOrganisationResponse['kind']

export type SupplierMailRecipientsResponse = Schemas['SupplierMailRecipientsResponse']

export type ContactUsageResponse = Schemas['ContactUsageResponse']

export type ContactUsageRecordResponse = Schemas['ContactUsageRecordResponse']
