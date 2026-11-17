import { describe, it, expect, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { useHostStore } from '@/core/host/stores/hostStore'
import { useProductionPlanning } from '../useProductionPlanning'

describe('useProductionPlanning', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('defaults to enabled before /host/capabilities has answered', () => {
    const { productionPlanningEnabled } = useProductionPlanning()

    expect(productionPlanningEnabled.value).toBe(true)
  })

  it('reflects the host store once the capability flag is off', () => {
    useHostStore().productionPlanningEnabled = false

    const { productionPlanningEnabled } = useProductionPlanning()

    expect(productionPlanningEnabled.value).toBe(false)
  })

  it('stays in sync with the host store after creation', () => {
    const host = useHostStore()
    const { productionPlanningEnabled } = useProductionPlanning()
    expect(productionPlanningEnabled.value).toBe(true)

    host.productionPlanningEnabled = false
    expect(productionPlanningEnabled.value).toBe(false)

    host.productionPlanningEnabled = true
    expect(productionPlanningEnabled.value).toBe(true)
  })
})
