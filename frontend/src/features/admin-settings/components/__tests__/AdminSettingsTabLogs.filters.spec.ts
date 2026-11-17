import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { i18n } from '@/core/i18n'

import type { LogEntriesResponse, LogFilterParams } from '../../types/adminSettingsTypes'

const getLogsMock = vi.fn<(params?: LogFilterParams) => Promise<LogEntriesResponse>>()

vi.mock('../../api/getLogs', () => ({
  getLogs: (params?: LogFilterParams) => getLogsMock(params),
}))

import AdminSettingsTabLogs from '../AdminSettingsTabLogs.vue'

const t = i18n.global.t

function filterInput(wrapper: ReturnType<typeof mountWithApp>, columnKey: string) {
  const column = t(`settings.logs.columns.${columnKey}`)
  return wrapper.find(`input[aria-label="${t('common.filterBy', { column })}"]`)
}

describe('AdminSettingsTabLogs column filters', () => {
  beforeEach(() => {
    vi.useRealTimers()
    getLogsMock.mockReset()
    getLogsMock.mockResolvedValue({ items: [], total: 0 })
  })

  it('sends the typed username as username_contains', async () => {
    vi.useFakeTimers()
    const wrapper = mountWithApp(AdminSettingsTabLogs)
    await flushPromises()
    getLogsMock.mockClear()

    await filterInput(wrapper, 'username').setValue('zoe')
    await vi.runAllTimersAsync()

    expect(getLogsMock).toHaveBeenLastCalledWith(
      expect.objectContaining({ username_contains: 'zoe' }),
    )
    vi.useRealTimers()
  })

  it('sends a typed status code as a number and ignores anything else', async () => {
    vi.useFakeTimers()
    const wrapper = mountWithApp(AdminSettingsTabLogs)
    await flushPromises()
    getLogsMock.mockClear()

    await filterInput(wrapper, 'statusCode').setValue('404')
    await vi.runAllTimersAsync()

    expect(getLogsMock).toHaveBeenLastCalledWith(expect.objectContaining({ status_code: 404 }))
    vi.useRealTimers()
  })
})
