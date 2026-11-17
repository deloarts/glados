import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { Permission } from '@/core/auth/permissions'
import { mountWithApp } from '@/test-utils/mountWithApp'

const granted = new Set<string>()

vi.mock('@/core/composables/usePermissions', () => ({
  usePermissions: () => ({ hasPermission: (permission: string) => granted.has(permission) }),
}))

vi.mock('../../api/boughtItemsEdpApi', () => ({
  searchEdpParts: vi.fn<() => Promise<never[]>>().mockResolvedValue([]),
  getEdpPartPicture: vi.fn<() => Promise<Blob | null>>().mockResolvedValue(null),
}))

import BoughtItemEdpSearch from '../BoughtItemEdpSearch.vue'

function mountSearch() {
  setActivePinia(createPinia())
  return mountWithApp(BoughtItemEdpSearch)
}

function input(wrapper: ReturnType<typeof mountSearch>): HTMLInputElement {
  return wrapper.find<HTMLInputElement>('#bi-edp-search').element
}

describe('BoughtItemEdpSearch', () => {
  beforeEach(() => {
    granted.clear()
  })

  it('is enabled with the Data Portal permission', () => {
    granted.add(Permission.USE_DATA_PORTAL)

    const wrapper = mountSearch()

    expect(input(wrapper).disabled).toBe(false)
  })

  it('stays visible but disabled without the Data Portal permission', () => {
    granted.add(Permission.WRITE_BOUGHT_ITEMS)

    const wrapper = mountSearch()

    expect(wrapper.find('[data-testid="bought-item-edp-search-wrap"]').exists()).toBe(true)
    expect(input(wrapper).disabled).toBe(true)
  })
})
