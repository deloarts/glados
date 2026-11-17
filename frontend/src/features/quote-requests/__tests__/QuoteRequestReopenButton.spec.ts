import { describe, it, expect } from 'vitest'

import { mountWithApp } from '@/test-utils/mountWithApp'
import QuoteRequestReopenButton from '../components/QuoteRequestReopenButton.vue'
import type { QuoteRequestResponse } from '../types/quoteRequestsResponse'
import { makeLine, makeRequest } from './quoteRequestFixtures'

const VOIDED = makeLine({
  state: 'open',
  award_voided: true,
  awarded_supplier_id: 11,
  awarded_at: '2026-10-30T08:00:00Z',
})

function closedWithVoidedAward(overrides: Partial<QuoteRequestResponse> = {}): QuoteRequestResponse {
  return makeRequest({
    status: 'closed',
    closed_at: '2026-10-30T09:00:00Z',
    actions: ['reopen'],
    lines: [VOIDED, makeLine({ id: 2, state: 'dropped', dropped_at: '2026-10-30T09:00:00Z' })],
    ...overrides,
  })
}

function mountButton(request: QuoteRequestResponse, writeBlocked = '') {
  return mountWithApp(QuoteRequestReopenButton, { props: { request, writeBlocked } })
}

describe('QuoteRequestReopenButton', () => {
  it('reopens a closed request whose award was voided', async () => {
    const wrapper = mountButton(closedWithVoidedAward())

    const button = wrapper.find('[data-testid="reopen-request"]')
    expect(button.text()).toBe('Reopen')
    expect(button.attributes('disabled')).toBeUndefined()
    await button.trigger('click')

    expect(wrapper.emitted('reopen')).toHaveLength(1)
  })

  it('stays visible but disabled with the missing permission as its tooltip', async () => {
    const reason = 'You need the permission to change orders.'
    const wrapper = mountButton(closedWithVoidedAward({ actions: [] }), reason)

    const button = wrapper.find('[data-testid="reopen-request"]')
    expect(button.exists()).toBe(true)
    expect(button.attributes('disabled')).toBeDefined()
    expect(tooltipOf(button)).toBe(reason)
    await button.trigger('click')
    expect(wrapper.emitted('reopen')).toBeUndefined()
  })

  it.each([
    ['an open request', makeRequest({ lines: [VOIDED] })],
    ['a request closed with no voided line', closedWithVoidedAward({ actions: [], lines: [makeLine({ state: 'awarded', awarded_at: '2026-10-30T08:00:00Z' })] })],
    ['a request closed only by dropping every line', closedWithVoidedAward({ closed_at: null })],
    ['a canceled request', closedWithVoidedAward({ status: 'canceled', canceled_at: '2026-10-30T10:00:00Z', actions: [] })],
    ['a request whose voided line was dropped', closedWithVoidedAward({ actions: [], lines: [{ ...VOIDED, state: 'dropped', dropped_at: '2026-10-30T09:00:00Z' }] })],
  ])('is not offered on %s', (_name, request) => {
    const wrapper = mountButton(request)

    expect(wrapper.find('[data-testid="reopen-request"]').exists()).toBe(false)
  })
})

/** The tooltip of a button, kept by OpenVue's Tooltip directive on the span around it. */
function tooltipOf(button: { element: Element }): string | undefined {
  return (button.element.parentElement as (HTMLElement & { $_ptooltipValue?: string }) | null)?.$_ptooltipValue
}
