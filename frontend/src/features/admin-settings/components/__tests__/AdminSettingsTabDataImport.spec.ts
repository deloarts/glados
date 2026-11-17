import { describe, it, expect, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import type { UserResponse } from '@/core/types/userResponse'
import type {
  AdminDataImportSettings,
  UpdateDataImportSettingsCommand,
} from '../../types/adminSettingsTypes'

const getMock = vi.fn<() => Promise<AdminDataImportSettings>>()
const updateMock =
  vi.fn<(cmd: UpdateDataImportSettingsCommand) => Promise<AdminDataImportSettings>>()

vi.mock('../../api/getDataImportSettings', () => ({ getDataImportSettings: () => getMock() }))
vi.mock('../../api/updateDataImportSettings', () => ({
  updateDataImportSettings: (cmd: UpdateDataImportSettingsCommand) => updateMock(cmd),
}))

import AdminSettingsTabDataImport from '../AdminSettingsTabDataImport.vue'

function makeSettings(): AdminDataImportSettings {
  return {
    id: 1,
    public_id: '11111111-1111-1111-1111-111111111111',
    profiles: [
      {
        import_type: 'bought_item_demand',
        header_row: null,
        data_offset: 1,
        max_rows: 100,
        fields: [
          { key: 'project_number', column_names: ['Project'] },
          { key: 'quantity', column_names: [] },
        ],
      },
      {
        import_type: 'made_item_demand',
        header_row: 3,
        data_offset: 2,
        max_rows: 50,
        fields: [{ key: 'revision', column_names: ['Rev'] }],
      },
    ],
  }
}

async function mountTab(permissions = ['read:settings', 'write:settings']) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useCurrentUserStore().user = {
    id: 1,
    is_systemuser: false,
    is_shared_account: false,
    permissions,
  } as unknown as UserResponse
  getMock.mockResolvedValue(makeSettings())
  updateMock.mockImplementation(async () => makeSettings())

  const wrapper = mountWithApp(AdminSettingsTabDataImport, { pinia })
  await flushPromises()
  return wrapper
}

describe('AdminSettingsTabDataImport', () => {
  it('shows one section per import profile', async () => {
    const wrapper = await mountTab()

    expect(wrapper.find('[data-testid="data-import-profile-bought_item_demand"]').exists()).toBe(
      true,
    )
    expect(wrapper.find('[data-testid="data-import-profile-made_item_demand"]').exists()).toBe(
      true,
    )
  })

  it('saves every profile with null for an automatic header row', async () => {
    const wrapper = await mountTab()

    await wrapper.find('[data-testid="data-import-save"]').trigger('click')
    await flushPromises()

    expect(updateMock).toHaveBeenCalledWith({
      profiles: [
        {
          import_type: 'bought_item_demand',
          header_row: null,
          data_offset: 1,
          max_rows: 100,
          column_names: { project_number: ['Project'], quantity: [] },
        },
        {
          import_type: 'made_item_demand',
          header_row: 3,
          data_offset: 2,
          max_rows: 50,
          column_names: { revision: ['Rev'] },
        },
      ],
    })
  })

  it('disables saving without write permission', async () => {
    const wrapper = await mountTab(['read:settings'])

    expect(wrapper.find('[data-testid="data-import-save"]').attributes('disabled')).toBeDefined()
  })
})
