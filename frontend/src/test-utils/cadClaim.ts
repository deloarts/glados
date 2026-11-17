import { flushPromises } from '@vue/test-utils'

import { i18n } from '@/core/i18n'

function cadClaimButtons(): HTMLButtonElement[] {
  return Array.from(
    document.querySelectorAll<HTMLButtonElement>('[data-testid="cad-claim-dialog"] button'),
  )
}

/** Whether the CAD claim warning a catalogue form shows is open. */
export function cadClaimOpen(): boolean {
  return cadClaimButtons().length > 0
}

/** The CAD claim warning's text, or an empty string while it is closed. */
export function cadClaimText(): string {
  return document.querySelector('[data-testid="cad-claim-dialog"]')?.textContent ?? ''
}

/**
 * Answers the CAD claim warning a catalogue form shows before a PDM-claimed
 * item is edited, when it is open. Tests about the form itself pass it.
 */
export async function answerCadClaim(proceed = true): Promise<void> {
  const label = proceed ? i18n.global.t('catalogue.cadClaim.continue') : i18n.global.t('common.cancel')
  cadClaimButtons()
    .find((button) => button.textContent?.trim() === label)
    ?.click()
  await flushPromises()
  await flushPromises()
}
