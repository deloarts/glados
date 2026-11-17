import { describe, it, expect, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import type { UserResponse } from '@/core/types/userResponse'
import type {
  AdminEdpSettings,
  UpdateEdpSettingsCommand,
} from '@/features/admin-settings'

const getMock = vi.fn<() => Promise<AdminEdpSettings>>()
const updateMock = vi.fn<(cmd: UpdateEdpSettingsCommand) => Promise<AdminEdpSettings>>()

vi.mock('@/features/admin-settings/api/eplanDataPortalSettingsApi', () => ({
  getEdpSettings: () => getMock(),
  updateEdpSettings: (cmd: UpdateEdpSettingsCommand) => updateMock(cmd),
  testEdpConnection: vi.fn<() => Promise<{ authenticated: boolean }>>(),
}))
vi.mock('@/features/article-groups', () => ({
  useArticleGroupsStore: () => ({ items: [], loading: false, refresh: vi.fn<() => void>() }),
}))

import AdminSettingsTabEplanDataPortal from '../AdminSettingsTabEplanDataPortal.vue'

function makeSettings(overrides: Partial<AdminEdpSettings> = {}): AdminEdpSettings {
  return {
    id: 1,
    public_id: '11111111-1111-1111-1111-111111111111',
    enabled: true,
    base_url: 'https://portal.example.test/api',
    pat_configured: true,
    default_article_group_ids: [],
    language: 'de_DE',
    is_configured: true,
    ...overrides,
  }
}

async function mountTab() {
  const pinia = createPinia()
  setActivePinia(pinia)
  useCurrentUserStore().user = {
    id: 1,
    is_systemuser: false,
    is_shared_account: false,
    permissions: ['read:settings', 'write:settings'],
  } as unknown as UserResponse
  getMock.mockResolvedValue(makeSettings())
  updateMock.mockImplementation(async () => makeSettings())
  const wrapper = mountWithApp(AdminSettingsTabEplanDataPortal, { pinia })
  await flushPromises()
  return wrapper
}

describe('AdminSettingsTabEplanDataPortal', () => {
  it('keeps the stored token when the field stays empty', async () => {
    const wrapper = await mountTab()

    await wrapper.find('[data-testid="edp-save"]').trigger('click')
    await flushPromises()

    expect(updateMock).toHaveBeenCalledWith(expect.objectContaining({ pat: null, enabled: true }))
  })

  it('clears the token and switches off on remove', async () => {
    const wrapper = await mountTab()

    await wrapper.find('[data-testid="edp-remove-token"]').trigger('click')
    await flushPromises()

    expect(updateMock).toHaveBeenCalledWith(expect.objectContaining({ pat: '', enabled: false }))
  })
})
