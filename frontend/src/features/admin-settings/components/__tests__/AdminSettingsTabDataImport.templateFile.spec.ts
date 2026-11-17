import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { stubFilePicker, textFile } from '@/test-utils/filePicker'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { serializeTemplateFile } from '@/shared/utils/templateFile'
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

function columnNamesFile(name: string, columnNames: Record<string, unknown>): File {
  return textFile(name, serializeTemplateFile('data_import_column_names', { column_names: columnNames }))
}

async function importAndSave(wrapper: Awaited<ReturnType<typeof mountTab>>) {
  await wrapper.find('[data-testid="data-import-import"]').trigger('click')
  await flushPromises()
  await wrapper.find('[data-testid="data-import-save"]').trigger('click')
  await flushPromises()
}

afterEach(() => {
  vi.restoreAllMocks()
})

describe('AdminSettingsTabDataImport template files', () => {
  it('adds the column names of every picked file, once each', async () => {
    const wrapper = await mountTab()
    stubFilePicker([
      columnNamesFile('column_names.enGB.json', {
        bought_item_demand: { project_number: ['project', 'Project number'], quantity: ['Qty'] },
      }),
      columnNamesFile('column_names.deAT.json', {
        bought_item_demand: { quantity: ['Menge', 'Qty'] },
      }),
    ])

    await importAndSave(wrapper)

    expect(updateMock).toHaveBeenCalledWith({
      profiles: [
        expect.objectContaining({
          column_names: { project_number: ['Project', 'Project number'], quantity: ['Qty', 'Menge'] },
        }),
      ],
    })
  })

  it('changes nothing when one of the files is broken', async () => {
    const wrapper = await mountTab()
    stubFilePicker([
      columnNamesFile('good.json', { bought_item_demand: { quantity: ['Qty'] } }),
      columnNamesFile('bad.json', { bought_item_demand: { quantity: 'Qty' } }),
    ])

    await importAndSave(wrapper)

    expect(updateMock).toHaveBeenCalledWith({
      profiles: [expect.objectContaining({ column_names: { project_number: ['Project'], quantity: [] } })],
    })
  })

  it('exports the column names in the format the import reads', async () => {
    const wrapper = await mountTab()
    const createObjectURL = vi.fn<(blob: Blob) => string>(() => 'blob:x')
    vi.stubGlobal('URL', Object.assign(URL, { createObjectURL, revokeObjectURL: vi.fn<(url: string) => void>() }))
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})

    await wrapper.find('[data-testid="data-import-export"]').trigger('click')

    const blob = createObjectURL.mock.calls[0]![0]
    expect(JSON.parse(await blob.text())).toEqual({
      glados_template: 'data_import_column_names',
      version: 1,
      column_names: { bought_item_demand: { project_number: ['Project'], quantity: [] } },
    })
  })

  it('disables importing without write permission', async () => {
    const wrapper = await mountTab(['read:settings'])

    expect(wrapper.find('[data-testid="data-import-import"]').attributes('disabled')).toBeDefined()
    expect(wrapper.find('[data-testid="data-import-export"]').attributes('disabled')).toBeUndefined()
  })
})
