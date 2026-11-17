import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ConfirmationService from 'openvue/confirmationservice'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { i18n } from '@/core/i18n'
import { createTokenStore } from '../../../stores/createTokenStore'

import type { TokenApi } from '../../../api/createTokenApi'
import type { TokenFilterParams, TokenSummary } from '../../../types/tokenTypes'
import type { PageResponse } from '@/core/api/types'

import TokenManagementTable from '../TokenManagementTable.vue'

function makeApi(): TokenApi {
  return {
    list: vi
      .fn<(params?: TokenFilterParams) => Promise<PageResponse<TokenSummary>>>()
      .mockResolvedValue({ items: [], total: 0, limit: 25, skip: 0 }),
    create: vi.fn<() => Promise<never>>(),
    revoke: vi.fn<() => Promise<never>>(),
    revokeAll: vi.fn<() => Promise<never>>(),
    getUsageLog: vi.fn<() => Promise<never>>(),
  }
}

async function mountTable(api: TokenApi, i18nPrefix = 'account.pat') {
  const pinia = createPinia()
  setActivePinia(pinia)
  const store = createTokenStore(`tokenTableFilters-${Math.random()}`, api)()
  const wrapper = mountWithApp(TokenManagementTable, {
    pinia,
    props: { store, api, canManage: true, i18nPrefix },
    global: { plugins: [ConfirmationService] },
  })
  await flushPromises()
  return { wrapper, store }
}

describe('TokenManagementTable row filters', () => {
  let api: TokenApi

  beforeEach(() => {
    vi.useRealTimers()
    api = makeApi()
  })

  it('refetches at once with the picked expiry state', async () => {
    const { wrapper } = await mountTable(api)
    vi.mocked(api.list).mockClear()

    await wrapper.findComponent({ name: 'Select' }).vm.$emit('update:modelValue', 'never')
    await flushPromises()

    expect(api.list).toHaveBeenCalledWith({ skip: 0, limit: 25, expiry: 'never' })
  })

  it('debounces the typed name filter into the search param', async () => {
    vi.useFakeTimers()
    const { wrapper } = await mountTable(api)
    vi.mocked(api.list).mockClear()

    const label = i18n.global.t('common.filterBy', { column: i18n.global.t('account.pat.columns.name') })
    await wrapper.find(`input[aria-label="${label}"]`).setValue('deploy')
    expect(api.list).not.toHaveBeenCalled()

    await vi.runAllTimersAsync()

    expect(api.list).toHaveBeenCalledWith({ skip: 0, limit: 25, search: 'deploy' })
    vi.useRealTimers()
  })

  it('labels the expiry options for both token kinds', async () => {
    for (const prefix of ['account.pat', 'settings.apiKeys']) {
      const { wrapper } = await mountTable(makeApi(), prefix)
      const labels = (wrapper.findComponent({ name: 'Select' }).props('options') as { label: string }[]).map(
        (option) => option.label,
      )
      expect(labels).toEqual([
        i18n.global.t(`${prefix}.neverExpires`),
        i18n.global.t(`${prefix}.expired`),
        i18n.global.t(`${prefix}.filters.notExpired`),
      ])
      expect(labels[2]).not.toContain('filters.')
      wrapper.unmount()
    }
  })
})
