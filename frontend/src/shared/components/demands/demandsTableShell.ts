// Types of DemandsTableShell's props, kept outside the SFC because a generic
// script setup block cannot export them.
import type { PublicUser } from '@/core/types/userResponse'

/** The row fields the shell's own columns read. */
export interface DemandsTableRow {
  id: number
  desired_delivery_date?: string | null
  created: string
  creator: PublicUser | null
}

/** Already translated texts, so every i18n key stays in the kind's table. */
export interface DemandsTableShellLabels {
  desiredDelivery: string
  created: string
  dateFilterPlaceholder: string
  creatorPlaceholder: string
  bulkCancelHeader: string
  bulkCancelMessage: string
  bulkCancelAction: string
}
