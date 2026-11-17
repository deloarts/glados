import { describe, it, expect, vi, afterEach } from 'vitest'
import { flushPromises, type VueWrapper } from '@vue/test-utils'

import { mountWithApp } from '@/test-utils/mountWithApp'

import DemandFulfillFromStockDialog from '../DemandFulfillFromStockDialog.vue'
import type {
  FulfillFromStockDemand,
  FulfillFromStockOperations,
  FulfillFromStockResult,
  FulfillFromStockSummary,
} from '../DemandFulfillFromStockDialog.vue'

interface TestDemand extends FulfillFromStockDemand {
  id: number
  unit: string
  item_article_name?: string
}

interface TestSummary extends FulfillFromStockSummary {
  unallocated: number
  unit: string
}

interface TestResult extends FulfillFromStockResult {
  quantity_fulfilled: number
}

function makeDemand(overrides: Partial<TestDemand> = {}): TestDemand {
  return {
    id: 1,
    unit: 'PCS',
    item_article_name: 'Hex Bolt',
    ...overrides,
  }
}

function makeSummary(overrides: Partial<TestSummary> = {}): TestSummary {
  return {
    unallocated: 10,
    unit: 'PCS',
    ...overrides,
  }
}

function makeOperations(
  overrides: Partial<FulfillFromStockOperations<TestSummary, TestResult>> = {},
): FulfillFromStockOperations<TestSummary, TestResult> {
  return {
    getSummary: vi.fn<(demandId: number) => TestSummary | undefined>().mockReturnValue(undefined),
    fetchSummaries: vi.fn<(demandIds: number[]) => Promise<void>>().mockResolvedValue(undefined),
    fulfillFromStock: vi
      .fn<(demandId: number, quantity: number) => Promise<TestResult>>()
      .mockResolvedValue({ quantity_fulfilled: 5 }),
    ...overrides,
  }
}

const mounted: VueWrapper[] = []

async function mountDialog(props: {
  demand: TestDemand | null
  operations: FulfillFromStockOperations<TestSummary, TestResult>
  formatUnit?: (unit: string) => string
}) {
  const wrapper = mountWithApp(DemandFulfillFromStockDialog, {
    attachTo: document.body,
    props: {
      visible: false,
      demand: props.demand,
      operations: props.operations,
      i18nPrefix: 'boughtItems.demands',
      formatUnit: props.formatUnit ?? ((unit: string) => unit),
    },
  })
  mounted.push(wrapper)
  await wrapper.setProps({ visible: true })
  await flushPromises()
  return wrapper
}

function quantityInput(wrapper: VueWrapper) {
  return wrapper.findComponent({ name: 'InputNumber' })
}

function submitButton(wrapper: VueWrapper) {
  return wrapper
    .findAllComponents({ name: 'Button' })
    .find((b) => b.props('label') === 'Fulfill from Stock')!
}

function closeButton(wrapper: VueWrapper) {
  return wrapper.findAllComponents({ name: 'Button' }).find((b) => b.props('label') === 'Close')!
}

