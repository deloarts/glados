import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { i18n } from '@/core/i18n'

import type { CustomerResponse } from '../../types/customerResponse'

const getMock = vi.fn<(url: string, config?: unknown) => Promise<{ data: unknown }>>()

vi.mock('@/core/api', () => ({
  default: {
    get: (url: string, config?: unknown) => getMock(url, config),
  },
}))

import CustomerSelect from '../CustomerSelect.vue'

function makeCustomer(overrides: Partial<CustomerResponse> = {}): CustomerResponse {
  return {
    edit_version: 0,
    id: 1,
    public_id: '11111111-1111-1111-1111-111111111111',
    created: '2026-01-01',
    changed: null,
    changed_by_id: null,
    changed_by: null,
    archived: false,
    name: 'Acme Corp',
    legal_name: null,
    vat_id: null,
    level: 'A',
    street: 'Main St 1',
    city: 'Vienna',
    country: 'AT',
    postal_code: '1010',
    email: null,
    phone: null,
    weblink: null,
    creator_id: 1,
    creator: null,
    ...overrides,
  }
}

describe('CustomerSelect', () => {
  beforeEach(() => {
    getMock.mockReset()
  })

  it('requests archived customers alongside live ones on the initial search', async () => {
    getMock.mockResolvedValue({ data: { items: [], total: 0, limit: 50, skip: 0 } })

    mountWithApp(CustomerSelect)
    await flushPromises()

    expect(getMock).toHaveBeenCalledWith('/customers/', {
      params: { limit: 50, include_archived: true },
    })
  })

  it('lists archived customers after live ones, each carrying the Archived tag', async () => {
    getMock.mockResolvedValue({
      data: {
        items: [
          makeCustomer({ id: 1, name: 'Archived Co', archived: true }),
          makeCustomer({ id: 2, name: 'Live Co', archived: false }),
        ],
        total: 2,
        limit: 50,
        skip: 0,
      },
    })

    const wrapper = mountWithApp(CustomerSelect)
    await flushPromises()

    const select = wrapper.findComponent({ name: 'Select' })
    const options = select.props('options') as CustomerResponse[]

    expect(options.map((o) => o.name)).toEqual(['Live Co', 'Archived Co'])
  })

  it('renders the Archived tag and a warning line when the current value is archived', async () => {
    getMock.mockResolvedValue({ data: { items: [], total: 0, limit: 50, skip: 0 } })

    const wrapper = mountWithApp(CustomerSelect, {
      props: { modelValue: makeCustomer({ archived: true }) },
    })
    await flushPromises()

    expect(wrapper.findComponent({ name: 'Tag' }).exists()).toBe(true)
    expect(wrapper.text()).toContain(i18n.global.t('common.archivedSelectionWarning'))
  })

  it('shows neither the tag nor the warning for a live current value', async () => {
    getMock.mockResolvedValue({ data: { items: [], total: 0, limit: 50, skip: 0 } })

    const wrapper = mountWithApp(CustomerSelect, {
      props: { modelValue: makeCustomer({ archived: false }) },
    })
    await flushPromises()

    expect(wrapper.findComponent({ name: 'Tag' }).exists()).toBe(false)
    expect(wrapper.text()).not.toContain(i18n.global.t('common.archivedSelectionWarning'))
  })
})
