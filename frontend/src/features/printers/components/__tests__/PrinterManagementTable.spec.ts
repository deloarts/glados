import { describe, it, expect, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ConfirmationService from 'openvue/confirmationservice'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { i18n } from '@/core/i18n'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { usePrintersStore } from '../../stores/printersStore'
import { TABLE_DEBOUNCE_MS } from '@/core/constants/table'
import { userWithPermissions } from '@/test-utils/factories'

import type { PrinterResponse } from '../../types/printerResponse'

function makePrinter(overrides: Partial<PrinterResponse> = {}): PrinterResponse {
  return {
    id: 1,
    public_id: '11111111-1111-1111-1111-111111111111',
    archived: false,
    created: '2026-01-01',
    changed: null,
    changed_by_id: null,
    changed_by_full_name: '',
    name: 'Zebra ZT230',
    internal_name: 'zebra-zt230',
    kind: 'zpl_label',
    host: '192.0.2.10',
    port: 9100,
    timeout_seconds: 5,
    transport: 'raw',
    ipp_uri_path: '/',
    head_dpi: 300,
    format_convert_factor: 2,
    default_media: null,
    location: 'Shop floor',
    vendor: 'Zebra',
    model: 'ZT230',
    firmware: null,
    bought_item_ids: [],
    bought_items: [],
    enabled: true,
    is_default: false,
    note: null,
    creator_id: 1,
    creator_full_name: 'Creator',
    changes: [],
    ...overrides,
  }
}

vi.mock('@/core/api', () => ({
  default: {
    get: vi.fn<() => Promise<unknown>>().mockResolvedValue({
      data: {
        items: [
          {
            id: 1,
            public_id: '11111111-1111-1111-1111-111111111111',
            archived: false,
            created: '2026-01-01',
            changed: null,
            name: 'Zebra ZT230',
            internal_name: 'zebra-zt230',
            kind: 'zpl_label',
            host: '192.0.2.10',
            port: 9100,
            timeout_seconds: 5,
            transport: 'raw',
            ipp_uri_path: '/',
            head_dpi: 300,
            format_convert_factor: 2,
            default_media: null,
            location: 'Shop floor',
            vendor: 'Zebra',
            model: 'ZT230',
            firmware: null,
            bought_item_ids: [],
            bought_items: [],
            enabled: true,
            is_default: false,
            note: null,
            creator_id: 1,
            creator_full_name: 'Creator',
            changes: [],
          },
        ],
        total: 1,
        limit: 25,
        skip: 0,
      },
    }),
  },
}))

import PrinterManagementTable from '../PrinterManagementTable.vue'

describe('PrinterManagementTable', () => {
  it('mounts, loads printers, and renders columns without errors', async () => {
    const logs: unknown[][] = []
    const errorSpy = vi.spyOn(console, 'error').mockImplementation((...args) => {
      logs.push(args)
    })
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation((...args) => {
      logs.push(args)
    })

    const wrapper = mountWithApp(PrinterManagementTable, {
      global: {
        plugins: [ConfirmationService],
      },
    })

    await flushPromises()
    await flushPromises()

    errorSpy.mockRestore()
    warnSpy.mockRestore()

    expect(wrapper.exists()).toBe(true)
    expect(logs).toEqual([])
    expect(wrapper.text()).toContain('Zebra ZT230')
    expect(wrapper.text()).toContain('192.0.2.10:9100')

    wrapper.unmount()
  })

  it('shows an Archive row action for a live printer, and a Restore action once it is archived', async () => {
    const apiModule = await import('@/core/api')
    const getMock = apiModule.default.get as ReturnType<typeof vi.fn>

    async function mountWithArchived(archived: boolean) {
      getMock.mockResolvedValue({
        data: { items: [makePrinter({ archived })], total: 1, limit: 25, skip: 0 },
      })

      const pinia = createPinia()
      setActivePinia(pinia)
      useCurrentUserStore().user = userWithPermissions(['write:printers'])
      usePrintersStore().showActions = true

      const wrapper = mountWithApp(PrinterManagementTable, {
        pinia,
        global: {
          plugins: [ConfirmationService],
        },
      })
      await flushPromises()
      await flushPromises()
      return wrapper
    }

    const live = await mountWithArchived(false)
    expect(live.find('[aria-label="' + i18n.global.t('common.archive') + '"]').exists()).toBe(true)
    expect(live.find('[aria-label="' + i18n.global.t('common.restore') + '"]').exists()).toBe(false)
    live.unmount()

    const archived = await mountWithArchived(true)
    expect(archived.find('[aria-label="' + i18n.global.t('common.restore') + '"]').exists()).toBe(true)
    expect(archived.find('[aria-label="' + i18n.global.t('common.archive') + '"]').exists()).toBe(false)
    archived.unmount()
  })

  it('sends typed and selected row filters as query params, and clearAll drops them', async () => {
    const apiModule = await import('@/core/api')
    const getMock = apiModule.default.get as ReturnType<typeof vi.fn>
    getMock.mockResolvedValue({
      data: { items: [makePrinter()], total: 1, limit: 25, skip: 0 },
    })

    const pinia = createPinia()
    setActivePinia(pinia)
    const store = usePrintersStore()

    const wrapper = mountWithApp(PrinterManagementTable, {
      pinia,
      global: {
        plugins: [ConfirmationService],
      },
    })
    await flushPromises()
    getMock.mockClear()

    const nameLabel = i18n.global.t('common.filterBy', {
      column: i18n.global.t('printers.columns.name'),
    })
    const nameInput = wrapper.find(`input[aria-label="${nameLabel}"]`)
    expect(nameInput.exists()).toBe(true)
    await nameInput.setValue('zebra')
    expect(getMock).not.toHaveBeenCalled()

    await new Promise((resolve) => setTimeout(resolve, TABLE_DEBOUNCE_MS + 50))
    await flushPromises()
    expect(getMock).toHaveBeenLastCalledWith('/printers/', {
      params: expect.objectContaining({ name: 'zebra', skip: 0 }),
    })
    expect(store.hasActiveFilters).toBe(true)

    store.filters = { ...store.filters, enabled: { value: false, matchMode: 'equals' } }
    await flushPromises()
    expect(getMock).toHaveBeenLastCalledWith('/printers/', {
      params: expect.objectContaining({ name: 'zebra', enabled: false }),
    })

    getMock.mockClear()
    store.clearAll()
    await flushPromises()
    expect(store.hasActiveFilters).toBe(false)
    expect(getMock).toHaveBeenCalled()
    const lastCall = getMock.mock.lastCall
    expect(lastCall).toBeDefined()
    const lastParams = (lastCall![1] as { params: Record<string, unknown> }).params
    expect(lastParams).not.toHaveProperty('name')
    expect(lastParams).not.toHaveProperty('enabled')

    wrapper.unmount()
  })

  it('disables Printer Status without Print Documents and Print History without Read Settings, naming the permission', async () => {
    const apiModule = await import('@/core/api')
    const getMock = apiModule.default.get as ReturnType<typeof vi.fn>
    getMock.mockResolvedValue({
      data: { items: [makePrinter()], total: 1, limit: 25, skip: 0 },
    })

    const pinia = createPinia()
    setActivePinia(pinia)
    useCurrentUserStore().user = userWithPermissions([])
    usePrintersStore().showActions = true

    const wrapper = mountWithApp(PrinterManagementTable, {
      pinia,
      global: { plugins: [ConfirmationService] },
    })
    await flushPromises()
    await flushPromises()

    const status = wrapper.get('[data-testid="printer-status"]')
    expect(status.attributes('disabled')).toBeDefined()
    expect(tooltipOf(status)).toBe('This needs the permission Print Documents.')

    wrapper.findComponent({ name: 'DataTable' }).vm.$emit('update:contextMenuSelection', makePrinter())
    await flushPromises()
    const items = wrapper.findComponent({ name: 'ContextMenu' }).props('model') as {
      label?: string
      disabled?: boolean
      title?: string
    }[]
    const statusItem = items.find((item) => item.label === i18n.global.t('printers.status.title'))!
    const historyItem = items.find((item) => item.label === i18n.global.t('printers.history.menuLabel'))!
    expect(statusItem.disabled).toBe(true)
    expect(statusItem.title).toBe('This needs the permission Print Documents.')
    expect(historyItem.disabled).toBe(true)
    expect(historyItem.title).toBe('This needs the permission Read Settings.')

    wrapper.unmount()
  })

  it('enables Printer Status and Print History with Print Documents and Read Settings', async () => {
    const apiModule = await import('@/core/api')
    const getMock = apiModule.default.get as ReturnType<typeof vi.fn>
    getMock.mockResolvedValue({
      data: { items: [makePrinter()], total: 1, limit: 25, skip: 0 },
    })

    const pinia = createPinia()
    setActivePinia(pinia)
    useCurrentUserStore().user = userWithPermissions(['print:documents', 'read:settings'])
    usePrintersStore().showActions = true

    const wrapper = mountWithApp(PrinterManagementTable, {
      pinia,
      global: { plugins: [ConfirmationService] },
    })
    await flushPromises()
    await flushPromises()

    const status = wrapper.get('[data-testid="printer-status"]')
    expect(status.attributes('disabled')).toBeUndefined()
    expect(tooltipOf(status)).toBeUndefined()

    wrapper.findComponent({ name: 'DataTable' }).vm.$emit('update:contextMenuSelection', makePrinter())
    await flushPromises()
    const items = wrapper.findComponent({ name: 'ContextMenu' }).props('model') as {
      label?: string
      disabled?: boolean
    }[]
    const historyItem = items.find((item) => item.label === i18n.global.t('printers.history.menuLabel'))!
    expect(historyItem.disabled).toBe(false)

    wrapper.unmount()
  })
})

/** The tooltip of a button, kept by OpenVue's Tooltip directive on the span around it. */
function tooltipOf(button: { element: Element }): string | undefined {
  return (button.element.parentElement as (HTMLElement & { $_ptooltipValue?: string }) | null)?.$_ptooltipValue
}
