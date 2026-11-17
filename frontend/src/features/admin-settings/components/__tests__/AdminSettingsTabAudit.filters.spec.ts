import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { i18n } from '@/core/i18n'

import type { PageResponse } from '@/core/api/types'
import type { SettingsAuditParams } from '../../api/getSettingsAudit'
import type { AdminSettingsAuditEntry } from '../../types/adminSettingsTypes'

const getSettingsAuditMock =
  vi.fn<(params?: SettingsAuditParams) => Promise<PageResponse<AdminSettingsAuditEntry>>>()

vi.mock('../../api/getSettingsAudit', () => ({
  getSettingsAudit: (params?: SettingsAuditParams) => getSettingsAuditMock(params),
}))

import AdminSettingsTabAudit from '../AdminSettingsTabAudit.vue'

function filterInput(wrapper: ReturnType<typeof mountWithApp>, column: string) {
  return wrapper.find(`input[aria-label="${i18n.global.t('common.filterBy', { column })}"]`)
}

describe('AdminSettingsTabAudit row filters', () => {
  beforeEach(() => {
    vi.useRealTimers()
    getSettingsAuditMock.mockReset()
    getSettingsAuditMock.mockResolvedValue({ items: [], total: 0, limit: 25, skip: 0 })
  })

  it('renders a row filter on every column and loads the first page unfiltered', async () => {
    const wrapper = mountWithApp(AdminSettingsTabAudit)
    await flushPromises()

    expect(wrapper.findComponent({ name: 'DataTable' }).props('filterDisplay')).toBe('row')
    expect(filterInput(wrapper, 'Changed At').exists()).toBe(true)
    expect(filterInput(wrapper, 'Summary').exists()).toBe(true)
    expect(wrapper.findComponent({ name: 'Select' }).exists()).toBe(true)
    expect(wrapper.findComponent({ name: 'UserDateFilter' }).exists()).toBe(true)
    expect(getSettingsAuditMock).toHaveBeenCalledWith({ skip: 0, limit: 25 })
  })

  it('refetches at once with the picked domain', async () => {
    const wrapper = mountWithApp(AdminSettingsTabAudit)
    await flushPromises()
    getSettingsAuditMock.mockClear()

    await wrapper.findComponent({ name: 'Select' }).vm.$emit('update:modelValue', 'mail')
    await flushPromises()

    expect(getSettingsAuditMock).toHaveBeenCalledWith({ skip: 0, limit: 25, settings_domain: 'mail' })
  })

  it('filters at once by the id of the person picked in the changed column', async () => {
    const wrapper = mountWithApp(AdminSettingsTabAudit)
    await flushPromises()
    getSettingsAuditMock.mockClear()

    await wrapper.findComponent({ name: 'UserDateFilter' }).vm.$emit('update:userId', 5)
    await flushPromises()

    expect(getSettingsAuditMock).toHaveBeenCalledWith({ skip: 0, limit: 25, changed_by_id: 5 })
  })
})
