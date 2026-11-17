import type { Schemas } from '@/core/api/generated'

export type AcknowledgementShowWhen = Schemas['AcknowledgementShowWhen']

/**
 * The list-item shape (also what create/PATCH return): table-backed, like
 * webhook subscriptions, but text/severity/recipients are immutable after
 * creation (a changed text would invalidate earlier confirmations), so
 * there is no update command beyond `enabled`, see setAcknowledgementEnabled.
 */
export type Acknowledgement = Schemas['AcknowledgementSummaryResult']

export type CreateAcknowledgementCommand = Schemas['CreateAcknowledgementRequest']

export type AcknowledgementRecipient = Schemas['AcknowledgementRecipientResult']
