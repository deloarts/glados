import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import ConfirmationService from 'openvue/confirmationservice'

import { i18n } from '@/core/i18n'
import { mountWithApp } from '@/test-utils/mountWithApp'

const pushMock = vi.fn<(to: string) => void>()

// Partial mock: only useRouter's `push` needs to be observable here; the
// rest of vue-router (RouterLink et al, used by the item detail dialog
// mounted alongside this table) must still be the real module.
vi.mock('vue-router', async (importOriginal) => ({
  ...(await importOriginal<typeof import('vue-router')>()),
  useRouter: () => ({ push: pushMock }),
}))

vi.mock('@/core/api', () => {
  const boughtItemsPage = {
    data: {
      items: [
        {
          id: 1,
          part_number: 'PN-1',
          status: 'active',
          archived: false,
          created: '2026-01-01',
          changed: '2026-02-01',
          order_code_1: 'OC1',
          order_code_2: 'OC2',
          gtin: '123',
          ean: '456',
          tariff_number: '789',
          article_name: 'Article',
          article_groups: [
            {
              id: 1,
              created: '2026-01-01',
              changed: '2026-01-01',
              archived: false,
              name: 'Group',
              label_color: '#b0e0e6',
              description: '',
              creator_id: 1,
              creator: {
                id: 1,
                username: 'creator',
                full_name: 'Creator',
                email: 'creator@example.com',
                has_avatar: false,
              },
            },
          ],
          data_source: 'WEB',
          mass: 100,
          note: 'Note',
          weblink: 'http://example.com',
          successor_item_id: null,
          creator_id: 1,
          creator: {
            id: 1,
            username: 'creator',
            full_name: 'Creator',
            email: 'creator@example.com',
            has_avatar: false,
          },
          manufacturer_id: 1,
          manufacturer_name: 'Manufacturer',
        },
      ],
      total: 1,
      limit: 25,
      skip: 0,
    },
  }

  // The edit form's manufacturer Select and article-groups MultiSelect
  // resolve their currently-selected option by id out of these two stores'
  // own item lists, which need a real `name` field to do that (unlike the
  // bought-items list above, whose fields don't match `optionLabel="name"`);
  // otherwise OpenVue's Select computes an undefined label and throws
  // once the context-menu "Edit" entry opens the form.
  const suppliersPage = {
    data: { items: [{ id: 1, name: 'Manufacturer' }], total: 1, limit: 25, skip: 0 },
  }
  const articleGroupsPage = {
    data: { items: [{ id: 1, name: 'Group' }], total: 1, limit: 25, skip: 0 },
  }

  return {
    default: {
      get: vi.fn<(url: string) => Promise<unknown>>().mockImplementation((url: string) => {
        if (url === '/suppliers/') return Promise.resolve(suppliersPage)
        if (url === '/article-groups/') return Promise.resolve(articleGroupsPage)
        // The PdmThumbnail column (rendered only while hostStore.pdmEnabled
        // is on) fetches this as a blob; a 404 keeps it a harmless
        // placeholder rather than handing URL.createObjectURL a plain
        // object dressed up as a Blob.
        if (url.includes('/thumbnail')) {
          return Promise.reject({ isAxiosError: true, response: { status: 404 } })
        }
        // A copy per call: a test that edits a loaded item (the unsafe
        // weblink one) must not change what the next test loads.
        return Promise.resolve(structuredClone(boughtItemsPage))
      }),
    },
  }
})

import BoughtItemsCatalogueTable from '../BoughtItemsCatalogueTable.vue'
import { useBoughtItemsCatalogueEditStore } from '../../stores/boughtItemsCatalogueEditStore'
import { useBoughtItemsStore } from '../../stores/boughtItemsStore'

