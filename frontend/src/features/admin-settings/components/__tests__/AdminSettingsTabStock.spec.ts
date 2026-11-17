import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import type { ToastMessageOptions } from 'openvue/toast'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { i18n } from '@/core/i18n'
import type { UserResponse } from '@/core/types/userResponse'
import type {
  AdminStockSettings,
  StockServiceTestResult,
  UpdateStockSettingsCommand,
  VerifyStockServiceCommand,
} from '../../types/adminSettingsTypes'

const getMock = vi.fn<() => Promise<AdminStockSettings>>()
const updateMock = vi.fn<(cmd: UpdateStockSettingsCommand) => Promise<AdminStockSettings>>()
const testMock = vi.fn<(cmd: VerifyStockServiceCommand) => Promise<StockServiceTestResult>>()

vi.mock('@/features/admin-settings/api/stockSettingsApi', () => ({
  getStockSettings: () => getMock(),
  updateStockSettings: (cmd: UpdateStockSettingsCommand) => updateMock(cmd),
  testStockService: (cmd: VerifyStockServiceCommand) => testMock(cmd),
}))

const toastAddMock = vi.fn<(options: ToastMessageOptions) => void>()
vi.mock('openvue/usetoast', () => ({
  useToast: () => ({ add: toastAddMock }),
}))

import AdminSettingsTabStock from '../AdminSettingsTabStock.vue'

const t = i18n.global.t

const SERVICE_URL = 'http://stock.example.test:3200'

function makeSettings(overrides: Partial<AdminStockSettings> = {}): AdminStockSettings {
  return {
    id: 1,
    public_id: '11111111-1111-1111-1111-111111111111',
    enabled: true,
    service_url: SERVICE_URL,
    api_key_configured: true,
    is_configured: true,
    is_ready: true,
    ...overrides,
  }
}

function makeTestResult(overrides: Partial<StockServiceTestResult> = {}): StockServiceTestResult {
  return {
    service: 'example-stock-service',
    service_version: '0.1.0',
    contract_version: '0.1',
    contract_supported: true,
    provider_label: 'Example Stock',
    server_version: '4.2',
    ...overrides,
  }
}

async function mountTab(
  settings: AdminStockSettings,
  permissions = ['read:settings', 'write:settings'],
) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useCurrentUserStore().user = {
    id: 1,
    is_systemuser: false,
    is_shared_account: false,
    permissions,
  } as unknown as UserResponse
  getMock.mockResolvedValue(settings)

  const wrapper = mountWithApp(AdminSettingsTabStock, { pinia })
  await flushPromises()
  return wrapper
}

type Wrapper = Awaited<ReturnType<typeof mountTab>>

function button(wrapper: Wrapper, testId: string) {
  return wrapper.find<HTMLButtonElement>(`[data-testid="${testId}"]`)
}

describe('AdminSettingsTabStock', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('loads the settings on its own, fills the form and never shows the API key', async () => {
    const wrapper = await mountTab(makeSettings())

    expect(getMock).toHaveBeenCalledTimes(1)
    expect(wrapper.find<HTMLInputElement>('#stock-service-url').element.value).toBe(SERVICE_URL)
    const apiKey = wrapper.find<HTMLInputElement>('#stock-service-api-key')
    expect(apiKey.element.value).toBe('')
    expect(apiKey.attributes('type')).toBe('password')
    expect(apiKey.attributes('placeholder')).toBe(t('adminSettings.stockService.apiKeySaved'))

    wrapper.unmount()
  })

  it('saves the fields and sends the API key only when one was typed', async () => {
    updateMock.mockResolvedValue(makeSettings())
    const wrapper = await mountTab(makeSettings())

    await button(wrapper, 'stock-service-save').trigger('click')
    await flushPromises()

    expect(updateMock).toHaveBeenLastCalledWith({ enabled: true, service_url: SERVICE_URL })

    await wrapper.find('#stock-service-api-key').setValue('new-key')
    await button(wrapper, 'stock-service-save').trigger('click')
    await flushPromises()

    expect(updateMock).toHaveBeenLastCalledWith(expect.objectContaining({ api_key: 'new-key' }))
    expect(wrapper.find<HTMLInputElement>('#stock-service-api-key').element.value).toBe('')

    wrapper.unmount()
  })

  it('tests the unsaved service and shows what it reports', async () => {
    testMock.mockResolvedValue(makeTestResult())
    const wrapper = await mountTab(makeSettings())

    await wrapper.find('#stock-service-url').setValue('http://other-stock:3200')
    await button(wrapper, 'stock-service-test').trigger('click')
    await flushPromises()

    expect(testMock).toHaveBeenCalledWith({ service_url: 'http://other-stock:3200' })
    const result = wrapper.find('[data-testid="stock-service-test-result"]').text()
    expect(result).toContain('example-stock-service 0.1.0')
    expect(result).toContain('Example Stock 4.2')
    expect(wrapper.find('[data-testid="stock-service-contract-unsupported"]').exists()).toBe(false)

    wrapper.unmount()
  })

  it('warns when the service speaks an unsupported contract', async () => {
    testMock.mockResolvedValue(makeTestResult({ contract_supported: false }))
    const wrapper = await mountTab(makeSettings())

    await button(wrapper, 'stock-service-test').trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-testid="stock-service-contract-unsupported"]').text()).toBe(
      t('adminSettings.stockService.contractUnsupported'),
    )

    wrapper.unmount()
  })

  it('shows a translated message for a known error code', async () => {
    testMock.mockRejectedValue({
      isAxiosError: true,
      response: {
        status: 503,
        data: { code: 'StockServiceUnavailableError', detail: 'down' },
      },
    })
    const wrapper = await mountTab(makeSettings())

    await button(wrapper, 'stock-service-test').trigger('click')
    await flushPromises()

    expect(toastAddMock).toHaveBeenCalledWith(
      expect.objectContaining({
        severity: 'error',
        detail: t('adminSettings.stockService.errors.unavailable'),
      }),
    )

    wrapper.unmount()
  })

  it('disables saving and testing without the write permission', async () => {
    const wrapper = await mountTab(makeSettings(), ['read:settings'])

    expect(button(wrapper, 'stock-service-save').element.disabled).toBe(true)
    expect(button(wrapper, 'stock-service-test').element.disabled).toBe(true)

    wrapper.unmount()
  })
})
