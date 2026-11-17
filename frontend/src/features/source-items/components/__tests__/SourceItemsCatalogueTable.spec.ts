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
  const sourceItemsPage = {
    data: {
      items: [
        {
          id: 1,
          public_id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
          status: 'active',
          archived: false,
          created: '2026-01-01',
          changed: null,
          type_id: 1,
          type_name: 'Rod',
          dimension: '10mm',
          material: 'Steel',
          mass: 100,
          note: null,
          order_code_1: null,
          order_code_2: null,
          successor_item_id: null,
          creator_id: 1,
          creator: null,
          approver_id: null,
          manufacturer_id: null,
          manufacturer_name: '',
        },
      ],
      total: 1,
      limit: 25,
      skip: 0,
    },
  }

  // The edit form's type and manufacturer Selects resolve their currently-
  // selected option by id out of these two stores' own item lists, which
  // need a real `name` field to do that (unlike the source-items list
  // above, whose fields don't match `optionLabel="name"`); otherwise
  // OpenVue's Select computes an undefined label and throws once the
  // context-menu "Edit" entry opens the form.
  const sourceItemTypesPage = {
    data: { items: [{ id: 1, name: 'Rod' }], total: 1, limit: 25, skip: 0 },
  }
  const suppliersPage = {
    data: { items: [], total: 0, limit: 25, skip: 0 },
  }

  return {
    default: {
      get: vi.fn<(url: string) => Promise<unknown>>().mockImplementation((url: string) => {
        if (url === '/source-item-types/') return Promise.resolve(sourceItemTypesPage)
        if (url === '/suppliers/') return Promise.resolve(suppliersPage)
        return Promise.resolve(sourceItemsPage)
      }),
    },
  }
})

import SourceItemsCatalogueTable from '../SourceItemsCatalogueTable.vue'
import { useSourceItemsCatalogueEditStore } from '../../stores/sourceItemsCatalogueEditStore'
import { useSourceItemsStore } from '../../stores/sourceItemsStore'

// The print-label context-menu entry reads its strings from
// `sourceItems.edit.contextMenu.*`; `sourceItems.catalogue.contextMenu.*`
// does not exist in the locale files and would render the raw dotted key
// instead of "Print Label".
describe('SourceItemsCatalogueTable', () => {
  beforeEach(() => {
    pushMock.mockClear()
  })

  it('resolves the print-label context-menu entry instead of rendering a raw i18n key', async () => {
    const wrapper = mountWithApp(SourceItemsCatalogueTable, {
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

    const items = contextMenu.props('model') as Array<{ label?: string }>
    const printLabelItem = items.find((item) => item.label?.toLowerCase().includes('print'))

    expect(printLabelItem).toBeDefined()
    expect(printLabelItem?.label).not.toMatch(/^[a-z]+(\.[a-zA-Z]+)+$/)
    expect(printLabelItem?.label).toBe('Print Label')
  })

  // The context menu offers Archive for a live row and Restore for an
  // already-archived one; the fixture row above is not archived, so only
  // Archive should be offered.
  it('offers Archive (not Restore) for a live row in the context menu', async () => {
    const wrapper = mountWithApp(SourceItemsCatalogueTable, {
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

  // selectionMode="single" makes every row keyboard-reachable and gives
  // Enter the same effect as a click, via the shared useRowOpenGuard recipe
  // proven on OrdersTable/ArticleGroupManagementTable.
  it('makes the first row keyboard-focusable outside edit mode', async () => {
    const wrapper = mountWithApp(SourceItemsCatalogueTable, {
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
    const wrapper = mountWithApp(SourceItemsCatalogueTable, {
      global: {
        plugins: [ConfirmationService],
      },
    })

    await flushPromises()

    const item = useSourceItemsStore().items[0]
    expect(item).toBeDefined()

    const dataTable = wrapper.findComponent({ name: 'DataTable' })
    dataTable.vm.$emit('row-select', { data: item, index: 0, originalEvent: new Event('keydown') })
    await flushPromises()

    expect(pushMock).toHaveBeenCalledWith(`/catalogue/source-items/${item!.id}`)
    expect(wrapper.findComponent({ name: 'SourceItemDetailDialog' }).props('visible')).toBe(false)
  })

  // The bulk-edit checkbox column (editStore.editMode) binds this same
  // DataTable's `selection`/`selectionMode` to an *array* for batch
  // actions, and the new single-row-open wiring must not fight it (the
  // "do not clobber existing nested selection" guard, verified empirically
  // on MadeItemsCatalogueTable, which shares this exact recipe).
  it('does not clobber the bulk-edit selection array when a row is checked, then clicked, in edit mode', async () => {
    const wrapper = mountWithApp(SourceItemsCatalogueTable, {
      global: {
        plugins: [ConfirmationService],
      },
    })
    await flushPromises()

    const editStore = useSourceItemsCatalogueEditStore()
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
    const wrapper = mountWithApp(SourceItemsCatalogueTable, {
      global: { plugins: [ConfirmationService] },
    })
    await flushPromises()

    const editStore = useSourceItemsCatalogueEditStore()
    editStore.editMode = true
    await flushPromises()

    const dialog = () => wrapper.findComponent({ name: 'SourceItemDetailDialog' })
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
    const wrapper = mountWithApp(SourceItemsCatalogueTable, {
      global: { plugins: [ConfirmationService] },
    })
    await flushPromises()

    const row = wrapper.find('tbody tr')
    await row.trigger('click')
    await flushPromises()

    expect(pushMock).toHaveBeenCalledWith('/catalogue/source-items/1')
    expect(wrapper.findComponent({ name: 'SourceItemDetailDialog' }).props('visible')).toBe(false)
  })

  // The dialog stays mounted in the table purely so the context menu's
  // "Edit" entry can still open it, in edit mode; unlike a plain row
  // click/select, this must not navigate anywhere.
  it('context-menu edit still opens the dialog in edit mode', async () => {
    const wrapper = mountWithApp(SourceItemsCatalogueTable, {
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
      (item) => item.label === i18n.global.t('sourceItems.catalogue.controls.edit'),
    )
    expect(editEntry).toBeDefined()

    editEntry?.command?.()
    await flushPromises()

    const dialog = wrapper.findComponent({ name: 'SourceItemDetailDialog' })
    expect(dialog.props('visible')).toBe(true)
    expect(dialog.props('editOnOpen')).toBe(true)
    expect(pushMock).not.toHaveBeenCalled()
  })
})
