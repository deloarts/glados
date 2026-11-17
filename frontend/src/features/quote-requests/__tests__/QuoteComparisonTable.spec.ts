import { describe, it, expect } from 'vitest'

import { mountWithApp } from '@/test-utils/mountWithApp'
import QuoteComparisonTable from '../components/QuoteComparisonTable.vue'
import { makeLine, makeRequest, makeRow, makeQuote } from './quoteRequestFixtures'

function mountTable(request = makeRequest(), selection = new Map<number, number>()) {
  return mountWithApp(QuoteComparisonTable, {
    props: {
      request,
      writeBlocked: '',
      sendBlocked: '',
      selection,
      'onUpdate:selection': () => {},
    },
  })
}

describe('QuoteComparisonTable', () => {
  it('chooses a supplier for a line by clicking its offer', async () => {
    const request = makeRequest({
      lines: [makeLine({ cheapest_supplier_id: 12 })],
      suppliers: [
        makeRow({ id: 11, quotes: [makeQuote({ line_id: 1, unit_price: 300, lead_time_days: 5 })] }),
        makeRow({ id: 12, supplier_name: 'Bolt', quotes: [makeQuote({ line_id: 1, unit_price: 250 })] }),
      ],
    })
    const wrapper = mountTable(request)

    await wrapper.find('[data-testid="offer-1-12"]').trigger('click')

    const emitted = wrapper.emitted('update:selection') as Map<number, number>[][]
    expect(emitted.at(-1)?.[0]?.get(1)).toBe(12)
    expect(wrapper.find('[data-testid="offer-1-12"]').classes()).toContain('cheapest')
  })

  it('does not choose a supplier that made no offer, and shows lines not asked yet', async () => {
    const request = makeRequest({
      suppliers: [
        makeRow({
          not_asked_line_ids: [1],
          quotes: [makeQuote({ line_id: 1, no_offer: true })],
        }),
      ],
    })
    const wrapper = mountTable(request)

    await wrapper.find('[data-testid="offer-1-11"]').trigger('click')

    expect(wrapper.emitted('update:selection')).toBeUndefined()
    expect(wrapper.text()).toContain('No offer')
    expect(wrapper.text()).toContain('Not asked yet')
  })

  it('lets nothing be chosen on a request that is no longer open', async () => {
    const wrapper = mountTable(makeRequest({ status: 'awarded' }))

    await wrapper.find('[data-testid="offer-1-11"]').trigger('click')

    expect(wrapper.emitted('update:selection')).toBeUndefined()
  })

  it('shows a supplier\'s alternative item and lets a bought line be substituted', async () => {
    const request = makeRequest({
      suppliers: [
        makeRow({
          quotes: [
            makeQuote({
              line_id: 1,
              unit_price: 90,
              substitute_bought_item_id: 8,
              substitute_item_name: 'Screw M6 A2',
              substitute_reason: 'Discontinued.',
            }),
          ],
        }),
      ],
    })
    const wrapper = mountTable(request)

    expect(wrapper.find('[data-testid="offer-alternative"]').text()).toContain('Screw M6 A2')
    await wrapper.find('[data-testid="substitute-line"]').trigger('click')

    expect(wrapper.emitted('substitute-line')?.[0]?.[0]).toMatchObject({ id: 1 })
  })

  it('offers no substitute for a lot position line, and marks a replaced line', () => {
    const request = makeRequest({
      lines: [
        makeLine({ line_type: 'MADE', bought_item_id: null, lot_position_id: 4 }),
        makeLine({ id: 2, position: 2, state: 'dropped', substituted_by_line_id: 3 }),
        makeLine({ id: 3, position: 3, substitute_reason: 'Stainless.' }),
      ],
    })
    const wrapper = mountTable(request)

    const [madeSubstitute] = wrapper.findAll('[data-testid="substitute-line"]')
    expect(madeSubstitute?.attributes('disabled')).toBeDefined()
    expect(wrapper.text()).toContain('Replaced by line 3')
    expect(wrapper.text()).toContain('Stainless.')
  })

  it('takes a dropped line back while the request is closed only by dropping every line', async () => {
    const request = makeRequest({
      status: 'closed',
      closed_at: null,
      lines: [makeLine({ state: 'dropped', dropped_at: '2026-10-30T08:00:00Z' })],
    })
    const wrapper = mountTable(request)

    const restore = wrapper.find('[data-testid="restore-line"]')
    expect(restore.attributes('disabled')).toBeUndefined()
    await restore.trigger('click')

    expect(wrapper.emitted('restore-line')).toHaveLength(1)
  })

  it('takes back a line dropped by mistake on a request that reads awarded', async () => {
    const request = makeRequest({
      status: 'awarded',
      closed_at: null,
      lines: [
        makeLine({ state: 'awarded', awarded_supplier_id: 11, awarded_at: '2026-10-30T08:00:00Z' }),
        makeLine({ id: 2, position: 2, state: 'dropped', dropped_at: '2026-10-30T07:00:00Z' }),
      ],
    })
    const wrapper = mountTable(request)

    const restore = wrapper.find('[data-testid="restore-line"]')
    expect(restore.attributes('disabled')).toBeUndefined()
  })

  it('names why a line of a request closed on purpose is not taken back', () => {
    const request = makeRequest({
      status: 'closed',
      closed_at: '2026-10-30T09:00:00Z',
      lines: [makeLine({ state: 'dropped', dropped_at: '2026-10-30T08:00:00Z' })],
    })
    const wrapper = mountTable(request)

    const restore = wrapper.find('[data-testid="restore-line"]')
    expect(restore.attributes('disabled')).toBeDefined()
    expect(tooltipOf(restore)).toBe('The request was closed on purpose and takes no line back.')
  })

  it('points to Reopen for a dropped line of a closed request whose award was voided', () => {
    const request = makeRequest({
      status: 'closed',
      closed_at: '2026-10-30T09:00:00Z',
      lines: [
        makeLine({ state: 'open', award_voided: true, awarded_supplier_id: 11, awarded_at: '2026-10-30T08:00:00Z' }),
        makeLine({ id: 2, position: 2, state: 'dropped', dropped_at: '2026-10-30T09:00:00Z' }),
      ],
    })
    const wrapper = mountTable(request)

    const restore = wrapper.find('[data-testid="restore-line"]')
    expect(restore.attributes('disabled')).toBeDefined()
    expect(tooltipOf(restore)).toBe(
      'An award on this request was voided. Reopen the request to take a line back.',
    )
  })

  it('names the request state on the actions it disables', () => {
    const wrapper = mountTable(makeRequest({ status: 'canceled' }))

    const enterOffer = wrapper.find('[data-testid="enter-offer"]')
    expect(enterOffer.attributes('disabled')).toBeDefined()
    expect(tooltipOf(enterOffer)).toBe('The request is canceled and takes no more changes.')
  })

  it('marks a voided award and no longer shows its supplier as the winner', () => {
    const request = makeRequest({
      lines: [
        makeLine({
          state: 'open',
          award_voided: true,
          awarded_supplier_id: 11,
          awarded_at: '2026-10-30T08:00:00Z',
          order_id: 4,
          order_number: 'BN-26-00004',
        }),
      ],
    })
    const wrapper = mountTable(request)

    expect(wrapper.find('[data-testid="award-voided"]').text()).toBe(
      'Award to Acme voided: order BN-26-00004 was canceled.',
    )
    expect(wrapper.find('[data-testid="offer-1-11"]').classes()).not.toContain('winner')
  })
})

/** The tooltip of a button, kept by OpenVue's Tooltip directive on the span around it. */
function tooltipOf(button: { element: Element }): string | undefined {
  return (button.element.parentElement as (HTMLElement & { $_ptooltipValue?: string }) | null)?.$_ptooltipValue
}
