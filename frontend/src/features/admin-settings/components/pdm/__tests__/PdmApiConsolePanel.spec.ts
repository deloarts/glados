import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import Tooltip from 'openvue/tooltip'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { i18n } from '@/core/i18n'
import PdmApiConsolePanel from '../PdmApiConsolePanel.vue'
import type { PdmOperation } from '../../../types/adminSettingsTypes'

const getMock = vi.fn<(url: string) => Promise<{ data: unknown }>>()

vi.mock('@/core/api', () => ({
  default: {
    get: (url: string) => getMock(url),
  },
}))

function makeOperation(overrides: Partial<PdmOperation> = {}): PdmOperation {
  return {
    id: 'get_api_vaultname_version',
    method: 'GET',
    path: 'api/version/webapi',
    group: 'Version',
    description: 'Returns the Web API product/version info.',
    params: [],
    has_body: false,
    body_example: null,
    mutating: false,
    ...overrides,
  }
}

function operationsFixture(): PdmOperation[] {
  return [
    makeOperation(),
    makeOperation({
      id: 'post_api_vaultname_authenticate',
      method: 'POST',
      path: 'api/{vaultName}/authenticate',
      group: 'Authentication',
      description: 'Authenticates the specified login for the specified vault.',
      params: [
        { name: 'vaultName', location: 'path', type: 'string', required: true, description: '' },
        { name: 'Username', location: 'body', type: 'string', required: false, description: '' },
      ],
      has_body: true,
      body_example: '{\n  "Username": "sample string 1"\n}',
      mutating: false,
    }),
    makeOperation({
      id: 'post_files_id_checkin',
      method: 'POST',
      path: 'files/{id}/checkin',
      group: 'Files',
      description: 'Checks in the specified file.',
      params: [{ name: 'id', location: 'path', type: 'integer', required: true, description: '' }],
      has_body: false,
      body_example: null,
      mutating: true,
    }),
  ]
}

async function mountPanel(criticalMode = false, mutatingOperationsEnabled = true) {
  const wrapper = mountWithApp(PdmApiConsolePanel, {
    props: { criticalMode, mutatingOperationsEnabled },
    global: { directives: { tooltip: Tooltip } },
  })
  await flushPromises()
  return wrapper
}

describe('PdmApiConsolePanel', () => {
  beforeEach(() => {
    getMock.mockReset()
    getMock.mockResolvedValue({ data: operationsFixture() })
  })

  it('loads and groups operations by their resource group', async () => {
    const wrapper = await mountPanel()

    expect(getMock).toHaveBeenCalledWith('/admin/settings/pdm/operations')
    expect(wrapper.text()).toContain('Version')
    expect(wrapper.text()).toContain('Authentication')
    expect(wrapper.text()).toContain('Files')
    expect(wrapper.text()).toContain('api/version/webapi')
    expect(wrapper.text()).toContain('api/{vaultName}/authenticate')

    wrapper.unmount()
  })

  it('filters rows by the search box', async () => {
    const wrapper = await mountPanel()

    const search = wrapper.find('input[placeholder="' + i18n.global.t('adminSettings.solidworksPdm.pdm.console.searchPlaceholder') + '"]')
    await search.setValue('checkin')
    await flushPromises()

    expect(wrapper.text()).toContain('files/{id}/checkin')
    expect(wrapper.text()).not.toContain('api/version/webapi')
    expect(wrapper.text()).not.toContain('api/{vaultName}/authenticate')

    wrapper.unmount()
  })

  it('locks mutating rows while critical mode is off, and unlocks them once it is on', async () => {
    const lockedWrapper = await mountPanel(false)
    const lockedRow = lockedWrapper.findAll('.op-row').find((row) => row.text().includes('checkin'))!
    expect(lockedRow.classes()).toContain('op-row--locked')
    expect(lockedRow.find('[data-testid="op-lock"]').exists()).toBe(true)
    lockedWrapper.unmount()

    const unlockedWrapper = await mountPanel(true)
    const unlockedRow = unlockedWrapper
      .findAll('.op-row')
      .find((row) => row.text().includes('checkin'))!
    expect(unlockedRow.classes()).not.toContain('op-row--locked')
    expect(unlockedRow.find('[data-testid="op-lock"]').exists()).toBe(false)
    unlockedWrapper.unmount()
  })

  it('clicking a locked mutating row does not open the operation dialog', async () => {
    const wrapper = await mountPanel(false)

    const lockedRow = wrapper.findAll('.op-row').find((row) => row.text().includes('checkin'))!
    await lockedRow.trigger('click')
    await flushPromises()

    const dialog = wrapper.findComponent({ name: 'PdmOperationDialog' })
    expect(dialog.props('visible')).toBe(false)

    wrapper.unmount()
  })

  it('clicking an unlocked row opens the operation dialog for that operation', async () => {
    const wrapper = await mountPanel()

    const row = wrapper.findAll('.op-row').find((r) => r.text().includes('api/version/webapi'))!
    await row.trigger('click')
    await flushPromises()

    const dialog = wrapper.findComponent({ name: 'PdmOperationDialog' })
    expect(dialog.props('visible')).toBe(true)
    expect(dialog.props('operation')).toMatchObject({ id: 'get_api_vaultname_version' })

    wrapper.unmount()
  })

  it('emits close when the close button is clicked', async () => {
    const wrapper = await mountPanel()

    await wrapper
      .findAllComponents({ name: 'Button' })
      .find((b) => b.props('icon') === 'mdi mdi-close')!
      .trigger('click')

    expect(wrapper.emitted('close')).toHaveLength(1)

    wrapper.unmount()
  })

  it('shows the load-failed message and lets the user reload', async () => {
    getMock.mockReset()
    getMock.mockRejectedValue(new Error('network error'))

    const wrapper = await mountPanel()

    expect(wrapper.text()).toContain(
      i18n.global.t('adminSettings.solidworksPdm.pdm.console.loadFailed'),
    )

    getMock.mockResolvedValue({ data: operationsFixture() })
    await wrapper
      .findAllComponents({ name: 'Button' })
      .find((b) => b.props('label') === (i18n.global.t('common.reload') as string))!
      .trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('api/version/webapi')

    wrapper.unmount()
  })
})
