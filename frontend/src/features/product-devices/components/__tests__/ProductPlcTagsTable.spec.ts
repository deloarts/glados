import { describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { reactive, ref } from 'vue'

import { mountWithApp } from '@/test-utils/mountWithApp'
import type { PlcTagList } from '../../types/productDevice'

const fakeLiveStore = reactive({ reconnectCount: ref(0), on: () => () => {} })
vi.mock('@/core/realtime/liveStore', () => ({ useLiveStore: () => fakeLiveStore }))

const LIST: PlcTagList = {
  environment: { id: 1, name: 'TIA', max_tag_length: 20, export_sheet: 'PLC Tags', export_columns: [] },
  tags: [
    {
      device_id: 1,
      device_name: 'B01 Zylinder P1',
      device_name_ascii: 'B01_Zylinder_P1',
      component_id: 10,
      signal_index: 0,
      name: 'di_B01_Zylinder_P1_AUS_lang',
      tag_table: 'Standard-Variablentabelle',
      address: null,
      comment: 'B01 Zylinder P1: ausgefahren',
      signal_type: 'di',
      safety: true,
      data_type: '',
      overridden: false,
      too_long: true,
      duplicate: false,
      manual_id: null,
    },
  ],
}
const exportMock = vi.fn<(list: PlcTagList, productNumber: string) => Promise<void>>()
vi.mock('../../api/plcTagsApi', () => ({
  getProductPlcTags: () => Promise.resolve(LIST),
  deleteManualPlcTag: vi.fn<() => Promise<void>>(),
}))
vi.mock('openvue/useconfirm', () => ({ useConfirm: () => ({ require: vi.fn<() => void>() }) }))
vi.mock('../../utils/plcTagExport', () => ({
  writePlcTagExportFile: (list: PlcTagList, productNumber: string) => exportMock(list, productNumber),
}))

import ProductPlcTagsTable from '../ProductPlcTagsTable.vue'
import { useProductDevicesViewStore } from '../../stores/productDevicesViewStore'

describe('ProductPlcTagsTable', () => {
  it('lists the tags with their problems and exports on request', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const wrapper = mountWithApp(ProductPlcTagsTable, {
      pinia,
      global: { stubs: { ConfirmDialog: true, PlcTagDialog: true } },
      props: { productId: 3, productNumber: 'M26001', canEdit: false },
    })
    await flushPromises()
    expect(wrapper.text()).toContain('di_B01_Zylinder_P1_AUS_lang')
    expect(wrapper.text()).toContain('Too long')
    expect(wrapper.text()).toContain('No address')
    expect(wrapper.text()).toContain('1 need attention.')
    // Without the rights to edit the product, editing is offered disabled.
    expect(wrapper.find('[data-testid="plc-tag-edit"]').attributes('disabled')).toBeDefined()

    useProductDevicesViewStore().requestExport()
    await flushPromises()
    expect(exportMock).toHaveBeenCalledWith(LIST, 'M26001')
  })
})
