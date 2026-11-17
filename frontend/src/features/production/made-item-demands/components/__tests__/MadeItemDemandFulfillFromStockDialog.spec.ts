import { describe, it, expect } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import type { VueWrapper } from '@vue/test-utils'
import type { ComponentPublicInstance } from 'vue'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { makeMadeItemDemandResponse } from '@/test-utils/factories'

import MadeItemDemandFulfillFromStockDialog from '../MadeItemDemandFulfillFromStockDialog.vue'
import SharedFulfillFromStockDialog from '@/shared/components/demands/DemandFulfillFromStockDialog.vue'
import type {
  FulfillFromStockOperations,
  FulfillFromStockResult,
  FulfillFromStockSummary,
} from '@/shared/components/demands/DemandFulfillFromStockDialog.vue'
import { useMadeItemsAllocationsStore } from '../../stores/madeItemsAllocationsStore'
import type { MadeItemDemandResponse } from '@/features/made-items'


// DemandFulfillFromStockDialog is a generic component (`generic="TDemand,
// TSummary, TResult"`), so Vue Test Utils cannot infer its instance type from
// `findComponent(SharedFulfillFromStockDialog)` alone and falls back to a
// plain DOMWrapper. Cast the lookup to the instance shape it actually
// renders with here. The summary/result generics aren't exercised by this
// wrapper-forwarding smoke test, so the base interfaces stand in for them.
type SharedFulfillFromStockDialogInstance = ComponentPublicInstance<{
  demand: MadeItemDemandResponse | null
  operations: FulfillFromStockOperations<FulfillFromStockSummary, FulfillFromStockResult>
  i18nPrefix: string
  formatUnit: (unit: string) => string
}>

describe('made-items MadeItemDemandFulfillFromStockDialog (wrapper)', () => {
  it('renders the shared dialog with the made-items allocations store and i18n prefix', () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const demand = makeMadeItemDemandResponse()
    const wrapper = mountWithApp(MadeItemDemandFulfillFromStockDialog, {
      pinia,
      props: { visible: true, demand },
    })

    const shared = wrapper.findComponent(SharedFulfillFromStockDialog) as unknown as VueWrapper<
      SharedFulfillFromStockDialogInstance
    >
    expect(shared.exists()).toBe(true)
    expect(shared.props('demand')).toEqual(demand)
    expect(shared.props('i18nPrefix')).toBe('madeItems.demands')
    expect(shared.props('formatUnit')('PCS')).toBe('pcs')
    expect(shared.props('operations')).toBe(useMadeItemsAllocationsStore())

    wrapper.unmount()
  })

  it('forwards the fulfilled event from the shared dialog', async () => {
    const wrapper = mountWithApp(MadeItemDemandFulfillFromStockDialog, {
      props: { visible: true, demand: makeMadeItemDemandResponse() },
    })

    const shared = wrapper.findComponent(SharedFulfillFromStockDialog) as unknown as VueWrapper<
      SharedFulfillFromStockDialogInstance
    >
    await shared.vm.$emit('fulfilled')

    expect(wrapper.emitted('fulfilled')).toHaveLength(1)

    wrapper.unmount()
  })
})