describe('DemandFulfillFromStockDialog', () => {
  afterEach(() => {
    mounted.splice(0).forEach((wrapper) => wrapper.unmount())
  })

  it('shows the item name in the header when the demand carries item_article_name', async () => {
    await mountDialog({
      demand: makeDemand({ item_article_name: 'Hex Bolt' }),
      operations: makeOperations(),
    })

    expect(document.body.textContent).toContain('Fulfill from Stock, Hex Bolt')
  })

  it('omits the item name from the header when item_article_name is absent', async () => {
    await mountDialog({
      demand: makeDemand({ item_article_name: undefined }),
      operations: makeOperations(),
    })

    expect(document.body.textContent).not.toContain('Fulfill from Stock, ')
  })

  it('fetches the summary on open when none is cached yet', async () => {
    const operations = makeOperations()
    const demand = makeDemand({ id: 42 })
    await mountDialog({ demand, operations })

    expect(operations.fetchSummaries).toHaveBeenCalledWith([42])
  })

  it('does not re-fetch when a summary is already cached', async () => {
    const summary = makeSummary()
    const operations = makeOperations({
      getSummary: vi.fn<(demandId: number) => TestSummary | undefined>().mockReturnValue(summary),
    })
    await mountDialog({ demand: makeDemand(), operations })

    expect(operations.fetchSummaries).not.toHaveBeenCalled()
  })

  it('shows the unallocated hint through the formatUnit prop', async () => {
    const summary = makeSummary({ unallocated: 7, unit: 'PCS' })
    const operations = makeOperations({
      getSummary: vi.fn<(demandId: number) => TestSummary | undefined>().mockReturnValue(summary),
    })
    await mountDialog({
      demand: makeDemand(),
      operations,
      formatUnit: (unit) => `unit:${unit}`,
    })

    expect(document.body.textContent).toContain('7')
    expect(document.body.textContent).toContain('unit:PCS')
  })

  it('disables submit until a positive quantity is entered', async () => {
    const wrapper = await mountDialog({ demand: makeDemand(), operations: makeOperations() })

    // Button has no declared `disabled` prop, it derives disabled-ness from
    // $attrs.disabled at render time, so this asserts the rendered DOM
    // attribute rather than a component prop.
    expect(submitButton(wrapper).attributes('disabled')).toBeDefined()

    await quantityInput(wrapper).vm.$emit('update:modelValue', 3)

    expect(submitButton(wrapper).attributes('disabled')).toBeUndefined()
  })

  it('prefills the whole unallocated quantity', async () => {
    const operations = makeOperations({
      getSummary: vi
        .fn<(demandId: number) => TestSummary | undefined>()
        .mockReturnValue(makeSummary({ unallocated: 5 })),
    })
    const wrapper = await mountDialog({ demand: makeDemand(), operations })

    expect(quantityInput(wrapper).props('modelValue')).toBe(5)
    expect(submitButton(wrapper).attributes('disabled')).toBeUndefined()
  })

  it('disables submit once the quantity exceeds the unallocated amount', async () => {
    const summary = makeSummary({ unallocated: 5 })
    const operations = makeOperations({
      getSummary: vi.fn<(demandId: number) => TestSummary | undefined>().mockReturnValue(summary),
    })
    const wrapper = await mountDialog({ demand: makeDemand(), operations })

    await quantityInput(wrapper).vm.$emit('update:modelValue', 6)

    expect(submitButton(wrapper).attributes('disabled')).toBeDefined()
  })

  it('submits the fulfillment, shows the success message, and emits fulfilled', async () => {
    const summary = makeSummary({ unallocated: 10, unit: 'PCS' })
    const operations = makeOperations({
      getSummary: vi.fn<(demandId: number) => TestSummary | undefined>().mockReturnValue(summary),
      fulfillFromStock: vi
        .fn<(demandId: number, quantity: number) => Promise<TestResult>>()
        .mockResolvedValue({ quantity_fulfilled: 4 }),
    })
    const wrapper = await mountDialog({ demand: makeDemand({ id: 9 }), operations })

    await quantityInput(wrapper).vm.$emit('update:modelValue', 4)
    await submitButton(wrapper).trigger('click')
    await flushPromises()

    expect(operations.fulfillFromStock).toHaveBeenCalledWith(9, 4)
    expect(document.body.textContent).toContain('Fulfilled 4 PCS from stock.')
    expect(wrapper.emitted('fulfilled')).toHaveLength(1)
  })

  it('shows the extracted API error message on failure', async () => {
    const operations = makeOperations({
      fulfillFromStock: vi
        .fn<(demandId: number, quantity: number) => Promise<TestResult>>()
        .mockRejectedValue({
          isAxiosError: true,
          response: { data: { detail: 'Not enough stock.' } },
        }),
    })
    const wrapper = await mountDialog({ demand: makeDemand(), operations })

    await quantityInput(wrapper).vm.$emit('update:modelValue', 2)
    await submitButton(wrapper).trigger('click')
    await flushPromises()

    expect(document.body.textContent).toContain('Not enough stock.')
  })

  it('falls back to the generic error message when the failure is not an API error', async () => {
    const operations = makeOperations({
      fulfillFromStock: vi
        .fn<(demandId: number, quantity: number) => Promise<TestResult>>()
        .mockRejectedValue(new Error('boom')),
    })
    const wrapper = await mountDialog({ demand: makeDemand(), operations })

    await quantityInput(wrapper).vm.$emit('update:modelValue', 2)
    await submitButton(wrapper).trigger('click')
    await flushPromises()

    expect(document.body.textContent).toContain('Something went wrong. Please try again.')
  })

  it('closes the dialog on the close button', async () => {
    const wrapper = await mountDialog({ demand: makeDemand(), operations: makeOperations() })

    await closeButton(wrapper).trigger('click')

    expect(wrapper.emitted('update:visible')?.at(-1)).toEqual([false])
  })
})