describe('BoughtItemsCatalogueTable', () => {
  beforeEach(() => {
    pushMock.mockClear()
  })

  it('mounts with all columns and date-range filters without recursive update errors', async () => {
    const logs: unknown[][] = []
    const errorSpy = vi.spyOn(console, 'error').mockImplementation((...args) => {
      logs.push(args)
    })
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation((...args) => {
      logs.push(args)
    })

    const wrapper = mountWithApp(BoughtItemsCatalogueTable, {
      global: {
        plugins: [ConfirmationService],
      },
    })

    await flushPromises()
    await flushPromises()
    await flushPromises()

    errorSpy.mockRestore()
    warnSpy.mockRestore()

    expect(wrapper.exists()).toBe(true)
    expect(logs).toEqual([])
  })

  // Export is not implemented, so its context-menu entry is disabled and
  // inert rather than a stub that would imply a working feature.
  it('offers no Export entry in the context menu, since no catalogue export exists', async () => {
    const wrapper = mountWithApp(BoughtItemsCatalogueTable, {
      global: {
        plugins: [ConfirmationService],
      },
    })

    await flushPromises()
    await flushPromises()
    await flushPromises()

    const row = wrapper.find('tbody tr')
    expect(row.exists()).toBe(true)
    await row.trigger('contextmenu')
    await flushPromises()

    const contextMenu = wrapper.findComponent({ name: 'ContextMenu' })
    expect(contextMenu.exists()).toBe(true)

    const items = contextMenu.props('model') as Array<{ icon?: string }>
    expect(items.map((item) => item.icon)).not.toContain('mdi mdi-export')
  })

  // The context menu offers Archive for a live row and Restore for an
  // already-archived one; the fixture row above is not archived, so only
  // Archive should be offered.
  it('offers Archive (not Restore) for a live row in the context menu', async () => {
    const wrapper = mountWithApp(BoughtItemsCatalogueTable, {
      global: {
        plugins: [ConfirmationService],
      },
    })

    await flushPromises()
    await flushPromises()
    await flushPromises()

    const row = wrapper.find('tbody tr')
    await row.trigger('contextmenu')
    await flushPromises()

    const contextMenu = wrapper.findComponent({ name: 'ContextMenu' })
    const items = contextMenu.props('model') as Array<{ label?: string }>

    expect(items.some((item) => item.label === i18n.global.t('common.archive'))).toBe(true)
    expect(items.some((item) => item.label === i18n.global.t('common.restore'))).toBe(false)
  })

  // selectionMode="single" makes every row keyboard-focusable via the
  // useRowOpenGuard recipe, giving Enter the same effect as a click.
  it('makes the first row keyboard-focusable outside edit mode', async () => {
    const wrapper = mountWithApp(BoughtItemsCatalogueTable, {
      global: {
        plugins: [ConfirmationService],
      },
    })

    await flushPromises()

    const row = wrapper.find('tr[data-p-selectable-row="true"]')
    expect(row.exists()).toBe(true)
    expect(row.attributes('tabindex')).toBe('0')
  })

  it('navigates to the detail page on @row-select the same way @row-click does', async () => {
    const wrapper = mountWithApp(BoughtItemsCatalogueTable, {
      global: {
        plugins: [ConfirmationService],
      },
    })

    await flushPromises()

    const item = useBoughtItemsStore().items[0]
    expect(item).toBeDefined()

    const dataTable = wrapper.findComponent({ name: 'DataTable' })
    dataTable.vm.$emit('row-select', { data: item, index: 0, originalEvent: new Event('keydown') })
    await flushPromises()

    expect(pushMock).toHaveBeenCalledWith(`/catalogue/bought-items/${item!.id}`)
    expect(wrapper.findComponent({ name: 'BoughtItemDetailDialog' }).props('visible')).toBe(false)
  })

  // The bulk-edit checkbox column (editStore.editMode) binds this same
  // DataTable's `selection`/`selectionMode` to an *array* for batch
  // actions; the row-open wiring must not clobber that existing nested
  // selection, verified empirically on MadeItemsCatalogueTable, which
  // shares this exact recipe.
  it('does not clobber the bulk-edit selection array when a row is checked, then clicked, in edit mode', async () => {
    const wrapper = mountWithApp(BoughtItemsCatalogueTable, {
      global: {
        plugins: [ConfirmationService],
      },
    })
    await flushPromises()

    const editStore = useBoughtItemsCatalogueEditStore()
    editStore.editMode = true
    await flushPromises()

    const checkbox = wrapper.find('input[type="checkbox"]')
    expect(checkbox.exists()).toBe(true)
    await checkbox.setValue(true)
    await flushPromises()

    expect(editStore.selectedItems).toHaveLength(1)
    expect(editStore.selectedItems[0]).toMatchObject({ id: 1 })

    const row = wrapper.find('tbody tr')
    await row.trigger('click')
    await flushPromises()

    expect(editStore.selectedItems).toHaveLength(1)
    expect(editStore.selectedItems[0]).toMatchObject({ id: 1 })
  })

  // The bulk-select checkbox click also bubbles into onRowClick, which would
  // open the detail dialog on top of the edit panel (see the "does not
  // clobber" test above for selection). onRowClick/onRowSelect are gated on
  // editStore.editMode so neither the checkbox nor a plain row click can
  // open the dialog while bulk edit is active, and selection still works.
  it('does not open the detail dialog when the bulk-select checkbox or a plain row click fires in edit mode', async () => {
    const wrapper = mountWithApp(BoughtItemsCatalogueTable, {
      global: { plugins: [ConfirmationService] },
    })
    await flushPromises()

    const editStore = useBoughtItemsCatalogueEditStore()
    editStore.editMode = true
    await flushPromises()

    const dialog = () => wrapper.findComponent({ name: 'BoughtItemDetailDialog' })
    expect(dialog().props('visible')).toBe(false)

    const checkbox = wrapper.find('input[type="checkbox"]')
    expect(checkbox.exists()).toBe(true)
    await checkbox.setValue(true)
    await flushPromises()

    expect(editStore.selectedItems).toHaveLength(1)
    expect(dialog().props('visible')).toBe(false)

    const row = wrapper.find('tbody tr')
    await row.trigger('click')
    await flushPromises()

    expect(dialog().props('visible')).toBe(false)
    expect(editStore.selectedItems).toHaveLength(1)
  })

  // The counterpart to the test above: outside edit mode, the row-open gate
  // must stay a no-op so a row click still opens the item, by navigating to
  // its detail page.
  it('navigates to the detail page on row click', async () => {
    const wrapper = mountWithApp(BoughtItemsCatalogueTable, {
      global: { plugins: [ConfirmationService] },
    })
    await flushPromises()

    const row = wrapper.find('tbody tr')
    await row.trigger('click')
    await flushPromises()

    expect(pushMock).toHaveBeenCalledWith('/catalogue/bought-items/1')
    expect(wrapper.findComponent({ name: 'BoughtItemDetailDialog' }).props('visible')).toBe(false)
  })

  // The dialog stays mounted in the table purely so the context menu's
  // "Edit" entry can still open it, in edit mode; unlike a plain row
  // click/select, this must not navigate anywhere.
  it('context-menu edit still opens the dialog in edit mode', async () => {
    const wrapper = mountWithApp(BoughtItemsCatalogueTable, {
      global: {
        plugins: [ConfirmationService],
      },
    })

    await flushPromises()

    const row = wrapper.find('tbody tr')
    expect(row.exists()).toBe(true)
    await row.trigger('contextmenu')
    await flushPromises()

    const contextMenu = wrapper.findComponent({ name: 'ContextMenu' })
    expect(contextMenu.exists()).toBe(true)

    const items = contextMenu.props('model') as Array<{
      label?: string
      command?: () => void
    }>
    const editEntry = items.find(
      (item) => item.label === i18n.global.t('boughtItems.catalogue.controls.edit'),
    )
    expect(editEntry).toBeDefined()

    editEntry?.command?.()
    await flushPromises()

    const dialog = wrapper.findComponent({ name: 'BoughtItemDetailDialog' })
    expect(dialog.props('visible')).toBe(true)
    expect(dialog.props('editOnOpen')).toBe(true)
    expect(pushMock).not.toHaveBeenCalled()
  })

  it('renders a safe weblink as a clickable href in the weblink column', async () => {
    const wrapper = mountWithApp(BoughtItemsCatalogueTable, {
      global: {
        plugins: [ConfirmationService],
      },
    })
    await flushPromises()

    const link = wrapper.find('a.weblink-cell')
    expect(link.exists()).toBe(true)
    expect(link.attributes('href')).toBe('http://example.com')
  })

  it('renders no href for an unsafe weblink, but still shows it as text', async () => {
    const wrapper = mountWithApp(BoughtItemsCatalogueTable, {
      global: {
        plugins: [ConfirmationService],
      },
    })
    await flushPromises()

    const item = useBoughtItemsStore().items[0]
    expect(item).toBeDefined()
    item!.weblink = 'javascript:alert(1)'
    await flushPromises()

    expect(wrapper.find('a.weblink-cell').exists()).toBe(false)
    expect(wrapper.text()).toContain('javascript:alert(1)')
  })
})
